"""Live boundary — smoke-gated, not unit-tested.

Real Google Data Manager API glue: lazy factories building the destinations read callable (ReadFn)
and the first-party upload callable (MutateFn). Isolated at the untyped third-party boundary
(``googleapiclient.*`` is mypy-ignored; this module is coverage-omitted via the live gate).
Imports are local so importing this module stays cheap and credential-free.

Targets the **Data Manager API** (``datamanager`` v1), the SOTA first-party upload plane (the
Google Ads API upload path is blocked since 2026-06-15). The Python client is the generic
``google-api-python-client`` discovery client (``googleapiclient.discovery.build``); there is no
dedicated hand-written client package — Data Manager is consumed through the discovery document.
OAuth credentials are derived from the shared Google creds dict.

HASHING IS THE OPERATOR'S RESPONSIBILITY. The op dicts arriving here already carry SHA-256-hashed,
normalized identifiers and the Consent Mode v2 consent block; this module only translates op dicts
into request bodies — it never hashes.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

ReadFn = Callable[[str, dict[str, object]], list[dict[str, object]]]
MutateFn = Callable[[str, list[dict[str, object]], bool], dict[str, object]]

# Customer Match + conversion ingestion + destinations management.
_SCOPES = ["https://www.googleapis.com/auth/datamanager"]


def _oauth_credentials(creds: dict[str, object]) -> Any:
    from google.oauth2.credentials import Credentials

    return Credentials(
        token=None,
        refresh_token=str(creds["refresh_token"]),
        client_id=str(creds["client_id"]),
        client_secret=str(creds["client_secret"]),
        token_uri="https://oauth2.googleapis.com/token",
        scopes=_SCOPES,
    )


def _service(creds: dict[str, object], version: str) -> Any:
    from googleapiclient.discovery import build

    return build("datamanager", version, credentials=_oauth_credentials(creds))


def default_read_factory(creds: dict[str, object], version: str) -> ReadFn:
    """Build the Data Manager ReadFn dispatching destinations.list over the discovery client."""
    service = _service(creds, version)

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        if operation == "destinations.list":
            account = str(params["account_id"])
            response = service.destinations().list(parent=account).execute()
            destinations = response.get("destinations", [])
            return [dict(d) for d in destinations]
        raise ValueError(f"unsupported datamanager read operation: {operation!r}")

    return read


def default_mutate_factory(creds: dict[str, object], version: str) -> MutateFn:
    """Build the op-dispatching MutateFn over the Data Manager ingestion endpoints.

    ``validate_only`` short-circuits to a synthetic preview because the Data Manager ingestion
    endpoints do not expose a server-side validate-only flag; the guarded preview still surfaces
    the exact op dicts (entity/action/payload/consent) that would be applied before the confirm
    step. Identifiers in the op payloads are already SHA-256 hashed/normalized by the operator.
    """
    service = _service(creds, version)

    def _upload_members(op: dict[str, object]) -> dict[str, object]:
        body: dict[str, object] = {
            "audienceId": str(op["audience_id"]),
            "members": op["members"],
            "consent": op["consent"],
        }
        request = service.audienceMembers().ingest(destination=str(op["destination_id"]), body=body)
        result: dict[str, object] = request.execute()
        return result

    def _remove_members(op: dict[str, object]) -> dict[str, object]:
        body: dict[str, object] = {
            "audienceId": str(op["audience_id"]),
            "members": op["members"],
        }
        request = service.audienceMembers().remove(destination=str(op["destination_id"]), body=body)
        result: dict[str, object] = request.execute()
        return result

    def _upload_conversions(op: dict[str, object]) -> dict[str, object]:
        body: dict[str, object] = {
            "conversions": op["conversions"],
            "consent": op["consent"],
        }
        request = service.conversions().ingest(destination=str(op["destination_id"]), body=body)
        result: dict[str, object] = request.execute()
        return result

    handlers: dict[str, Callable[[dict[str, object]], dict[str, object]]] = {
        "audience_member:upload": _upload_members,
        "audience_member:remove": _remove_members,
        "conversion:upload": _upload_conversions,
    }

    def mutate(
        destination_id: str, operations: list[dict[str, object]], validate_only: bool
    ) -> dict[str, object]:
        if validate_only:
            return {"validate_only": True, "preview": operations}
        results: list[dict[str, object]] = []
        for op in operations:
            key = f"{op.get('entity')}:{op.get('action')}"
            handler = handlers.get(key)
            if handler is None:
                raise ValueError(f"unsupported datamanager mutate op: {key!r}")
            results.append(handler(op))
        return {"validate_only": False, "results": results}

    return mutate
