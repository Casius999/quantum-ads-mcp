"""Generic Google API execution through ``google-api-python-client`` (live boundary).

Untyped third-party boundary (mypy-ignored, coverage-omitted, smoke-gated). Discovery documents
come from the copies bundled with the client library (offline, the exact contract the client
runs), falling back to Google's public discovery endpoints for APIs too new to be bundled.

- ``read_factory``  -> ReadFn: ``discovery`` returns the document, ``execute`` runs one call.
- ``mutate_factory`` -> MutateFn over ``"api/version"`` targets: validate_only uses the API's own
  ``validateOnly`` when it has one; commits read the before-state and record inverse calls.
"""

from __future__ import annotations

import json
import urllib.request
from collections.abc import Callable
from typing import Any

from .discovery import Method, find_method, scope_gap, sibling
from .rollback import before_state_call, inverse_operations

ReadFn = Callable[[str, dict[str, object]], list[dict[str, object]]]
MutateFn = Callable[[str, list[dict[str, object]], bool], dict[str, object]]
_DOCS: dict[tuple[str, str], dict[str, Any]] = {}


def load_document(api: str, version: str) -> dict[str, Any]:
    key = (api, version)
    if key in _DOCS:
        return _DOCS[key]
    from googleapiclient.discovery_cache import get_static_doc

    text = get_static_doc(api, version)
    if text is None:
        for url in (
            f"https://{api}.googleapis.com/$discovery/rest?version={version}",
            f"https://www.googleapis.com/discovery/v1/apis/{api}/{version}/rest",
        ):
            try:
                with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310
                    text = response.read().decode()
                break
            except Exception:  # noqa: BLE001, S112 - try the next discovery location
                continue
    if text is None:
        raise ValueError(f"no discovery document for {api} {version}")
    _DOCS[key] = json.loads(text)
    return _DOCS[key]


def _credentials(creds: dict[str, object]) -> Any:
    from google.oauth2.credentials import Credentials

    quota = creds.get("quota_project_id")
    # No explicit scopes: the refresh token's own grant decides what each API accepts.
    return Credentials(
        token=creds.get("access_token"),
        refresh_token=creds.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=str(creds.get("client_id")),
        client_secret=str(creds.get("client_secret")),
        quota_project_id=str(quota) if quota else None,
    )


class _Runner:
    def __init__(self, creds: dict[str, object]) -> None:
        self._credentials = _credentials(creds)
        self._services: dict[tuple[str, str], Any] = {}
        self._granted: set[str] | None = None

    def granted(self) -> set[str]:
        """Scopes the refresh token actually holds (tokeninfo), fetched once."""
        if self._granted is None:
            from google.auth.transport.requests import Request

            self._credentials.refresh(Request())
            url = f"https://oauth2.googleapis.com/tokeninfo?access_token={self._credentials.token}"
            with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310
                self._granted = set(json.loads(response.read()).get("scope", "").split())
        return self._granted

    def service(self, api: str, version: str) -> Any:
        key = (api, version)
        if key not in self._services:
            from googleapiclient.discovery import build_from_document

            self._services[key] = build_from_document(
                load_document(api, version), credentials=self._credentials
            )
        return self._services[key]

    def call(
        self, api: str, version: str, method: Method, params: dict[str, object], body: object
    ) -> dict[str, object]:
        from googleapiclient.discovery import key2param

        node = self.service(api, version)
        *resources, name = method.id.split(".")[1:]
        for resource in resources:
            node = getattr(node, resource)()
        kwargs = {key2param(k): v for k, v in params.items()}
        if body is not None:
            kwargs["body"] = body
        response = getattr(node, key2param(name))(**kwargs).execute()
        return dict(response) if isinstance(response, dict) else {"response": response}


def read_factory(creds: dict[str, object], version: str) -> ReadFn:
    runner = _Runner(creds)

    def read(op: str, params: dict[str, object]) -> list[dict[str, object]]:
        api, api_version = str(params["api"]), str(params["version"])
        if op == "discovery":
            return [load_document(api, api_version)]
        if op == "execute":
            method = find_method(load_document(api, api_version), str(params["method"]))
            call_params = dict(params.get("params") or {})  # type: ignore[call-overload]
            return [runner.call(api, api_version, method, call_params, params.get("body"))]
        raise ValueError(f"unsupported google.api operation: {op!r}")

    return read


def mutate_factory(creds: dict[str, object], version: str) -> MutateFn:
    runner = _Runner(creds)

    def mutate(
        target: str, operations: list[dict[str, object]], validate_only: bool
    ) -> dict[str, object]:
        api, api_version = target.split("/", 1)
        doc = load_document(api, api_version)
        results: list[dict[str, object]] = []
        inverse: list[dict[str, object]] = []
        for op in operations:
            method = find_method(doc, str(op["method"]))
            params = dict(op.get("params") or {})  # type: ignore[call-overload]
            body = op.get("body")
            if validate_only:
                gap = scope_gap(method, runner.granted())
                if gap:
                    raise PermissionError(
                        f"the token holds no scope that authorizes {method.id}; needs one of {gap}"
                    )
                undo = sibling(doc, method, "delete") or sibling(doc, method, "archive")
                if undo is not None and method.name in ("create", "insert"):
                    undo_gap = scope_gap(undo, runner.granted())
                    if undo_gap:
                        results.append({"method": method.id, "rollback_unavailable": undo_gap})
                if method.supports_validate_only:
                    results.append(
                        runner.call(
                            api, api_version, method, {**params, "validateOnly": True}, body
                        )
                    )
                else:
                    results.append({"method": method.id, "validated": "discovery contract"})
                continue
            before = None
            reader = before_state_call(doc, method, params)
            if reader is not None:
                before = runner.call(api, api_version, reader[0], reader[1], None)
            response = runner.call(api, api_version, method, params, body)
            results.append(response)
            inverse = (
                inverse_operations(doc, api, api_version, method, params, response, before, body)
                + inverse
            )
        out: dict[str, object] = {"results": results}
        if inverse:
            out["inverse_operations"] = inverse
        return out

    return mutate
