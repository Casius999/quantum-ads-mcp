"""Raw GAQL execution + shared helpers for the read connector."""

from __future__ import annotations

from ....core.auth.tenant import normalize_customer_id
from ....core.query.gaql_validator import GaqlError
from ....core.query.runner import StreamFn, run_report

# Date-range literals accepted by report/change-history wrappers (prevents injection in interpolation).
ALLOWED_DATE_RANGES: set[str] = {
    "TODAY",
    "YESTERDAY",
    "LAST_7_DAYS",
    "LAST_14_DAYS",
    "LAST_30_DAYS",
    "THIS_MONTH",
    "LAST_MONTH",
    "LAST_BUSINESS_WEEK",
}


def execute_query(customer_id: str, query: str, stream: StreamFn) -> dict[str, object]:
    """Normalize the customer id, validate+run the GAQL, and wrap rows or a structured error."""
    cid = normalize_customer_id(customer_id)
    try:
        rows = run_report(cid, query, stream=stream)
    except GaqlError as exc:
        return {"error": {"code": "GAQL_INVALID", "message": str(exc)}}
    return {"rows": rows, "row_count": len(rows)}


def run_gaql(*, customer_id: str, query: str, stream: StreamFn) -> dict[str, object]:
    """Tool: run an arbitrary GAQL query (read-only)."""
    return execute_query(customer_id, query, stream)
