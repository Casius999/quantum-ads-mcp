"""Live reachability for the Google Business Profile connector (run with `pytest -m live`).

accounts.list returns the (possibly empty) set of GBP accounts the caller manages — reaching the
mybusinessaccountmanagement API IS the proof (a personal account with no listing returns an empty
set). Plus a validate_only location-update preview. Needs a broad-scope OAuth token with
`business.manage` + GOOGLE_CLOUD_PROJECT (quota project where the mybusiness* APIs are enabled).
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


def test_gbp_accounts_list_reachable_live():
    from quantum_ads.connectors.gbp.sdk import read_factory

    rows = read_factory(_creds(), "v1")("accounts.list", {})
    assert isinstance(rows, list)  # empty when the token manages no business listing


def test_gbp_update_location_validate_only_live():
    from quantum_ads.connectors.gbp.sdk import mutate_factory

    ops: list[dict[str, object]] = [
        {"action": "update", "location_name": "locations/0", "fields": {"title": "noop"}}
    ]
    out = mutate_factory(_creds(), "v1")("locations/0", ops, True)  # preview only
    assert out["validate_only"] is True
