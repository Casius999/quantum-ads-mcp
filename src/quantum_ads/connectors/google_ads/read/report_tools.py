"""Opinionated read reports: build verified GAQL for the right FROM resource, then execute."""

from __future__ import annotations

from ....core.query.gaql_builder import build_gaql
from ....core.query.runner import StreamFn
from .gaql_tools import ALLOWED_DATE_RANGES, execute_query


def _report(
    *,
    customer_id: str,
    resource: str,
    fields: list[str],
    date_range: str,
    stream: StreamFn,
    extra_where: list[str] | None = None,
    order_by: str | None = None,
) -> dict[str, object]:
    if date_range not in ALLOWED_DATE_RANGES:
        return {
            "error": {"code": "BAD_DATE_RANGE", "message": f"unsupported date_range {date_range!r}"}
        }
    where = list(extra_where or [])
    where.append(f"segments.date DURING {date_range}")
    query = build_gaql(resource=resource, fields=fields, where=where, order_by=order_by)
    return execute_query(customer_id, query, stream)


def report_campaign(
    *, customer_id: str, date_range: str = "LAST_7_DAYS", stream: StreamFn
) -> dict[str, object]:
    return _report(
        customer_id=customer_id,
        resource="campaign",
        fields=[
            "campaign.id",
            "campaign.name",
            "campaign.status",
            "metrics.impressions",
            "metrics.clicks",
            "metrics.cost_micros",
            "metrics.conversions",
        ],
        date_range=date_range,
        stream=stream,
        order_by="metrics.cost_micros DESC",
    )


def report_search_terms(
    *, customer_id: str, date_range: str = "LAST_14_DAYS", stream: StreamFn
) -> dict[str, object]:
    return _report(
        customer_id=customer_id,
        resource="search_term_view",
        fields=[
            "search_term_view.search_term",
            "segments.search_term_match_source",
            "metrics.clicks",
            "metrics.conversions",
            "metrics.cost_micros",
        ],
        date_range=date_range,
        stream=stream,
    )


def report_pmax_asset_groups(
    *, customer_id: str, date_range: str = "LAST_14_DAYS", stream: StreamFn
) -> dict[str, object]:
    return _report(
        customer_id=customer_id,
        resource="asset_group",
        fields=[
            "campaign.name",
            "asset_group.name",
            "asset_group.status",
            "metrics.conversions",
            "metrics.conversions_value",
        ],
        date_range=date_range,
        stream=stream,
        extra_where=["campaign.advertising_channel_type = 'PERFORMANCE_MAX'"],
    )


def report_ai_max(
    *, customer_id: str, date_range: str = "LAST_30_DAYS", stream: StreamFn
) -> dict[str, object]:
    return _report(
        customer_id=customer_id,
        resource="matched_location_interest_view",
        fields=[
            "campaign.id",
            "campaign.name",
            "metrics.impressions",
            "metrics.clicks",
            "metrics.conversions",
        ],
        date_range=date_range,
        stream=stream,
    )


def report_conversions(
    *, customer_id: str, date_range: str = "LAST_30_DAYS", stream: StreamFn
) -> dict[str, object]:
    return _report(
        customer_id=customer_id,
        resource="campaign",
        fields=[
            "campaign.name",
            "segments.conversion_action_name",
            "metrics.conversions_by_conversion_date",
            "metrics.conversions_value_by_conversion_date",
        ],
        date_range=date_range,
        stream=stream,
    )
