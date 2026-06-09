"""Live reachability for the Campaign Manager 360 connector (run with `pytest -m live`).

No CM360 account is required: userProfiles.list returns the (possibly empty) set of the caller's CM360
profiles — reaching the dfareporting API IS the proof. Plus a validate_only placement-patch preview.
Needs a broad-scope OAuth token with `dfatrafficking` + GOOGLE_CLOUD_PROJECT (quota project where
dfareporting.googleapis.com is enabled).
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


def test_cm360_user_profiles_reachable_live(reached_or_skip):
    from quantum_ads.connectors.cm360.sdk import default_read_factory

    read = default_read_factory(_creds(), "v4")
    rows = reached_or_skip(lambda: read("userProfiles.list", {}))
    assert isinstance(rows, list)  # empty when the token owns no CM360 profile


def test_cm360_update_placement_validate_only_live():
    from quantum_ads.connectors.cm360.sdk import default_mutate_factory

    ops: list[dict[str, object]] = [
        {"action": "update_placement", "placement_id": "1", "fields": {}}
    ]
    out = default_mutate_factory(_creds(), "v4")("0", ops, True)  # preview only
    assert out["validate_only"] is True
