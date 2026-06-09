"""Live reachability for the Ads Data Hub connector (run with `pytest -m live`).

No ADH account is required: customers.list returns the (possibly empty) set of accessible ADH
customers — reaching the adsdatahub API IS the proof. Plus a validate_only analysis-query-create
preview. Needs a broad-scope OAuth token with `adsdatahub` + GOOGLE_CLOUD_PROJECT (quota project
where adsdatahub.googleapis.com is enabled).
"""

import os

import pytest

pytestmark = pytest.mark.live

_REQ = ("GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_OAUTH_CLIENT_SECRET", "GOOGLE_OAUTH_REFRESH_TOKEN")


def _creds() -> dict[str, object]:
    proj = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if any(not os.environ.get(k) for k in _REQ) or not proj:
        pytest.skip("broad OAuth creds or GOOGLE_CLOUD_PROJECT missing")
    return {
        "client_id": os.environ["GOOGLE_OAUTH_CLIENT_ID"],
        "client_secret": os.environ["GOOGLE_OAUTH_CLIENT_SECRET"],
        "refresh_token": os.environ["GOOGLE_OAUTH_REFRESH_TOKEN"],
        "quota_project_id": proj,
    }


def test_adh_customers_list_reachable_live():
    from quantum_ads.connectors.adh.sdk import read_factory

    rows = read_factory(_creds(), "v1")("customers.list", {})
    assert isinstance(rows, list)  # empty when the token owns no ADH customer


def test_adh_create_query_validate_only_live():
    from quantum_ads.connectors.adh.sdk import mutate_factory

    ops: list[dict[str, object]] = [
        {"entity": "analysis_query", "title": "qa_smoke", "query_text": "SELECT 1"}
    ]
    out = mutate_factory(_creds(), "v1")("0", ops, True)  # preview only
    assert out["validate_only"] is True
