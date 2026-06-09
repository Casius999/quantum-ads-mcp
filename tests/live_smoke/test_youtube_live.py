"""Live conformance for the YouTube Data API v3 read plane (run with `pytest -m live`).

Validates the Data API read ops against public resources with a youtube.readonly token, plus a
validate_only mutate preview. The Analytics/Reporting surface (yt-analytics.readonly) is NOT
covered here — that scope is not in the validation token; re-consent is required to exercise it.
"""

import os

import pytest

pytestmark = pytest.mark.live

_REQ = ("GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_OAUTH_CLIENT_SECRET", "GOOGLE_OAUTH_REFRESH_TOKEN")

# Stable public resources (Google Developers channel / a long-lived public video).
_PUBLIC_CHANNEL = "UC_x5XG1OV2P6uZZ5FSM9Ttw"
_PUBLIC_VIDEO = "dQw4w9WgXcQ"


def _creds() -> dict[str, object]:
    if any(not os.environ.get(k) for k in _REQ):
        pytest.skip("broad OAuth creds missing")
    return {
        "client_id": os.environ["GOOGLE_OAUTH_CLIENT_ID"],
        "client_secret": os.environ["GOOGLE_OAUTH_CLIENT_SECRET"],
        "refresh_token": os.environ["GOOGLE_OAUTH_REFRESH_TOKEN"],
        "quota_project_id": os.environ.get("GOOGLE_CLOUD_PROJECT", ""),
    }


def _data():
    from quantum_ads.connectors.youtube.sdk import data_read_factory

    return data_read_factory(_creds(), "v3")


def test_youtube_videos_list_live():
    rows = _data()("videos.list", {"video_ids": [_PUBLIC_VIDEO]})
    assert rows and rows[0]["id"] == _PUBLIC_VIDEO


def test_youtube_channels_get_live():
    rows = _data()("channels.get", {"channel_id": _PUBLIC_CHANNEL})
    assert rows and rows[0]["id"] == _PUBLIC_CHANNEL


def test_youtube_videos_list_bulk_live():
    # The bulk-statistics path: one videos.list call with a comma-separated id list (1 unit).
    rows = _data()("videos.list", {"video_ids": [_PUBLIC_VIDEO, "9bZkp7q19f0"]})
    assert isinstance(rows, list) and len(rows) >= 1


def test_youtube_update_video_validate_only_live():
    from quantum_ads.connectors.youtube.sdk import mutate_factory

    ops: list[dict[str, object]] = [
        {"action": "update_video", "video_id": _PUBLIC_VIDEO, "fields": {"title": "noop"}}
    ]
    out = mutate_factory(_creds(), "v3")(_PUBLIC_CHANNEL, ops, True)  # preview only
    assert out["validate_only"] is True
