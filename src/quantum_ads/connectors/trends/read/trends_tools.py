"""Google Trends read tools: pure request builders + thin backend-invoking wrappers.

Pure ``build_*`` functions construct the params dict handed to the injected ``ReadFn`` backend
(unit-tested directly); the thin tool wrappers do the result wrapping. The backend ReadFn
signature is ``(operation, params) -> rows`` where operation is one of
``"interest_over_time"`` / ``"related_queries"`` / ``"trending_now"`` / ``"interest_by_region"``.

The ``{"rows", "row_count"}`` envelope matches the Search Console / YouTube / Merchant read
connectors. Demand/seasonality is the agency use-case: interest over time drives budget pacing,
related queries surface keyword expansion, trending now flags breakout demand, and interest by
region informs geo-targeting.
"""

from __future__ import annotations

from ..types import ReadFn

# Operation names passed as the first ReadFn argument.
OP_INTEREST_OVER_TIME = "interest_over_time"
OP_RELATED_QUERIES = "related_queries"
OP_TRENDING_NOW = "trending_now"
OP_INTEREST_BY_REGION = "interest_by_region"

# Default lookback window for interest_over_time (pytrends timeframe grammar; ~12 months).
DEFAULT_TIMEFRAME = "today 12-m"
# Default region resolution for interest_by_region (COUNTRY / REGION / CITY / DMA).
DEFAULT_RESOLUTION = "COUNTRY"
# Default geo for trending_now (two-letter country code; Trends requires one, unlike the
# empty-geo "worldwide" default used by the keyword-scoped calls).
DEFAULT_TRENDING_GEO = "US"


def build_interest_over_time_request(
    *,
    keywords: list[str],
    timeframe: str = DEFAULT_TIMEFRAME,
    geo: str = "",
) -> dict[str, object]:
    """Build the interest_over_time request (keywords + timeframe + geo).

    ``keywords`` is the comparison set (Trends compares up to 5 terms on a 0-100 relative scale);
    ``timeframe`` follows the pytrends grammar (e.g. ``"today 12-m"``, ``"2026-01-01 2026-06-01"``);
    ``geo`` is an empty string for worldwide or a Trends geo code (e.g. ``"US"``, ``"US-CA"``).
    """
    request: dict[str, object] = {
        "keywords": list(keywords),
        "timeframe": timeframe,
        "geo": geo,
    }
    return request


def build_related_queries_request(*, keyword: str, geo: str = "") -> dict[str, object]:
    """Build the related_queries request (single keyword + geo).

    Returns the top + rising related search queries for ``keyword`` — the keyword-expansion signal
    for the agency. ``geo`` is empty for worldwide or a Trends geo code.
    """
    request: dict[str, object] = {"keyword": keyword, "geo": geo}
    return request


def build_trending_now_request(*, geo: str = DEFAULT_TRENDING_GEO) -> dict[str, object]:
    """Build the trending_now request (geo only).

    Daily/real-time trending searches for a country. ``geo`` is a two-letter country code; Trends
    requires one here (there is no worldwide trending feed), so it defaults to ``"US"``.
    """
    request: dict[str, object] = {"geo": geo}
    return request


def build_interest_by_region_request(
    *, keyword: str, resolution: str = DEFAULT_RESOLUTION
) -> dict[str, object]:
    """Build the interest_by_region request (single keyword + resolution).

    Geographic breakdown of interest in ``keyword`` for geo-targeting. ``resolution`` is one of
    ``COUNTRY`` / ``REGION`` / ``CITY`` / ``DMA``.
    """
    request: dict[str, object] = {"keyword": keyword, "resolution": resolution}
    return request


def _wrap(rows: list[dict[str, object]]) -> dict[str, object]:
    """Wrap rows in the shared read envelope."""
    return {"rows": rows, "row_count": len(rows)}


def interest_over_time(
    *,
    keywords: list[str],
    timeframe: str = DEFAULT_TIMEFRAME,
    geo: str = "",
    read: ReadFn,
) -> dict[str, object]:
    """Tool: relative search interest over time for a comparison set (demand / seasonality)."""
    request = build_interest_over_time_request(keywords=keywords, timeframe=timeframe, geo=geo)
    return _wrap(read(OP_INTEREST_OVER_TIME, request))


def related_queries(*, keyword: str, geo: str = "", read: ReadFn) -> dict[str, object]:
    """Tool: top + rising related search queries for a keyword (keyword expansion)."""
    request = build_related_queries_request(keyword=keyword, geo=geo)
    return _wrap(read(OP_RELATED_QUERIES, request))


def trending_now(*, geo: str = DEFAULT_TRENDING_GEO, read: ReadFn) -> dict[str, object]:
    """Tool: currently trending searches for a country (breakout demand)."""
    request = build_trending_now_request(geo=geo)
    return _wrap(read(OP_TRENDING_NOW, request))


def interest_by_region(
    *, keyword: str, resolution: str = DEFAULT_RESOLUTION, read: ReadFn
) -> dict[str, object]:
    """Tool: geographic breakdown of interest in a keyword (geo-targeting)."""
    request = build_interest_by_region_request(keyword=keyword, resolution=resolution)
    return _wrap(read(OP_INTEREST_BY_REGION, request))
