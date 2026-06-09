"""Search Console API v3 (webmasters) read tools.

Pure request builders (``build_*``) construct the params dict handed to the injected backend
``ReadFn``; the thin ``run_*`` / list wrappers do the result wrapping. The backend ReadFn
signature is ``(operation, params) -> rows`` where operation is one of
``"searchAnalytics.query"`` / ``"sites.list"`` / ``"sitemaps.list"`` / ``"urlInspection.inspect"``.

The ``{"rows", "row_count"}`` envelope matches the Google Ads / Merchant read connectors.
"""

from __future__ import annotations

from ..types import ReadFn

# Operation names passed as the first ReadFn argument.
OP_SEARCH_ANALYTICS = "searchAnalytics.query"
OP_SITES_LIST = "sites.list"
OP_SITEMAPS_LIST = "sitemaps.list"
OP_URL_INSPECT = "urlInspection.inspect"

# Default number of rows requested from searchAnalytics.query (API max is 25000).
DEFAULT_ROW_LIMIT = 1000


def build_search_analytics_request(
    *,
    site_url: str,
    start_date: str,
    end_date: str,
    dimensions: list[str],
    row_limit: int = DEFAULT_ROW_LIMIT,
) -> dict[str, object]:
    """Build the searchAnalytics.query request body (date range + dimensions + row limit).

    The dimensions (query/page/country/device/date/searchAppearance) drive the breakdown of the
    clicks/impressions/ctr/position metrics returned per row.
    """
    request: dict[str, object] = {
        "site_url": site_url,
        "start_date": start_date,
        "end_date": end_date,
        "dimensions": list(dimensions),
        "row_limit": row_limit,
    }
    return request


def _wrap(rows: list[dict[str, object]]) -> dict[str, object]:
    """Wrap rows in the shared read envelope."""
    return {"rows": rows, "row_count": len(rows)}


def search_analytics(
    *,
    site_url: str,
    start_date: str,
    end_date: str,
    dimensions: list[str],
    row_limit: int = DEFAULT_ROW_LIMIT,
    read: ReadFn,
) -> dict[str, object]:
    """Tool: query Search Analytics (organic clicks/impressions/ctr/position) for a property."""
    request = build_search_analytics_request(
        site_url=site_url,
        start_date=start_date,
        end_date=end_date,
        dimensions=dimensions,
        row_limit=row_limit,
    )
    return _wrap(read(OP_SEARCH_ANALYTICS, request))


def list_sites(*, read: ReadFn) -> dict[str, object]:
    """Tool: list the Search Console properties the authenticated user can access."""
    params: dict[str, object] = {}
    return _wrap(read(OP_SITES_LIST, params))


def list_sitemaps(*, site_url: str, read: ReadFn) -> dict[str, object]:
    """Tool: list the sitemaps submitted for a property."""
    params: dict[str, object] = {"site_url": site_url}
    return _wrap(read(OP_SITEMAPS_LIST, params))


def inspect_url(*, site_url: str, inspection_url: str, read: ReadFn) -> dict[str, object]:
    """Tool: inspect a URL's index status for a property (URL Inspection API)."""
    params: dict[str, object] = {"site_url": site_url, "inspection_url": inspection_url}
    return _wrap(read(OP_URL_INSPECT, params))
