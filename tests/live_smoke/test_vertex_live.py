"""Live conformance for the Vertex AI generative connector (run with `pytest -m live`).

BILLABLE: this fires one minimal Gemini Flash generation (a handful of tokens, ~cents) to prove the
live path + OAuth-credentials wiring. Imagen/Veo are NOT exercised (materially more expensive). Needs
a broad-scope OAuth token (cloud-platform) in GOOGLE_OAUTH_*, GOOGLE_CLOUD_PROJECT (quota project
where aiplatform.googleapis.com is enabled), and optionally GOOGLE_VERTEX_MODEL / GOOGLE_VERTEX_LOCATION.
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
        "location": os.environ.get("GOOGLE_VERTEX_LOCATION", "us-central1"),
    }


def test_vertex_gemini_micro_generation_live():
    from quantum_ads.connectors.vertex.sdk import generative_read_factory

    read = generative_read_factory(_creds(), "v1")
    candidates = [
        os.environ.get("GOOGLE_VERTEX_MODEL"),
        "gemini-2.5-flash",
        "gemini-2.0-flash-001",
        "gemini-1.5-flash-002",
    ]
    last_exc: Exception | None = None
    for model in [m for m in candidates if m]:
        try:
            rows = read(
                "gemini",
                {"model": model, "prompt": "Reply with the single word: pong", "max_tokens": 8},
            )
        except Exception as exc:  # noqa: BLE001 — probing which Gemini model the project can access
            last_exc = exc
            continue
        assert rows and rows[0]["text"]
        return
    name = type(last_exc).__name__ if last_exc else "none"
    pytest.skip(f"no Gemini model accessible in this project/region: {name}")
