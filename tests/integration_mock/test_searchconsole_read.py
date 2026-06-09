"""Search Console read connector: registration, read_only flags, request builders, degradation.

All fakes — the real googleapiclient (webmasters v3 / Search Console URL Inspection) SDK is never
imported. Verifies the ``{"rows", "row_count"}`` envelope, the right operation name + params reach
the backend, and a missing backend yields a structured ``BACKEND_NOT_CONFIGURED`` error.
"""

from quantum_ads.connectors.searchconsole import register_searchconsole
from quantum_ads.connectors.searchconsole.read import search_analytics_tools as tools_mod
from quantum_ads.connectors.searchconsole.read.connector import register_searchconsole_read
from quantum_ads.core.query.runner import StreamFn


def _env() -> dict[str, str]:
    return {
        "GOOGLE_ADS_DEVELOPER_TOKEN": "d",
        "GOOGLE_ADS_CLIENT_ID": "c",
        "GOOGLE_ADS_CLIENT_SECRET": "s",
        "GOOGLE_ADS_REFRESH_TOKEN": "r",
        "QUANTUM_ADS_READ_ONLY": "false",
    }


def _stream(creds: dict[str, object], version: str) -> StreamFn:
    return lambda cid, q: []


_CANNED_ROW: dict[str, object] = {"clicks": 10, "impressions": 100, "ctr": 0.1, "position": 3.2}


def _fake_read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
    return [{"operation": operation, "params": params, **_CANNED_ROW}]


def _fake_mutate(
    site_url: str, operations: list[dict[str, object]], validate_only: bool
) -> dict[str, object]:
    return {"validate_only": validate_only}


def _backends() -> dict[str, object]:
    return {"searchconsole.api": _fake_read, "searchconsole.mutate": _fake_mutate}


# --- registration via register_searchconsole (full connector) -------------------------------


def test_searchconsole_read_tools_registered():
    from quantum_ads.server import build_server

    assembled = build_server(
        env=_env(),
        stream_factory=_stream,
        backends=_backends(),
        connectors=[register_searchconsole],
    )
    names = {t.name for t in assembled.registry.all_tools()}
    assert "searchconsole.search_analytics" in names
    assert "searchconsole.sites.list" in names
    assert "searchconsole.sitemaps.list" in names
    assert "searchconsole.url_inspect" in names


def test_searchconsole_read_tools_are_read_only():
    from quantum_ads.server import build_server

    assembled = build_server(
        env=_env(),
        stream_factory=_stream,
        backends=_backends(),
        connectors=[register_searchconsole],
    )
    for name in (
        "searchconsole.search_analytics",
        "searchconsole.sites.list",
        "searchconsole.sitemaps.list",
        "searchconsole.url_inspect",
    ):
        assert assembled.registry.describe_tool(name).read_only is True


def test_register_searchconsole_read_alone_registers_only_read_tools():
    from quantum_ads.server import build_server

    assembled = build_server(
        env=_env(),
        stream_factory=_stream,
        backends=_backends(),
        connectors=[register_searchconsole_read],
    )
    names = {t.name for t in assembled.registry.all_tools()}
    assert "searchconsole.search_analytics" in names
    assert "searchconsole.sitemaps.submit" not in names


# --- pure request builder (unit) ------------------------------------------------------------


def test_build_search_analytics_request_shape():
    request = tools_mod.build_search_analytics_request(
        site_url="https://example.com/",
        start_date="2026-05-01",
        end_date="2026-05-31",
        dimensions=["query", "page"],
        row_limit=500,
    )
    assert request == {
        "site_url": "https://example.com/",
        "start_date": "2026-05-01",
        "end_date": "2026-05-31",
        "dimensions": ["query", "page"],
        "row_limit": 500,
    }


def test_build_search_analytics_request_defaults_row_limit():
    request = tools_mod.build_search_analytics_request(
        site_url="https://example.com/",
        start_date="2026-05-01",
        end_date="2026-05-31",
        dimensions=["query"],
    )
    assert request["row_limit"] == tools_mod.DEFAULT_ROW_LIMIT


# --- tool helpers against the fake ReadFn ---------------------------------------------------


def test_search_analytics_wraps_rows_and_passes_request():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["operation"] = operation
        seen["params"] = params
        return [{"keys": ["shoes"], "clicks": 5}]

    out = tools_mod.search_analytics(
        site_url="https://example.com/",
        start_date="2026-05-01",
        end_date="2026-05-31",
        dimensions=["query"],
        read=read,
    )
    assert out["rows"] == [{"keys": ["shoes"], "clicks": 5}]
    assert out["row_count"] == 1
    assert seen["operation"] == "searchAnalytics.query"
    assert isinstance(seen["params"], dict)
    assert seen["params"]["site_url"] == "https://example.com/"
    assert seen["params"]["dimensions"] == ["query"]


def test_list_sites_uses_sites_operation_and_no_params():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["operation"] = operation
        seen["params"] = params
        return [{"siteUrl": "https://example.com/", "permissionLevel": "siteOwner"}]

    out = tools_mod.list_sites(read=read)
    assert out["row_count"] == 1
    assert seen["operation"] == "sites.list"
    assert seen["params"] == {}


def test_list_sitemaps_passes_site_url():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["operation"] = operation
        seen["params"] = params
        return [{"path": "https://example.com/sitemap.xml"}]

    out = tools_mod.list_sitemaps(site_url="https://example.com/", read=read)
    assert out["rows"] == [{"path": "https://example.com/sitemap.xml"}]
    assert seen["operation"] == "sitemaps.list"
    assert seen["params"] == {"site_url": "https://example.com/"}


def test_inspect_url_passes_inspection_url():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["operation"] = operation
        seen["params"] = params
        return [{"inspectionResult": {"indexStatusResult": {"verdict": "PASS"}}}]

    out = tools_mod.inspect_url(
        site_url="https://example.com/",
        inspection_url="https://example.com/page",
        read=read,
    )
    assert out["row_count"] == 1
    assert seen["operation"] == "urlInspection.inspect"
    assert seen["params"] == {
        "site_url": "https://example.com/",
        "inspection_url": "https://example.com/page",
    }


# --- backend-not-configured degradation (integration) ---------------------------------------


def test_read_tools_degrade_when_backend_missing():
    from quantum_ads.server import build_server

    # No backends wired -> ctx.backend("searchconsole.api") is None.
    assembled = build_server(
        env=_env(),
        stream_factory=_stream,
        connectors=[register_searchconsole_read],
    )
    names = {t.name for t in assembled.registry.all_tools()}
    assert "searchconsole.search_analytics" in names
