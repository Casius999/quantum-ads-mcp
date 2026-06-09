"""GA4 Analytics Admin API v1 read tools (list properties / data streams / key events).

Pure request builders (``build_*_params``) construct the param dict handed to the injected
backend ReadFn; thin ``list_*`` wrappers do the None-check + structured error envelope.
The backend ReadFn signature is ``(operation, params) -> rows`` where operation is one of
``"listProperties"`` / ``"listDataStreams"`` / ``"listKeyEvents"``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

# (operation, params) -> rows.
ReadFn = Callable[[str, dict[str, object]], list[dict[str, object]]]

_BACKEND_NOT_CONFIGURED: dict[str, object] = {
    "error": {"code": "BACKEND_NOT_CONFIGURED", "message": "ga4.admin not wired"}
}


def build_list_properties_params(account_id: str) -> dict[str, object]:
    """Build params to list GA4 properties under an Admin account (filter accounts/<id>)."""
    params: dict[str, object] = {"account_id": account_id}
    return params


def build_list_data_streams_params(property_id: str) -> dict[str, object]:
    """Build params to list data streams under a GA4 property."""
    params: dict[str, object] = {"property_id": property_id}
    return params


def build_list_key_events_params(property_id: str) -> dict[str, object]:
    """Build params to list key events (conversions) under a GA4 property."""
    params: dict[str, object] = {"property_id": property_id}
    return params


def list_properties(*, account_id: str, backend: object | None) -> dict[str, object]:
    """Tool: list properties under an Admin account."""
    if backend is None:
        return dict(_BACKEND_NOT_CONFIGURED)
    read = cast(ReadFn, backend)
    rows = read("listProperties", build_list_properties_params(account_id))
    return {"rows": rows, "row_count": len(rows)}


def list_data_streams(*, property_id: str, backend: object | None) -> dict[str, object]:
    """Tool: list data streams under a property."""
    if backend is None:
        return dict(_BACKEND_NOT_CONFIGURED)
    read = cast(ReadFn, backend)
    rows = read("listDataStreams", build_list_data_streams_params(property_id))
    return {"rows": rows, "row_count": len(rows)}


def list_key_events(*, property_id: str, backend: object | None) -> dict[str, object]:
    """Tool: list key events (conversions) under a property."""
    if backend is None:
        return dict(_BACKEND_NOT_CONFIGURED)
    read = cast(ReadFn, backend)
    rows = read("listKeyEvents", build_list_key_events_params(property_id))
    return {"rows": rows, "row_count": len(rows)}
