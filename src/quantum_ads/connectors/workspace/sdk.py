"""Live boundary — smoke-gated, not unit-tested.

Real Google Workspace SDK glue: lazy factories building the read callable (Drive files.list,
Sheets values.get, Sheets spreadsheets.get) and the mutate callable (Sheets values.update,
Sheets spreadsheets.create, Slides presentations.create). Isolated at the untyped third-party
boundary (``googleapiclient.*`` is mypy-ignored; this module is coverage-omitted via the live
gate). Imports are local so importing this module stays cheap and credential-free; OAuth
credentials are derived from the shared Google creds dict. SDK-derived values stay implicitly
typed (``Any``).

Three discovery surfaces, all via ``googleapiclient.discovery.build``:
  - ``drive`` v3   — files.list
  - ``sheets`` v4  — spreadsheets.values.get / spreadsheets.get / spreadsheets.values.update /
                     spreadsheets.create
  - ``slides`` v1  — presentations.create

Python package: ``google-api-python-client`` (plus ``google-auth``).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

ReadFn = Callable[[str, dict[str, object]], list[dict[str, object]]]
MutateFn = Callable[[str, list[dict[str, object]], bool], dict[str, object]]

# Read-only scopes cover Drive metadata listing + Sheets reads; the read/write scopes are required
# to write Sheets ranges, create spreadsheets, and create Slides decks.
_READONLY_SCOPES = [
    "https://www.googleapis.com/auth/drive.metadata.readonly",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
]
_WRITE_SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/presentations",
]


def _oauth_credentials(creds: dict[str, object], scopes: list[str]) -> Any:
    from google.oauth2.credentials import Credentials

    return Credentials(
        token=None,
        refresh_token=str(creds["refresh_token"]),
        client_id=str(creds["client_id"]),
        client_secret=str(creds["client_secret"]),
        token_uri="https://oauth2.googleapis.com/token",
        scopes=scopes,
    )


def read_factory(creds: dict[str, object], version: str) -> ReadFn:
    """Build the Workspace ReadFn dispatching the three read operations."""
    from googleapiclient.discovery import build

    credentials = _oauth_credentials(creds, _READONLY_SCOPES)
    drive = build("drive", "v3", credentials=credentials, cache_discovery=False)
    sheets = build("sheets", "v4", credentials=credentials, cache_discovery=False)

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        if operation == "drive.files.list":
            response = drive.files().list(q=str(params.get("query", "")) or None).execute()
            return [dict(entry) for entry in response.get("files", [])]
        if operation == "sheets.values.get":
            response = (
                sheets.spreadsheets()
                .values()
                .get(
                    spreadsheetId=str(params["spreadsheet_id"]),
                    range=str(params["range_a1"]),
                )
                .execute()
            )
            return [dict(response)]
        if operation == "sheets.spreadsheets.get":
            response = (
                sheets.spreadsheets().get(spreadsheetId=str(params["spreadsheet_id"])).execute()
            )
            return [dict(response)]
        raise ValueError(f"unsupported workspace read operation: {operation!r}")

    return read


def mutate_factory(creds: dict[str, object], version: str) -> MutateFn:
    """Build the Workspace MutateFn over Sheets (values.update / spreadsheets.create) + Slides.

    ``validate_only`` short-circuits to a synthetic preview because these endpoints do not expose
    a server-side validate-only flag; the guarded preview still surfaces the exact op dicts that
    would be applied before the confirm step.
    """
    from googleapiclient.discovery import build

    credentials = _oauth_credentials(creds, _WRITE_SCOPES)
    sheets = build("sheets", "v4", credentials=credentials, cache_discovery=False)
    slides = build("slides", "v1", credentials=credentials, cache_discovery=False)

    def _write_range(account_id: str, op: dict[str, object]) -> dict[str, object]:
        body: dict[str, object] = {"values": op.get("values", [])}
        response = (
            sheets.spreadsheets()
            .values()
            .update(
                spreadsheetId=str(op["spreadsheet_id"]),
                range=str(op["range_a1"]),
                valueInputOption="USER_ENTERED",
                body=body,
            )
            .execute()
        )
        return dict(response)

    def _create_spreadsheet(account_id: str, op: dict[str, object]) -> dict[str, object]:
        body: dict[str, object] = {"properties": {"title": str(op["title"])}}
        response = sheets.spreadsheets().create(body=body).execute()
        return dict(response)

    def _create_deck(account_id: str, op: dict[str, object]) -> dict[str, object]:
        body: dict[str, object] = {"title": str(op["title"])}
        response = slides.presentations().create(body=body).execute()
        return dict(response)

    handlers: dict[str, Callable[[str, dict[str, object]], dict[str, object]]] = {
        "write_range": _write_range,
        "create": _create_spreadsheet,
        "create_deck": _create_deck,
    }

    def mutate(
        customer_id: str, operations: list[dict[str, object]], validate_only: bool
    ) -> dict[str, object]:
        if validate_only:
            return {"validate_only": True, "preview": operations}
        results = []
        for op in operations:
            # spreadsheet + presentation creation share the "create" action; disambiguate by entity.
            action = str(op["action"])
            if action == "create" and op.get("entity") == "presentation":
                action = "create_deck"
            handler = handlers.get(action)
            if handler is None:
                raise ValueError(f"unsupported workspace mutate action: {op.get('action')!r}")
            results.append(handler(customer_id, op))
        return {"validate_only": False, "results": results}

    return mutate
