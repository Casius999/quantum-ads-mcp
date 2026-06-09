"""SA360 read tools: backend-invoking runners wrapping the pure query builders.

The query-string + param builders are pure and live in :mod:`..queries` (unit-tested directly).
These thin wrappers invoke the injected ``ReadFn`` backend (operation ``"search"`` with
``{"customer_id", "query"}`` params, or ``"customers.listAccessible"``) and wrap the result in the
shared ``{"rows", "row_count"}`` envelope — matching the Google Ads / Search Console read
connectors. The report shortcuts validate ``date_range`` against the closed allow-list and return
a structured ``BAD_DATE_RANGE`` error rather than interpolating an unvetted token.
"""

from __future__ import annotations

from ..queries import (
    ALLOWED_DATE_RANGES,
    OP_LIST_ACCESSIBLE_CUSTOMERS,
    OP_SEARCH,
    build_ad_group_query,
    build_campaign_query,
    build_search_params,
)
from ..types import ReadFn


def _wrap(rows: list[dict[str, object]]) -> dict[str, object]:
    """Wrap rows in the shared read envelope."""
    return {"rows": rows, "row_count": len(rows)}


def _bad_date_range(date_range: str) -> dict[str, object]:
    return {
        "error": {"code": "BAD_DATE_RANGE", "message": f"unsupported date_range {date_range!r}"}
    }


def search(*, customer_id: str, query: str, read: ReadFn) -> dict[str, object]:
    """Tool: run an arbitrary read-only SA360 query (SA360 query language)."""
    return _wrap(read(OP_SEARCH, build_search_params(customer_id, query)))


def list_accessible_customers(*, read: ReadFn) -> dict[str, object]:
    """Tool: list the SA360 customers (login accounts) the authenticated user can access."""
    params: dict[str, object] = {}
    return _wrap(read(OP_LIST_ACCESSIBLE_CUSTOMERS, params))


def report_campaign(
    *, customer_id: str, date_range: str = "LAST_30_DAYS", read: ReadFn
) -> dict[str, object]:
    """Tool: campaign performance report (builds the query, then runs ``search``)."""
    if date_range not in ALLOWED_DATE_RANGES:
        return _bad_date_range(date_range)
    query = build_campaign_query(date_range)
    return _wrap(read(OP_SEARCH, build_search_params(customer_id, query)))


def report_ad_group(
    *, customer_id: str, date_range: str = "LAST_30_DAYS", read: ReadFn
) -> dict[str, object]:
    """Tool: ad-group performance report (builds the query, then runs ``search``)."""
    if date_range not in ALLOWED_DATE_RANGES:
        return _bad_date_range(date_range)
    query = build_ad_group_query(date_range)
    return _wrap(read(OP_SEARCH, build_search_params(customer_id, query)))
