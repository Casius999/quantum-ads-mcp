"""Mount the read-only Search Ads 360 tools onto the FastMCP app + register capabilities.

Read backend is keyed ``"sa360.api"`` (a ``ReadFn``). When it is not wired the tools degrade
gracefully, returning a structured ``BACKEND_NOT_CONFIGURED`` error rather than raising.

SA360 is the cross-engine search-management reporting plane (the new Search Ads 360 Reporting API
v0): ``sa360.search`` runs an arbitrary SA360 query, the report shortcuts pre-build campaign /
ad-group performance queries, and ``customers.list_accessible`` enumerates reachable accounts.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from fastmcp import FastMCP

from ....core.context import ServerContext
from ....core.mcp.register import add_tool
from ....core.registry.registry import Capability, ToolSpec
from ..types import ReadFn
from . import search_tools

BACKEND_KEY = "sa360.api"

_NOT_CONFIGURED: dict[str, object] = {
    "error": {"code": "BACKEND_NOT_CONFIGURED", "message": f"{BACKEND_KEY} not wired"}
}


def register_sa360_read(app: FastMCP, ctx: ServerContext) -> None:
    def read_backend() -> ReadFn | None:
        backend = ctx.backend(BACKEND_KEY)
        if backend is None:
            return None
        return cast(ReadFn, backend)

    def sa360_search(customer_id: str, query: str) -> dict[str, object]:
        read = read_backend()
        if read is None:
            return dict(_NOT_CONFIGURED)
        return search_tools.search(customer_id=customer_id, query=query, read=read)

    def sa360_customers_list_accessible() -> dict[str, object]:
        read = read_backend()
        if read is None:
            return dict(_NOT_CONFIGURED)
        return search_tools.list_accessible_customers(read=read)

    def sa360_report_campaign(
        customer_id: str, date_range: str = "LAST_30_DAYS"
    ) -> dict[str, object]:
        read = read_backend()
        if read is None:
            return dict(_NOT_CONFIGURED)
        return search_tools.report_campaign(
            customer_id=customer_id, date_range=date_range, read=read
        )

    def sa360_report_ad_group(
        customer_id: str, date_range: str = "LAST_30_DAYS"
    ) -> dict[str, object]:
        read = read_backend()
        if read is None:
            return dict(_NOT_CONFIGURED)
        return search_tools.report_ad_group(
            customer_id=customer_id, date_range=date_range, read=read
        )

    tools: list[tuple[str, str, Callable[..., Any]]] = [
        (
            "sa360.search",
            "Run an arbitrary read-only SA360 query (SA360 query language: SELECT ... FROM ...).",
            sa360_search,
        ),
        (
            "sa360.customers.list_accessible",
            "List SA360 customers (accounts) the authenticated user can access.",
            sa360_customers_list_accessible,
        ),
        (
            "sa360.report.campaign",
            "Campaign performance report (SA360).",
            sa360_report_campaign,
        ),
        (
            "sa360.report.ad_group",
            "Ad-group performance report (SA360).",
            sa360_report_ad_group,
        ),
    ]
    for name, description, fn in tools:
        add_tool(app, name, description, fn)

    ctx.registry.register(
        Capability(
            connector="sa360",
            domain="read",
            tools=[ToolSpec(name=name, summary=description) for name, description, _ in tools],
        )
    )
