"""Vertex AI model-catalog conformance (run with `pytest -m live`). Free: no generation.

Google retires and supersedes publisher models continuously — between June and November 2026 the
whole Imagen family left the catalog, Veo 3.0 was replaced by 3.1, and Gemini 2.5 text models
stopped serving generation. A hard-coded default model id therefore rots silently: the tool keeps
advertising a model that now 404s. This test reads the live publisher catalog and asserts every
default model the vertex connector ships is listed AND generally available (GA).

Needs a broad-scope OAuth token (cloud-platform) in GOOGLE_OAUTH_* and GOOGLE_CLOUD_PROJECT.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

import pytest

from quantum_ads.connectors.vertex.gen_tools import DEFAULT_GEMINI_MODEL
from quantum_ads.connectors.vertex.sdk import DEFAULT_IMAGE_MODEL, DEFAULT_VIDEO_MODEL

pytestmark = pytest.mark.live

_REQ = ("GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_OAUTH_CLIENT_SECRET", "GOOGLE_OAUTH_REFRESH_TOKEN")
_CATALOG = "https://us-central1-aiplatform.googleapis.com/v1beta1/publishers/google/models"
_DEFAULTS = {
    "text": DEFAULT_GEMINI_MODEL,
    "image": DEFAULT_IMAGE_MODEL,
    "video": DEFAULT_VIDEO_MODEL,
}


def _headers() -> dict[str, str]:
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if any(not os.environ.get(k) for k in _REQ) or not project:
        pytest.skip("broad OAuth creds or GOOGLE_CLOUD_PROJECT missing")
    body = urllib.parse.urlencode(
        {
            "client_id": os.environ["GOOGLE_OAUTH_CLIENT_ID"],
            "client_secret": os.environ["GOOGLE_OAUTH_CLIENT_SECRET"],
            "refresh_token": os.environ["GOOGLE_OAUTH_REFRESH_TOKEN"],
            "grant_type": "refresh_token",
        }
    ).encode()
    with urllib.request.urlopen("https://oauth2.googleapis.com/token", body, timeout=30) as resp:  # noqa: S310
        token = json.loads(resp.read())["access_token"]
    return {"Authorization": f"Bearer {token}", "x-goog-user-project": project}


@pytest.mark.parametrize("modality", sorted(_DEFAULTS))
def test_default_model_is_listed_and_ga(modality: str) -> None:
    model = _DEFAULTS[modality]
    request = urllib.request.Request(f"{_CATALOG}/{model}", headers=_headers())
    try:
        with urllib.request.urlopen(request, timeout=60) as resp:  # noqa: S310 — fixed Google URL
            meta = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        pytest.fail(
            f"default {modality} model {model!r} is not in the publisher catalog: {exc.code}"
        )
    assert meta.get("launchStage") == "GA", f"{model!r} is {meta.get('launchStage')}, not GA"
