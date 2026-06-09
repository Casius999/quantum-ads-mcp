"""Mount the read-only Ads Data Hub (ADH) tools onto the FastMCP app + register capabilities.

Read backend is keyed ``"adh.api"`` (a ``ReadFn``). When it is not wired the tools degrade
gracefully, returning a structured ``BACKEND_NOT_CONFIGURED`` error rather than raising.

ADH is the privacy-safe aggregated-measurement plane (Ads Data Hub API v1): ``adh.customers.list``
enumerates reachable accounts, ``adh.queries.list`` lists a customer's stored analysis queries,
``adh.query.start`` launches a stored analysis query over a date range (returning an operation/job
reference), and ``adh.jobs.get`` polls that operation. ADH enforces privacy checks (aggregation
thresholds + difference checks) server-side; these tools submit/poll and never bypass that layer.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from fastmcp import FastMCP

from ....core.context import ServerContext
from ....core.mcp.register import add_tool
from ....core.registry.registry import Capability, ToolSpec
from ..types import ReadFn
from . import query_tools

BACKEND_KEY = "adh.api"

_NOT_CONFIGURED: dict[str, object] = {
    "error": {"code": "BACKEND_NOT_CONFIGURED", "message": f"{BACKEND_KEY} not wired"}
}


def register_adh_read(app: FastMCP, ctx: ServerContext) -> None:
    def read_backend() -> ReadFn | None:
        backend = ctx.backend(BACKEND_KEY)
        if backend is None:
            return None
        return cast(ReadFn, backend)

    def adh_customers_list() -> dict[str, object]:
        read = read_backend()
        if read is None:
            return dict(_NOT_CONFIGURED)
        return query_tools.list_customers(read=read)

    def adh_queries_list(customer_id: str) -> dict[str, object]:
        read = read_backend()
        if read is None:
            return dict(_NOT_CONFIGURED)
        return query_tools.list_queries(customer_id=customer_id, read=read)

    def adh_query_start(
        customer_id: str, query_id: str, start_date: str, end_date: str
    ) -> dict[str, object]:
        read = read_backend()
        if read is None:
            return dict(_NOT_CONFIGURED)
        return query_tools.start_query(
            customer_id=customer_id,
            query_id=query_id,
            start_date=start_date,
            end_date=end_date,
            read=read,
        )

    def adh_jobs_get(operation_name: str) -> dict[str, object]:
        read = read_backend()
        if read is None:
            return dict(_NOT_CONFIGURED)
        return query_tools.get_job(operation_name=operation_name, read=read)

    tools: list[tuple[str, str, Callable[..., Any]]] = [
        (
            "adh.customers.list",
            "List Ads Data Hub customers (accounts) the authenticated user can access.",
            adh_customers_list,
        ),
        (
            "adh.queries.list",
            "List the stored analysis queries owned by an ADH customer.",
            adh_queries_list,
        ),
        (
            "adh.query.start",
            "Start a stored ADH analysis query over a date range; returns an operation/job ref "
            "(async, privacy-checked run — poll adh.jobs.get for the result).",
            adh_query_start,
        ),
        (
            "adh.jobs.get",
            "Poll a started ADH analysis-query run by operation name (status + result reference).",
            adh_jobs_get,
        ),
    ]
    for name, description, fn in tools:
        add_tool(app, name, description, fn)

    ctx.registry.register(
        Capability(
            connector="adh",
            domain="read",
            tools=[ToolSpec(name=name, summary=description) for name, description, _ in tools],
        )
    )
