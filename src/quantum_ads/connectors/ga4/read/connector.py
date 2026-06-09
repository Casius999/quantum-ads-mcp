"""Mount the read-only GA4 tools onto the FastMCP app + register their capabilities.

Two backends are read lazily per call via ``ctx.backend(...)`` so the connector degrades
gracefully (structured BACKEND_NOT_CONFIGURED error) when a backend is not wired:
  - ``ga4.data``  -> Analytics Data API ReadFn  (runReport / runRealtimeReport)
  - ``ga4.admin`` -> Analytics Admin API ReadFn (listProperties / listDataStreams / listKeyEvents)
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastmcp import FastMCP

from ....core.context import ServerContext
from ....core.mcp.register import add_tool
from ....core.registry.registry import Capability, ToolSpec
from . import admin_tools, data_tools


def register_ga4_read(app: FastMCP, ctx: ServerContext) -> None:
    def ga4_report(
        property_id: str,
        dimensions: list[str],
        metrics: list[str],
        start_date: str,
        end_date: str,
    ) -> dict[str, object]:
        return data_tools.run_report(
            property_id=property_id,
            dimensions=dimensions,
            metrics=metrics,
            start_date=start_date,
            end_date=end_date,
            backend=ctx.backend("ga4.data"),
        )

    def ga4_realtime(
        property_id: str, dimensions: list[str], metrics: list[str]
    ) -> dict[str, object]:
        return data_tools.run_realtime(
            property_id=property_id,
            dimensions=dimensions,
            metrics=metrics,
            backend=ctx.backend("ga4.data"),
        )

    def ga4_admin_list_properties(account_id: str) -> dict[str, object]:
        return admin_tools.list_properties(account_id=account_id, backend=ctx.backend("ga4.admin"))

    def ga4_admin_list_data_streams(property_id: str) -> dict[str, object]:
        return admin_tools.list_data_streams(
            property_id=property_id, backend=ctx.backend("ga4.admin")
        )

    def ga4_admin_list_key_events(property_id: str) -> dict[str, object]:
        return admin_tools.list_key_events(
            property_id=property_id, backend=ctx.backend("ga4.admin")
        )

    tools: list[tuple[str, str, Callable[..., Any]]] = [
        ("ga4.report", "GA4 Data API report (runReport over a date range).", ga4_report),
        ("ga4.realtime", "GA4 Data API realtime report (runRealtimeReport).", ga4_realtime),
        (
            "ga4.admin.list_properties",
            "List GA4 properties under an Admin account.",
            ga4_admin_list_properties,
        ),
        (
            "ga4.admin.list_data_streams",
            "List data streams under a GA4 property.",
            ga4_admin_list_data_streams,
        ),
        (
            "ga4.admin.list_key_events",
            "List key events (conversions) under a GA4 property.",
            ga4_admin_list_key_events,
        ),
    ]
    for name, description, fn in tools:
        add_tool(app, name, description, fn)

    ctx.registry.register(
        Capability(
            connector="ga4",
            domain="read",
            tools=[ToolSpec(name=name, summary=description) for name, description, _ in tools],
        )
    )
