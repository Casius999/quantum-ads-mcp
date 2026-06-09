"""Live conformance for the Search Console connector (run with `pytest -m live`).

sites.list on the webmasters.readonly scope, then searchAnalytics + sitemaps.list against the first
owned site (skipped when the token owns no Search Console property), plus a validate_only sitemap
mutate preview (no submit/delete is performed).
"""

import os

import pytest

pytestmark = pytest.mark.live

_REQ = ("GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_OAUTH_CLIENT_SECRET", "GOOGLE_OAUTH_REFRESH_TOKEN")


def _creds() -> dict[str, object]:
    if any(not os.environ.get(k) for k in _REQ):
        pytest.skip("broad OAuth creds missing")
    return {
        "client_id": os.environ["GOOGLE_OAUTH_CLIENT_ID"],
        "client_secret": os.environ["GOOGLE_OAUTH_CLIENT_SECRET"],
        "refresh_token": os.environ["GOOGLE_OAUTH_REFRESH_TOKEN"],
        "quota_project_id": os.environ.get("GOOGLE_CLOUD_PROJECT", ""),
    }


def _read():
    from quantum_ads.connectors.searchconsole.sdk import read_factory

    return read_factory(_creds(), "v3")


def _first_site() -> str | None:
    sites = _read()("sites.list", {})
    return str(sites[0]["siteUrl"]) if sites else None


def test_searchconsole_sites_list_live():
    assert isinstance(_read()("sites.list", {}), list)


def test_searchconsole_search_analytics_live():
    site = _first_site()
    if not site:
        pytest.skip("token owns no Search Console property")
    rows = _read()(
        "searchAnalytics.query",
        {
            "site_url": site,
            "start_date": "2026-05-01",
            "end_date": "2026-05-31",
            "dimensions": ["query"],
            "row_limit": 5,
        },
    )
    assert isinstance(rows, list)


def test_searchconsole_sitemaps_list_live():
    site = _first_site()
    if not site:
        pytest.skip("token owns no Search Console property")
    assert isinstance(_read()("sitemaps.list", {"site_url": site}), list)


def test_searchconsole_submit_sitemap_validate_only_live():
    from quantum_ads.connectors.searchconsole.sdk import mutate_factory

    ops: list[dict[str, object]] = [
        {"action": "submit", "feedpath": "https://example.com/sitemap.xml"}
    ]
    out = mutate_factory(_creds(), "v3")("https://example.com/", ops, True)  # preview only
    assert out["validate_only"] is True
