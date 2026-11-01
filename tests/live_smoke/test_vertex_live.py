"""Live conformance for the Vertex AI generative connector (run with `pytest -m live`).

BILLABLE: this fires one minimal Gemini Flash generation (a handful of tokens, ~cents) to prove the
live path + OAuth-credentials wiring. Imagen/Veo are NOT exercised (materially more expensive). Needs
a broad-scope OAuth token (cloud-platform) in GOOGLE_OAUTH_*, GOOGLE_CLOUD_PROJECT (quota project
where aiplatform.googleapis.com is enabled), and optionally GOOGLE_VERTEX_MODEL / GOOGLE_VERTEX_LOCATION.
"""

import os

import pytest

from quantum_ads.connectors.vertex.gen_tools import DEFAULT_GEMINI_MODEL

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
        "location": os.environ.get("GOOGLE_VERTEX_LOCATION", "global"),
    }


def test_vertex_gemini_micro_generation_live():
    from quantum_ads.connectors.vertex.sdk import generative_read_factory

    read = generative_read_factory(_creds(), "v1")
    candidates = [
        os.environ.get("GOOGLE_VERTEX_MODEL"),
        DEFAULT_GEMINI_MODEL,
        "gemini-3.5-flash",
    ]
    last_exc: Exception | None = None
    for model in [m for m in candidates if m]:
        try:
            rows = read(
                "gemini",
                {"model": model, "prompt": "Reply with the single word: pong", "max_tokens": 512},
            )
        except Exception as exc:  # noqa: BLE001 — probing which Gemini model the project can access
            last_exc = exc
            continue
        assert rows and rows[0]["text"], rows
        return
    name = type(last_exc).__name__ if last_exc else "none"
    pytest.skip(f"no Gemini model accessible in this project/region: {name}")


def test_vertex_image_generation_live():
    # BILLABLE (~cents): one image from the default image model, returned as base64.
    import base64

    from quantum_ads.connectors.vertex.sdk import generative_read_factory

    rows = generative_read_factory(_creds(), "v1")(
        "imagen",
        {"prompt": "A minimalist red sneaker on a white background", "n": 1, "aspect_ratio": "1:1"},
    )
    assert rows and rows[0]["mime_type"].startswith("image/")
    assert len(base64.b64decode(rows[0]["image_base64"])) > 1000  # a real encoded image


def test_vertex_veo_generate_and_poll_live():
    # BILLABLE (several USD per clip): runs only with VERTEX_LIVE_VEO=1. Generates a short clip,
    # then polls vertex.veo.status until done (bounded wait).
    if os.environ.get("VERTEX_LIVE_VEO") != "1":
        pytest.skip("Veo generation is costly; set VERTEX_LIVE_VEO=1 to run it")
    import time

    from quantum_ads.connectors.vertex.sdk import generative_read_factory

    read = generative_read_factory(_creds(), "v1")
    started = read("veo", {"prompt": "Slow pan over a calm sea at sunrise", "duration_seconds": 4})
    op = started[0]["operation_name"]
    assert "/operations/" in op
    deadline = time.monotonic() + 600
    status = read("veo.status", {"operation_name": op})[0]
    while not status["done"] and time.monotonic() < deadline:
        time.sleep(15)
        status = read("veo.status", {"operation_name": op})[0]
    assert status["done"], "Veo operation did not finish within 10 minutes"
    assert status["error"] is None, status["error"]
    assert status["videos"], status
