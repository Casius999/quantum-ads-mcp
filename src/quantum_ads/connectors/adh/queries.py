"""Pure builders for Ads Data Hub (ADH) read params (unit-tested directly).

ADH (the Ads Data Hub API, ``adsdatahub`` v1, the privacy-safe aggregated-measurement plane) is
addressed through a small set of operations. These builders shape the ``params`` dict handed to
the generic ``ReadFn`` backend for each operation. They never touch the network — the injected
``ReadFn`` backend owns the live ``adsdatahub`` calls.

The operations:

* ``customers.list`` — enumerate ADH customers (accounts) reachable by the caller (no params).
* ``queries.list`` — list the stored analysis queries owned by a customer.
* ``query.start`` — start (run) a stored analysis query over a ``[start_date, end_date]`` window;
  the backend returns a long-running operation / job reference, not result rows (ADH runs are
  asynchronous and privacy-checked before any output is produced).
* ``jobs.get`` — poll a previously started operation for status + the result table reference.

ADH's own privacy layer (aggregation thresholds + difference checks) runs server-side; these
builders neither weaken nor inspect it.
"""

from __future__ import annotations

# Operation names passed as the first ReadFn argument.
OP_CUSTOMERS_LIST = "customers.list"
OP_QUERIES_LIST = "queries.list"
OP_QUERY_START = "query.start"
OP_JOBS_GET = "jobs.get"


def build_list_customers_params() -> dict[str, object]:
    """Pure: params for ``customers.list`` (enumerate reachable ADH accounts; no args)."""
    params: dict[str, object] = {}
    return params


def build_list_queries_params(customer_id: str) -> dict[str, object]:
    """Pure: params for ``queries.list`` (stored analysis queries owned by a customer)."""
    params: dict[str, object] = {"customer_id": customer_id}
    return params


def build_start_query_params(
    customer_id: str, query_id: str, start_date: str, end_date: str
) -> dict[str, object]:
    """Pure: params to start a stored analysis query over a ``[start_date, end_date]`` window.

    The backend launches an asynchronous, privacy-checked run and returns an operation/job
    reference; no result rows come back here (poll ``jobs.get`` for status + the result ref).
    """
    params: dict[str, object] = {
        "customer_id": customer_id,
        "query_id": query_id,
        "start_date": start_date,
        "end_date": end_date,
    }
    return params


def build_get_job_params(operation_name: str) -> dict[str, object]:
    """Pure: params for ``jobs.get`` (poll a started run by its operation name)."""
    params: dict[str, object] = {"operation_name": operation_name}
    return params
