"""Live reachability for the Search Ads 360 connector (run with `pytest -m live`).

No SA360 account is required: customers.listAccessible returns the (possibly empty) set of accessible
accounts — reaching the API with a valid token + enabled service IS the proof. Plus a validate_only
conversion-ingest preview (connector contract; no API call). Needs a broad-scope OAuth token with
`doubleclicksearch` + GOOGLE_CLOUD_PROJECT (quota project where searchads360.googleapis.com is on).
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


def test_sa360_list_accessible_reachable_live():
    from quantum_ads.connectors.sa360.sdk import read_factory

    rows = read_factory(_creds(), "v0")("customers.listAccessible", {})
    assert isinstance(rows, list)  # empty when the token owns no SA360 account


def test_sa360_ingest_validate_only_live():
    from quantum_ads.connectors.sa360.sdk import mutate_factory

    ops: list[dict[str, object]] = [{"action": "upload_conversions", "conversions": []}]
    out = mutate_factory(_creds(), "v0")("0000000000", ops, True)  # preview only
    assert out["validate_only"] is True
