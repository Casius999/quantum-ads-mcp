"""Reversibility for generic Google API writes, derived from the Discovery document.

- update (PATCH / PUT / ``update``): read the resource first with the sibling ``get`` and record
  a call that writes the previous values back (restricted to ``updateMask`` when one is sent);
- create (``create`` / ``insert``): record the sibling ``delete`` (or ``archive``) for the new resource, addressed
  by the identifier the API response returns (``name``, ``path``, ``id``...);
- delete and anything else: irreversible, nothing recorded.
Pure functions over the document and the call; the SDK layer performs the reads and writes.
"""

from __future__ import annotations

from typing import Any

from .discovery import Method, sibling

_UPDATE_NAMES = frozenset({"patch", "update"})
_CREATE_NAMES = frozenset({"create", "insert"})


def before_state_call(
    doc: dict[str, Any], method: Method, params: dict[str, object]
) -> tuple[Method, dict[str, object]] | None:
    """The ``get`` call that captures the resource before an update, if the API offers one."""
    if method.name not in _UPDATE_NAMES:
        return None
    getter = sibling(doc, method, "get")
    if getter is None or any(p not in params for p in getter.required):
        return None
    return getter, {p: params[p] for p in getter.required}


def _mask_fields(params: dict[str, object]) -> list[str] | None:
    mask = params.get("updateMask") or params.get("update_mask")
    if not mask:
        return None
    paths = mask if isinstance(mask, list) else str(mask).split(",")
    return sorted({str(p).strip().split(".")[0] for p in paths if str(p).strip()})


def inverse_of_update(
    api: str,
    version: str,
    method: Method,
    params: dict[str, object],
    before: dict[str, object],
    body: object = None,
) -> dict[str, object]:
    """A call restoring the previous values of exactly the fields this update touches.

    The touched fields come from ``updateMask``, else from the update's own body; only with
    neither is the whole previous state written back.
    """
    fields = _mask_fields(params)
    if fields is None and isinstance(body, dict) and body:
        fields = sorted(body)
    restored = dict(before) if fields is None else {f: before[f] for f in fields if f in before}
    return {
        "api": api,
        "version": version,
        "method": method.id,
        "params": dict(params),
        "body": restored,
    }


def inverse_of_create(
    doc: dict[str, Any],
    api: str,
    version: str,
    method: Method,
    params: dict[str, object],
    response: dict[str, object],
) -> dict[str, object] | None:
    """The ``delete`` of what this create made, when the response identifies it."""
    if method.name not in _CREATE_NAMES:
        return None
    # GA4 Admin and others retire resources with ``archive`` instead of ``delete``.
    deleter = sibling(doc, method, "delete") or sibling(doc, method, "archive")
    if deleter is None:
        return None
    resolved: dict[str, object] = {}
    for param in deleter.required:
        # The response identifies the new resource (name / path / id / lineItemId...);
        # parent identifiers come from the create call's own parameters.
        if response.get(param) not in (None, ""):
            resolved[param] = response[param]
        elif param in params:
            resolved[param] = params[param]
        elif param.endswith("Id") and response.get("id"):
            resolved[param] = response["id"]  # e.g. drive.files.delete(fileId) <- {"id": ...}
        else:
            return None
    body: dict[str, object] | None = {} if deleter.request_ref else None
    return {"api": api, "version": version, "method": deleter.id, "params": resolved, "body": body}


def inverse_operations(
    doc: dict[str, Any],
    api: str,
    version: str,
    method: Method,
    params: dict[str, object],
    response: dict[str, object],
    before: dict[str, object] | None,
    body: object = None,
) -> list[dict[str, object]]:
    if before is not None:
        return [inverse_of_update(api, version, method, params, before, body)]
    created = inverse_of_create(doc, api, version, method, params, response)
    return [created] if created is not None else []
