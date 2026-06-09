"""GA4 Analytics Data API v1 read tools.

Pure request builders (``build_*_params``) construct the param dict handed to the injected
backend ReadFn; the thin ``run_*`` wrappers do the None-check + structured error envelope.
The backend ReadFn signature is ``(operation, params) -> rows`` where operation is one of
``"runReport"`` / ``"runRealtimeReport"``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

# (operation, params) -> rows.
ReadFn = Callable[[str, dict[str, object]], list[dict[str, object]]]

_BACKEND_NOT_CONFIGURED: dict[str, object] = {
    "error": {"code": "BACKEND_NOT_CONFIGURED", "message": "ga4.data not wired"}
}


def build_report_params(
    *,
    property_id: str,
    dimensions: list[str],
    metrics: list[str],
    start_date: str,
    end_date: str,
) -> dict[str, object]:
    """Build the runReport request params (property + dimensions/metrics + date range)."""
    params: dict[str, object] = {
        "property_id": property_id,
        "dimensions": list(dimensions),
        "metrics": list(metrics),
        "start_date": start_date,
        "end_date": end_date,
    }
    return params


def build_realtime_params(
    *,
    property_id: str,
    dimensions: list[str],
    metrics: list[str],
) -> dict[str, object]:
    """Build the runRealtimeReport request params (no date range in the realtime API)."""
    params: dict[str, object] = {
        "property_id": property_id,
        "dimensions": list(dimensions),
        "metrics": list(metrics),
    }
    return params


def run_report(
    *,
    property_id: str,
    dimensions: list[str],
    metrics: list[str],
    start_date: str,
    end_date: str,
    backend: object | None,
) -> dict[str, object]:
    """Tool: runReport over the Data API for a property + dimensions/metrics + date range."""
    if backend is None:
        return dict(_BACKEND_NOT_CONFIGURED)
    read = cast(ReadFn, backend)
    params = build_report_params(
        property_id=property_id,
        dimensions=dimensions,
        metrics=metrics,
        start_date=start_date,
        end_date=end_date,
    )
    rows = read("runReport", params)
    return {"rows": rows, "row_count": len(rows)}


def run_realtime(
    *,
    property_id: str,
    dimensions: list[str],
    metrics: list[str],
    backend: object | None,
) -> dict[str, object]:
    """Tool: runRealtimeReport over the Data API for a property + dimensions/metrics."""
    if backend is None:
        return dict(_BACKEND_NOT_CONFIGURED)
    read = cast(ReadFn, backend)
    params = build_realtime_params(property_id=property_id, dimensions=dimensions, metrics=metrics)
    rows = read("runRealtimeReport", params)
    return {"rows": rows, "row_count": len(rows)}
