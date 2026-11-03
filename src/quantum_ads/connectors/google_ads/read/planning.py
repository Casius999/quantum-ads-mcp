"""Google Ads planning and discovery reads: recommendations, keyword ideas, mutate schema."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastmcp import FastMCP

from ....core.context import ServerContext
from ....core.mcp.register import add_tool
from ....core.query.runner import StreamFn
from ....core.registry.registry import ToolSpec
from ..write.operations import InvalidOperation, operation_kinds, resource_fields

# recommendation.impact is selectable only as a whole (its sub-fields are not, per
# GoogleAdsFieldService for v26); it carries base vs potential metrics.
_RECOMMENDATION_FIELDS = (
    "recommendation.resource_name, recommendation.type, recommendation.campaign, "
    "recommendation.ad_group, recommendation.impact"
)
_SERVICES_NOT_CONFIGURED: dict[str, object] = {
    "error": {"code": "BACKEND_NOT_CONFIGURED", "message": "Google Ads services not wired"}
}


def _api_message(exc: Exception) -> str:
    """Google Ads errors carry a failure with codes and messages; keep those, not the gRPC dump."""
    failure = getattr(exc, "failure", None)
    if failure is not None and getattr(failure, "errors", None):
        parts = [f"{err.error_code}: {err.message}" for err in failure.errors]
        return " ".join("; ".join(parts).split())[:1000]
    return str(exc)[:1000]


def build_recommendations_query(types: list[str] | None = None, limit: int = 100) -> str:
    where = " WHERE recommendation.dismissed = FALSE"
    if types:
        names = ", ".join(f"'{t.upper()}'" for t in types if t.replace("_", "").isalnum())
        where += f" AND recommendation.type IN ({names})"
    return f"SELECT {_RECOMMENDATION_FIELDS} FROM recommendation{where} LIMIT {int(limit)}"


def register_google_ads_planning(
    app: FastMCP, ctx: ServerContext, stream: StreamFn
) -> list[ToolSpec]:
    def ads_recommendations_list(
        customer_id: str, types: list[str] | None = None, limit: int = 100
    ) -> dict[str, object]:
        rows = stream(customer_id, build_recommendations_query(types, limit))
        return {"rows": rows, "row_count": len(rows)}

    def ads_keyword_ideas(
        customer_id: str,
        keywords: list[str] | None = None,
        url: str | None = None,
        language_id: str = "1000",
        geo_target_ids: list[str] | None = None,
        limit: int = 50,
    ) -> dict[str, object]:
        services = ctx.services()
        if services is None:
            return dict(_SERVICES_NOT_CONFIGURED)
        if not keywords and not url:
            return {"error": {"code": "INVALID_ARGUMENT", "message": "give keywords and/or url"}}
        rows = services(
            "keyword_ideas",
            {
                "customer_id": customer_id,
                "keywords": keywords or [],
                "url": url,
                "language_id": language_id,
                "geo_target_ids": geo_target_ids or [],
                "limit": limit,
            },
        )
        return {"rows": rows, "row_count": len(rows)}

    def service_rows(op: str, params: dict[str, object]) -> dict[str, object]:
        services = ctx.services()
        if services is None:
            return dict(_SERVICES_NOT_CONFIGURED)
        try:
            rows = services(op, params)
        except Exception as exc:  # noqa: BLE001 - API refusals (e.g. allowlisted Reach Planner)
            return {"error": {"code": "API_ERROR", "message": _api_message(exc)}}
        return {"rows": rows, "row_count": len(rows)}

    def ads_batch_status(customer_id: str, batch_job: str, limit: int = 100) -> dict[str, object]:
        return service_rows(
            "batch_status", {"customer_id": customer_id, "batch_job": batch_job, "limit": limit}
        )

    def ads_reach_locations() -> dict[str, object]:
        return service_rows("reach_locations", {})

    def ads_reach_products(location_id: str) -> dict[str, object]:
        return service_rows("reach_products", {"location_id": location_id})

    def ads_reach_forecast(
        customer_id: str,
        location_id: str,
        currency_code: str,
        duration_days: int,
        products: list[dict[str, Any]],
    ) -> dict[str, object]:
        return service_rows(
            "reach_forecast",
            {
                "customer_id": customer_id,
                "location_id": location_id,
                "currency_code": currency_code,
                "duration_days": duration_days,
                "products": products,
            },
        )

    def ads_mutate_schema(operation_kind: str | None = None) -> dict[str, object]:
        if operation_kind is None:
            return {"version": ctx.version, "operation_kinds": operation_kinds(ctx.version)}
        try:
            return {"version": ctx.version, **resource_fields(ctx.version, operation_kind)}
        except InvalidOperation as exc:
            return {"error": {"code": "INVALID_ARGUMENT", "message": str(exc)}}

    tools: list[tuple[str, str, Callable[..., Any]]] = [
        (
            "ads.recommendations.list",
            "Active Google Ads recommendations with their estimated conversion/cost impact.",
            ads_recommendations_list,
        ),
        (
            "ads.keyword_ideas",
            "Keyword Planner ideas from seed keywords and/or a URL: monthly searches, "
            "competition, top-of-page bid range.",
            ads_keyword_ideas,
        ),
        (
            "ads.batch.status",
            "Status of a BatchJob and, once done, its per-operation results.",
            ads_batch_status,
        ),
        (
            "ads.reach.locations",
            "Reach Planner: plannable locations (ids for ads.reach.products / forecast).",
            ads_reach_locations,
        ),
        (
            "ads.reach.products",
            "Reach Planner: plannable video/display products for a location.",
            ads_reach_products,
        ),
        (
            "ads.reach.forecast",
            "Reach Planner forecast (reach curve, on-target impressions) for a media plan: "
            "products [{code, budget_micros}], location, currency, duration.",
            ads_reach_forecast,
        ),
        (
            "ads.mutate.schema",
            "List the mutate operation kinds, or the fields of one kind, for the pinned version.",
            ads_mutate_schema,
        ),
    ]
    for name, description, fn in tools:
        add_tool(app, name, description, fn)
    return [ToolSpec(name=n, summary=d) for n, d, _ in tools]
