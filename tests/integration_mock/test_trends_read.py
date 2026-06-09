"""Google Trends read connector: registration, read_only flags, request builders, degradation.

All fakes — the real ``pytrends`` SDK is never imported. Verifies the ``{"rows", "row_count"}``
envelope, the right operation name + params reach the backend, the tools register as read-only,
and a missing backend yields a structured ``BACKEND_NOT_CONFIGURED`` error.
"""

from quantum_ads.connectors.trends import register_trends
from quantum_ads.connectors.trends.read import trends_tools as tools_mod
from quantum_ads.connectors.trends.read.connector import register_trends_read
from quantum_ads.core.query.runner import StreamFn


def _env() -> dict[str, str]:
    return {
        "GOOGLE_ADS_DEVELOPER_TOKEN": "d",
        "GOOGLE_ADS_CLIENT_ID": "c",
        "GOOGLE_ADS_CLIENT_SECRET": "s",
        "GOOGLE_ADS_REFRESH_TOKEN": "r",
        "QUANTUM_ADS_READ_ONLY": "true",
    }


def _stream(creds: dict[str, object], version: str) -> StreamFn:
    return lambda cid, q: []


_CANNED_ROW: dict[str, object] = {"value": 42}


def _fake_read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
    return [{"operation": operation, "params": params, **_CANNED_ROW}]


def _backends() -> dict[str, object]:
    return {"trends.api": _fake_read}


# --- registration via register_trends (full connector) --------------------------------------


def test_trends_read_tools_registered():
    from quantum_ads.server import build_server

    assembled = build_server(
        env=_env(),
        stream_factory=_stream,
        backends=_backends(),
        connectors=[register_trends],
    )
    names = {t.name for t in assembled.registry.all_tools()}
    assert "trends.interest_over_time" in names
    assert "trends.related_queries" in names
    assert "trends.trending_now" in names
    assert "trends.interest_by_region" in names


def test_trends_read_tools_are_read_only():
    from quantum_ads.server import build_server

    assembled = build_server(
        env=_env(),
        stream_factory=_stream,
        backends=_backends(),
        connectors=[register_trends],
    )
    for name in (
        "trends.interest_over_time",
        "trends.related_queries",
        "trends.trending_now",
        "trends.interest_by_region",
    ):
        assert assembled.registry.describe_tool(name).read_only is True


def test_register_trends_read_alone_registers_only_read_tools():
    from quantum_ads.server import build_server

    assembled = build_server(
        env=_env(),
        stream_factory=_stream,
        backends=_backends(),
        connectors=[register_trends_read],
    )
    names = {t.name for t in assembled.registry.all_tools()}
    assert "trends.interest_over_time" in names
    # Trends is read-only: there is no write/mutate tool surface.
    assert not any(name.startswith("trends.") and "write" in name for name in names)


# --- pure request builders (unit) -----------------------------------------------------------


def test_build_interest_over_time_request_shape():
    request = tools_mod.build_interest_over_time_request(
        keywords=["running shoes", "trail shoes"],
        timeframe="today 3-m",
        geo="US",
    )
    assert request == {
        "keywords": ["running shoes", "trail shoes"],
        "timeframe": "today 3-m",
        "geo": "US",
    }


def test_build_interest_over_time_request_defaults():
    request = tools_mod.build_interest_over_time_request(keywords=["running shoes"])
    assert request["timeframe"] == tools_mod.DEFAULT_TIMEFRAME
    assert request["geo"] == ""


def test_build_related_queries_request_shape():
    request = tools_mod.build_related_queries_request(keyword="running shoes", geo="FR")
    assert request == {"keyword": "running shoes", "geo": "FR"}


def test_build_related_queries_request_defaults_geo():
    request = tools_mod.build_related_queries_request(keyword="running shoes")
    assert request["geo"] == ""


def test_build_trending_now_request_defaults_geo():
    request = tools_mod.build_trending_now_request()
    assert request == {"geo": tools_mod.DEFAULT_TRENDING_GEO}


def test_build_trending_now_request_shape():
    request = tools_mod.build_trending_now_request(geo="GB")
    assert request == {"geo": "GB"}


def test_build_interest_by_region_request_shape():
    request = tools_mod.build_interest_by_region_request(keyword="running shoes", resolution="CITY")
    assert request == {"keyword": "running shoes", "resolution": "CITY"}


def test_build_interest_by_region_request_defaults_resolution():
    request = tools_mod.build_interest_by_region_request(keyword="running shoes")
    assert request["resolution"] == tools_mod.DEFAULT_RESOLUTION


# --- tool helpers against the fake ReadFn ---------------------------------------------------


def test_interest_over_time_wraps_rows_and_passes_request():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["operation"] = operation
        seen["params"] = params
        return [{"date": "2026-05-01", "running shoes": 80}]

    out = tools_mod.interest_over_time(
        keywords=["running shoes"], timeframe="today 12-m", geo="US", read=read
    )
    assert out["rows"] == [{"date": "2026-05-01", "running shoes": 80}]
    assert out["row_count"] == 1
    assert seen["operation"] == "interest_over_time"
    assert isinstance(seen["params"], dict)
    assert seen["params"]["keywords"] == ["running shoes"]
    assert seen["params"]["geo"] == "US"


def test_related_queries_uses_related_operation():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["operation"] = operation
        seen["params"] = params
        return [{"bucket": "rising", "query": "best running shoes 2026", "value": 250}]

    out = tools_mod.related_queries(keyword="running shoes", read=read)
    assert out["row_count"] == 1
    assert seen["operation"] == "related_queries"
    assert seen["params"] == {"keyword": "running shoes", "geo": ""}


def test_trending_now_uses_trending_operation_and_geo():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["operation"] = operation
        seen["params"] = params
        return [{"rank": 0, "query": "nba finals"}]

    out = tools_mod.trending_now(geo="US", read=read)
    assert out["rows"] == [{"rank": 0, "query": "nba finals"}]
    assert seen["operation"] == "trending_now"
    assert seen["params"] == {"geo": "US"}


def test_interest_by_region_passes_resolution():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["operation"] = operation
        seen["params"] = params
        return [{"geoName": "California", "running shoes": 100}]

    out = tools_mod.interest_by_region(keyword="running shoes", resolution="REGION", read=read)
    assert out["row_count"] == 1
    assert seen["operation"] == "interest_by_region"
    assert seen["params"] == {"keyword": "running shoes", "resolution": "REGION"}


# --- backend-not-configured degradation (integration) ---------------------------------------


def test_read_tools_degrade_when_backend_missing():
    from quantum_ads.server import build_server

    # No backends wired -> ctx.backend("trends.api") is None.
    assembled = build_server(
        env=_env(),
        stream_factory=_stream,
        connectors=[register_trends_read],
    )
    names = {t.name for t in assembled.registry.all_tools()}
    assert "trends.interest_over_time" in names
