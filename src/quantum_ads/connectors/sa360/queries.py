"""Pure builders for Search Ads 360 query strings + read params (unit-tested directly).

SA360 (the new Search Ads 360 Reporting API v0, the cross-engine search-management reporting
plane) speaks a GAQL-like query language: ``SELECT <fields> FROM <resource> WHERE <predicates>``.
These builders assemble that query string for the report shortcuts and wrap the
``(customer_id, query)`` pair as backend params for the generic ``search`` operation. They never
touch the network — the injected ``ReadFn`` backend owns the live ``searchAds360:search`` call.

``date_range`` is validated against a closed allow-list (anti-injection: the value is interpolated
into ``segments.date DURING <range>``), mirroring the Google Ads report wrappers.
"""

from __future__ import annotations

# Operation names passed as the first ReadFn argument.
OP_SEARCH = "search"
OP_LIST_ACCESSIBLE_CUSTOMERS = "customers.listAccessible"

# Allowed date-range literals for the report shortcuts (interpolated into the query -> allow-list
# them to keep the query language injection-safe). SA360 shares the Google Ads date-range tokens.
ALLOWED_DATE_RANGES: set[str] = {
    "TODAY",
    "YESTERDAY",
    "LAST_7_DAYS",
    "LAST_14_DAYS",
    "LAST_30_DAYS",
    "THIS_MONTH",
    "LAST_MONTH",
    "LAST_BUSINESS_WEEK",
}

# Field projections for the opinionated report shortcuts.
_CAMPAIGN_FIELDS: list[str] = [
    "campaign.id",
    "campaign.name",
    "campaign.status",
    "metrics.impressions",
    "metrics.clicks",
    "metrics.cost_micros",
    "metrics.conversions",
]
_AD_GROUP_FIELDS: list[str] = [
    "ad_group.id",
    "ad_group.name",
    "ad_group.status",
    "campaign.name",
    "metrics.impressions",
    "metrics.clicks",
    "metrics.cost_micros",
    "metrics.conversions",
]


def build_search_query(
    *,
    resource: str,
    fields: list[str],
    date_range: str,
    order_by: str | None = None,
) -> str:
    """Assemble a SA360 ``SELECT ... FROM ... WHERE segments.date DURING <range>`` query string.

    Pure: ``fields`` are joined verbatim; the caller supplies a vetted projection. ``date_range``
    must already be validated by the caller (see :data:`ALLOWED_DATE_RANGES`).
    """
    select = ", ".join(fields)
    query = f"SELECT {select} FROM {resource} WHERE segments.date DURING {date_range}"
    if order_by is not None:
        query = f"{query} ORDER BY {order_by}"
    return query


def build_campaign_query(date_range: str) -> str:
    """Pure: the campaign performance report query (cost-desc)."""
    return build_search_query(
        resource="campaign",
        fields=_CAMPAIGN_FIELDS,
        date_range=date_range,
        order_by="metrics.cost_micros DESC",
    )


def build_ad_group_query(date_range: str) -> str:
    """Pure: the ad-group performance report query (cost-desc)."""
    return build_search_query(
        resource="ad_group",
        fields=_AD_GROUP_FIELDS,
        date_range=date_range,
        order_by="metrics.cost_micros DESC",
    )


def build_search_params(customer_id: str, query: str) -> dict[str, object]:
    """Pure: wrap a customer id + query string as backend params for the ``search`` operation."""
    params: dict[str, object] = {"customer_id": customer_id, "query": query}
    return params
