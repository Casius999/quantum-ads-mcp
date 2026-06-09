"""Real Google Tag Manager (API v2) SDK glue: read + mutate factories.

Live boundary — smoke-gated, not unit-tested.

Isolated at the untyped third-party boundary (``googleapiclient.*`` / ``google.oauth2.*``
are in the mypy ``ignore_missing_imports`` list, so ``build(...)`` yields ``Any`` and the
dynamic resource objects are threaded as ``Any`` here). Imports are local so importing this
module stays cheap and credential-free.

Backends produced here match the connector contracts:
- ``ReadFn``  = (operation, params) -> rows   (operation names the GTM resource;
  params carry the parent path, e.g. {"parent": "accounts/123/containers/456"}).
- ``MutateFn`` = (account_path, operations, validate_only) -> result   where
  account_path is the parent path and each op dict names the resource + action.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

ReadFn = Callable[[str, dict[str, object]], list[dict[str, object]]]
MutateFn = Callable[[str, list[dict[str, object]], bool], dict[str, object]]

# Reads ride the read-only scope; edit/publish rides the edit scope. Splitting them lets a
# read-only token drive the read plane without an invalid_scope refresh failure.
TAGMANAGER_READ_SCOPE = "https://www.googleapis.com/auth/tagmanager.readonly"
TAGMANAGER_EDIT_SCOPE = "https://www.googleapis.com/auth/tagmanager.edit.containers"


def _build_service(creds: dict[str, object], scopes: list[str]) -> Any:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    quota = creds.get("quota_project_id")
    credentials = Credentials(
        token=None,
        refresh_token=str(creds.get("refresh_token")),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=str(creds.get("client_id")),
        client_secret=str(creds.get("client_secret")),
        scopes=scopes,
        quota_project_id=str(quota) if quota else None,
    )
    return build("tagmanager", "v2", credentials=credentials, cache_discovery=False)


def _rows(response: dict[str, object], key: str) -> list[dict[str, object]]:
    items = response.get(key, [])
    return [dict(item) for item in items]  # type: ignore[arg-type]


def default_read_factory(creds: dict[str, object], version: str) -> ReadFn:
    accounts: Any = _build_service(creds, [TAGMANAGER_READ_SCOPE]).accounts()

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        parent = str(params.get("parent", ""))
        if operation == "list_accounts":
            return _rows(accounts.list().execute(), "account")
        if operation == "list_containers":
            return _rows(accounts.containers().list(parent=parent).execute(), "container")
        if operation == "list_workspaces":
            workspaces = accounts.containers().workspaces()
            return _rows(workspaces.list(parent=parent).execute(), "workspace")
        if operation == "list_tags":
            tags = accounts.containers().workspaces().tags()
            return _rows(tags.list(parent=parent).execute(), "tag")
        if operation == "list_triggers":
            triggers = accounts.containers().workspaces().triggers()
            return _rows(triggers.list(parent=parent).execute(), "trigger")
        if operation == "list_variables":
            variables = accounts.containers().workspaces().variables()
            return _rows(variables.list(parent=parent).execute(), "variable")
        if operation == "list_versions":
            headers = accounts.containers().version_headers()
            return _rows(headers.list(parent=parent).execute(), "containerVersionHeader")
        raise ValueError(f"unsupported gtm read operation: {operation!r}")

    return read


def default_mutate_factory(creds: dict[str, object], version: str) -> MutateFn:
    accounts: Any = _build_service(creds, [TAGMANAGER_EDIT_SCOPE]).accounts()

    def _create_tag(parent: str, op: dict[str, object]) -> dict[str, object]:
        body: dict[str, object] = {"name": op["tag_name"], "type": op["tag_type"]}
        if op.get("parameter"):
            body["parameter"] = op["parameter"]
        tags = accounts.containers().workspaces().tags()
        return dict(tags.create(parent=parent, body=body).execute())

    def _update_tag(parent: str, op: dict[str, object]) -> dict[str, object]:
        tags = accounts.containers().workspaces().tags()
        request = tags.update(path=str(op["path"]), body=dict(op.get("fields", {})))
        return dict(request.execute())

    def _create_version(parent: str, op: dict[str, object]) -> dict[str, object]:
        body: dict[str, object] = {"name": op.get("name")}
        workspaces = accounts.containers().workspaces()
        return dict(workspaces.create_version(path=parent, body=body).execute())

    def _publish_version(parent: str, op: dict[str, object]) -> dict[str, object]:
        request = accounts.containers().versions().publish(path=str(op["path"]))
        return dict(request.execute())

    handlers: dict[str, Callable[[str, dict[str, object]], dict[str, object]]] = {
        "create_tag": _create_tag,
        "update_tag": _update_tag,
        "create_version": _create_version,
        "publish_version": _publish_version,
    }

    def mutate(
        account_path: str, operations: list[dict[str, object]], validate_only: bool
    ) -> dict[str, object]:
        if validate_only:
            # Tag Manager API v2 has no native validate_only; preview without applying.
            return {"validate_only": True, "operations": operations, "parent": account_path}
        results: list[dict[str, object]] = []
        for op in operations:
            handler = handlers.get(str(op.get("action")))
            if handler is None:
                raise ValueError(f"unsupported gtm mutate action: {op.get('action')!r}")
            results.append(handler(account_path, op))
        return {"validate_only": False, "results": results}

    return mutate
