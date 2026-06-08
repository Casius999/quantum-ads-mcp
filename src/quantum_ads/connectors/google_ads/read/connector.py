"""Mount the read-only Google Ads tools onto the FastMCP app + register their capabilities."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastmcp import FastMCP

from ....core.context import ServerContext
from ....core.mcp.register import add_tool
from ....core.registry.registry import Capability, ToolSpec
from . import report_tools
from .change_history import change_history
from .fields import field_deltas_2026, list_v24_new_views
from .gaql_tools import run_gaql


def register_google_ads_read(app: FastMCP, ctx: ServerContext) -> None:
    stream = ctx.stream()  # bound once (build client object lazily via the injected factory)

    def ads_gaql_query(customer_id: str, query: str) -> dict[str, object]:
        return run_gaql(customer_id=customer_id, query=query, stream=stream)

    def ads_report_campaign(customer_id: str, date_range: str = "LAST_7_DAYS") -> dict[str, object]:
        return report_tools.report_campaign(
            customer_id=customer_id, date_range=date_range, stream=stream
        )

    def ads_report_search_terms(
        customer_id: str, date_range: str = "LAST_14_DAYS"
    ) -> dict[str, object]:
        return report_tools.report_search_terms(
            customer_id=customer_id, date_range=date_range, stream=stream
        )

    def ads_report_pmax(customer_id: str, date_range: str = "LAST_14_DAYS") -> dict[str, object]:
        return report_tools.report_pmax_asset_groups(
            customer_id=customer_id, date_range=date_range, stream=stream
        )

    def ads_report_ai_max(customer_id: str, date_range: str = "LAST_30_DAYS") -> dict[str, object]:
        return report_tools.report_ai_max(
            customer_id=customer_id, date_range=date_range, stream=stream
        )

    def ads_report_conversions(
        customer_id: str, date_range: str = "LAST_30_DAYS"
    ) -> dict[str, object]:
        return report_tools.report_conversions(
            customer_id=customer_id, date_range=date_range, stream=stream
        )

    def ads_change_history(
        customer_id: str, mode: str = "audit", date_range: str = "LAST_7_DAYS", limit: int = 10000
    ) -> dict[str, object]:
        return change_history(
            customer_id=customer_id, mode=mode, date_range=date_range, limit=limit, stream=stream
        )

    def ads_fields_deltas() -> dict[str, object]:
        return field_deltas_2026()

    def ads_fields_new_views() -> dict[str, object]:
        return {"new_views_2026": list_v24_new_views()}

    tools: list[tuple[str, str, Callable[..., Any]]] = [
        ("ads.gaql.query", "Run an arbitrary read-only GAQL query.", ads_gaql_query),
        ("ads.report.campaign", "Campaign performance report.", ads_report_campaign),
        (
            "ads.report.search_terms",
            "Search-terms report (incl. AI Max source).",
            ads_report_search_terms,
        ),
        ("ads.report.pmax_asset_groups", "Performance Max asset-group report.", ads_report_pmax),
        ("ads.report.ai_max", "AI Max matched-location-interest report.", ads_report_ai_max),
        ("ads.report.conversions", "Conversions by conversion date.", ads_report_conversions),
        (
            "ads.change_history",
            "Change history (audit=change_event, delta=change_status).",
            ads_change_history,
        ),
        ("ads.fields.deltas", "Curated v24 2026 field/view deltas.", ads_fields_deltas),
        ("ads.fields.new_views", "New 2026 reporting views.", ads_fields_new_views),
    ]
    for name, description, fn in tools:
        add_tool(app, name, description, fn)

    ctx.registry.register(
        Capability(
            connector="google_ads",
            domain="read",
            tools=[ToolSpec(name=name, summary=description) for name, description, _ in tools],
        )
    )
