"""Live conformance for the Cloud Translation + Natural Language connector (`pytest -m live`).

All five read ops (translate / detect / sentiment / entities / batch_translate). Needs a broad-scope
OAuth token (cloud-platform) in GOOGLE_OAUTH_* and GOOGLE_CLOUD_PROJECT. These calls incur small
Translation / Natural Language API cost (a few characters each).
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
        "project": proj,
        "quota_project_id": proj,
    }


def _read():
    from quantum_ads.connectors.language.sdk import language_read_factory

    return language_read_factory(_creds(), "v3")


def test_language_translate_live():
    rows = _read()("translate", {"text": "Hello world", "target_language": "fr"})
    assert rows and rows[0]["translated_text"]


def test_language_detect_live():
    rows = _read()("detect", {"text": "Bonjour le monde"})
    assert rows and rows[0]["language_code"]


def test_language_sentiment_live():
    rows = _read()("sentiment", {"text": "I absolutely love this product."})
    assert rows and "score" in rows[0]


def test_language_entities_live():
    rows = _read()("entities", {"text": "Google was founded in California."})
    assert isinstance(rows, list)


def test_language_batch_translate_live():
    rows = _read()("batch_translate", {"texts": ["Hello", "Goodbye"], "target_language": "es"})
    assert len(rows) == 2
