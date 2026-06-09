"""ADH read tools: backend-invoking runners wrapping the pure param builders.

The param builders are pure and live in :mod:`..queries` (unit-tested directly). These thin
wrappers invoke the injected ``ReadFn`` backend with the right operation name + params and wrap the
result in the shared ``{"rows", "row_count"}`` envelope — matching the SA360 / Search Console read
connectors.

ADH query runs are asynchronous and privacy-checked server-side: ``start_query`` does not return
result rows but the launched operation/job reference (poll ``get_job`` for status + the result
table reference), and every eventual result is aggregated + privacy-filtered by ADH, never
row-level. These wrappers do not and cannot bypass that privacy layer.
"""

from __future__ import annotations

from ..queries import (
    OP_CUSTOMERS_LIST,
    OP_JOBS_GET,
    OP_QUERIES_LIST,
    OP_QUERY_START,
    build_get_job_params,
    build_list_customers_params,
    build_list_queries_params,
    build_start_query_params,
)
from ..types import ReadFn


def _wrap(rows: list[dict[str, object]]) -> dict[str, object]:
    """Wrap rows in the shared read envelope."""
    return {"rows": rows, "row_count": len(rows)}


def list_customers(*, read: ReadFn) -> dict[str, object]:
    """Tool: list the ADH customers (accounts) the authenticated user can access."""
    return _wrap(read(OP_CUSTOMERS_LIST, build_list_customers_params()))


def list_queries(*, customer_id: str, read: ReadFn) -> dict[str, object]:
    """Tool: list the stored analysis queries owned by an ADH customer."""
    return _wrap(read(OP_QUERIES_LIST, build_list_queries_params(customer_id)))


def start_query(
    *, customer_id: str, query_id: str, start_date: str, end_date: str, read: ReadFn
) -> dict[str, object]:
    """Tool: start a stored analysis query over ``[start_date, end_date]``.

    Returns the launched operation/job reference (asynchronous, privacy-checked run) wrapped in the
    shared envelope; no result rows are produced here. Poll :func:`get_job` for status + the result
    table reference.
    """
    params = build_start_query_params(customer_id, query_id, start_date, end_date)
    return _wrap(read(OP_QUERY_START, params))


def get_job(*, operation_name: str, read: ReadFn) -> dict[str, object]:
    """Tool: poll a started analysis-query run by its operation name (status + result ref)."""
    return _wrap(read(OP_JOBS_GET, build_get_job_params(operation_name)))
