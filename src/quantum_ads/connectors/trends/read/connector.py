"""Mount the read-only Google Trends tools onto the FastMCP app + register capabilities.

Read backend is keyed ``"trends.api"`` (a ``ReadFn``). When it is not wired the tools degrade
gracefully, returning a structured ``BACKEND_NOT_CONFIGURED`` error rather than raising.

Trends covers the **demand / seasonality** surface (interest over time, related queries, trending
now, interest by region), pairing the paid Google Ads connectors with the upstream demand signal
an agency uses for budget pacing, keyword expansion, and geo-targeting.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from fastmcp import FastMCP

from ....core.context import ServerContext
from ....core.mcp.register import add_tool
from ....core.registry.registry import Capability, ToolSpec
from ..types import ReadFn
from . import trends_tools as tools_mod

BACKEND_KEY = "trends.api"

_NOT_CONFIGURED: dict[str, object] = {
    "error": {"code": "BACKEND_NOT_CONFIGURED", "message": f"{BACKEND_KEY} not wired"}
}


def register_trends_read(app: FastMCP, ctx: ServerContext) -> None:
    def read_backend() -> ReadFn | None:
        backend = ctx.backend(BACKEND_KEY)
        if backend is None:
            return None
        return cast(ReadFn, backend)

    def trends_interest_over_time(
        keywords: list[str],
        timeframe: str = tools_mod.DEFAULT_TIMEFRAME,
        geo: str = "",
    ) -> dict[str, object]:
        read = read_backend()
        if read is None:
            return dict(_NOT_CONFIGURED)
        return tools_mod.interest_over_time(
            keywords=keywords, timeframe=timeframe, geo=geo, read=read
        )

    def trends_related_queries(keyword: str, geo: str = "") -> dict[str, object]:
        read = read_backend()
        if read is None:
            return dict(_NOT_CONFIGURED)
        return tools_mod.related_queries(keyword=keyword, geo=geo, read=read)

    def trends_trending_now(geo: str = tools_mod.DEFAULT_TRENDING_GEO) -> dict[str, object]:
        read = read_backend()
        if read is None:
            return dict(_NOT_CONFIGURED)
        return tools_mod.trending_now(geo=geo, read=read)

    def trends_interest_by_region(
        keyword: str, resolution: str = tools_mod.DEFAULT_RESOLUTION
    ) -> dict[str, object]:
        read = read_backend()
        if read is None:
            return dict(_NOT_CONFIGURED)
        return tools_mod.interest_by_region(keyword=keyword, resolution=resolution, read=read)

    tools: list[tuple[str, str, Callable[..., Any]]] = [
        (
            "trends.interest_over_time",
            "Relative search interest over time for a comparison set (demand / seasonality).",
            trends_interest_over_time,
        ),
        (
            "trends.related_queries",
            "Top + rising related search queries for a keyword (keyword expansion).",
            trends_related_queries,
        ),
        (
            "trends.trending_now",
            "Currently trending searches for a country (breakout demand).",
            trends_trending_now,
        ),
        (
            "trends.interest_by_region",
            "Geographic breakdown of interest in a keyword (geo-targeting).",
            trends_interest_by_region,
        ),
    ]
    for name, description, fn in tools:
        add_tool(app, name, description, fn)

    ctx.registry.register(
        Capability(
            connector="trends",
            domain="read",
            tools=[ToolSpec(name=name, summary=description) for name, description, _ in tools],
        )
    )
