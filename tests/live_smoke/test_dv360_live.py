"""Live reachability for the Display & Video 360 connector (run with `pytest -m live`).

DV360 has no no-account "list everything" endpoint — every read is scoped to a partner/advertiser
the caller owns. So the validate_only line-item preview is the always-available contract proof, and
advertisers.list is attempted only when DV360_PARTNER_ID is provided (skipped otherwise). Needs a
broad-scope OAuth token with `display-video` + GOOGLE_CLOUD_PROJECT (quota project where
displayvideo.googleapis.com is enabled).
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


def test_dv360_set_status_validate_only_live():
    from quantum_ads.connectors.dv360.sdk import default_mutate_factory

    ops: list[dict[str, object]] = [
        {
            "action": "set_line_item_status",
            "line_item_id": "1",
            "entity_status": "ENTITY_STATUS_PAUSED",
        }
    ]
    out = default_mutate_factory(_creds(), "v4")("0", ops, True)  # preview only
    assert out["validate_only"] is True


def test_dv360_advertisers_list_reachable_live():
    partner = os.environ.get("DV360_PARTNER_ID")
    if not partner:
        pytest.skip("set DV360_PARTNER_ID to exercise advertisers.list (needs a DV360 partner)")
    from quantum_ads.connectors.dv360.sdk import default_read_factory

    rows = default_read_factory(_creds(), "v4")("advertisers.list", {"partner_id": partner})
    assert isinstance(rows, list)
