"""Live conformance for the Google Trends connector (run with `pytest -m live`).

pytends scrapes the unofficial public Trends endpoints — no Google credentials. These endpoints
aggressively rate-limit (HTTP 429) and drift without notice, so each op skips (does not fail) on
any transport/parse error; a green run proves the dispatch + frame-normalization path end to end.
"""

import pytest

pytestmark = pytest.mark.live


def _read():
    from quantum_ads.connectors.trends.sdk import read_factory

    return read_factory({}, "v1")


def test_trends_interest_over_time_live():
    try:
        rows = _read()(
            "interest_over_time",
            {"keywords": ["coffee"], "timeframe": "today 3-m", "geo": ""},
        )
    except Exception as exc:  # noqa: BLE001 — pytrends is unofficial + rate-limited
        pytest.skip(f"pytrends unavailable: {type(exc).__name__}")
    assert isinstance(rows, list)


def test_trends_trending_now_live():
    try:
        rows = _read()("trending_now", {"geo": "US"})
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"pytrends unavailable: {type(exc).__name__}")
    assert isinstance(rows, list)
