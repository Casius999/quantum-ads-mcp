"""Real Campaign Manager 360 (dfareporting API v4) SDK glue: read + mutate factories.

Live boundary — smoke-gated, not unit-tested.

Isolated at the untyped third-party boundary (``googleapiclient.*`` / ``google.oauth2.*`` are in
the mypy ``ignore_missing_imports`` list, so ``build(...)`` yields ``Any`` and the dynamic resource
objects are threaded as ``Any`` here). Imports are local so importing this module stays cheap and
credential-free.

Backends produced here match the connector contracts:
- ``ReadFn``  = (operation, params) -> rows   (operation names the dfareporting resource; params
  carry the profile id, e.g. {"profile_id": "123"}, plus {"report_id": "..."} for ``reports.run``).
  ``userProfiles.list`` takes no profile id (it enumerates the profiles themselves).
- ``MutateFn`` = (profile_id, operations, validate_only) -> result   where profile_id is the user
  profile every placement patch / report insert is scoped to, and each op dict names the action.
  The dfareporting API has no native validate_only, so the preview pass returns the planned
  operations without applying.

Python package: ``google-api-python-client`` (plus ``google-auth``).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

ReadFn = Callable[[str, dict[str, object]], list[dict[str, object]]]
MutateFn = Callable[[str, list[dict[str, object]], bool], dict[str, object]]

# OAuth scope for full Campaign Manager 360 trafficking (read + edit placements / reports).
DFAREPORTING_SCOPE = "https://www.googleapis.com/auth/dfatrafficking"


def _build_service(creds: dict[str, object], version: str) -> Any:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    quota = creds.get("quota_project_id")
    credentials = Credentials(
        token=None,
        refresh_token=str(creds.get("refresh_token")),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=str(creds.get("client_id")),
        client_secret=str(creds.get("client_secret")),
        scopes=[DFAREPORTING_SCOPE],
        quota_project_id=str(quota) if quota else None,
    )
    return build("dfareporting", version or "v4", credentials=credentials, cache_discovery=False)


def _rows(response: dict[str, object], key: str) -> list[dict[str, object]]:
    items = response.get(key, [])
    return [dict(item) for item in items]  # type: ignore[arg-type]


def default_read_factory(creds: dict[str, object], version: str) -> ReadFn:
    service: Any = _build_service(creds, version)

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        if operation == "userProfiles.list":
            response = service.userProfiles().list().execute()
            return _rows(response, "items")
        profile_id = str(params.get("profile_id", ""))
        if operation == "campaigns.list":
            response = service.campaigns().list(profileId=profile_id).execute()
            return _rows(response, "campaigns")
        if operation == "placements.list":
            response = service.placements().list(profileId=profile_id).execute()
            return _rows(response, "placements")
        if operation == "reports.list":
            response = service.reports().list(profileId=profile_id).execute()
            return _rows(response, "items")
        if operation == "reports.run":
            report_id = str(params.get("report_id", ""))
            response = service.reports().run(profileId=profile_id, reportId=report_id).execute()
            return [dict(response)]
        if operation == "floodlightActivities.list":
            floodlight = service.floodlightActivities()
            response = floodlight.list(profileId=profile_id).execute()
            return _rows(response, "floodlightActivities")
        raise ValueError(f"unsupported cm360 read operation: {operation!r}")

    return read


def default_mutate_factory(creds: dict[str, object], version: str) -> MutateFn:
    service: Any = _build_service(creds, version)

    def _update_placement(profile_id: str, op: dict[str, object]) -> dict[str, object]:
        fields = dict(op.get("fields", {}))
        body: dict[str, object] = {"id": str(op["placement_id"]), **fields}
        request = service.placements().patch(
            profileId=profile_id,
            id=str(op["placement_id"]),
            body=body,
        )
        return dict(request.execute())

    def _insert_report(profile_id: str, op: dict[str, object]) -> dict[str, object]:
        body = dict(op.get("report", {}))
        request = service.reports().insert(profileId=profile_id, body=body)
        return dict(request.execute())

    handlers: dict[str, Callable[[str, dict[str, object]], dict[str, object]]] = {
        "update_placement": _update_placement,
        "insert_report": _insert_report,
    }

    def mutate(
        profile_id: str, operations: list[dict[str, object]], validate_only: bool
    ) -> dict[str, object]:
        if validate_only:
            # dfareporting API has no native validate_only; preview without applying.
            return {
                "validate_only": True,
                "operations": operations,
                "profile_id": profile_id,
            }
        results: list[dict[str, object]] = []
        for op in operations:
            handler = handlers.get(str(op.get("action")))
            if handler is None:
                raise ValueError(f"unsupported cm360 mutate action: {op.get('action')!r}")
            results.append(handler(profile_id, op))
        return {"validate_only": False, "results": results}

    return mutate
