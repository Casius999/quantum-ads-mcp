"""Live: free text-to-video through the real Hugging Face ZeroGPU Spaces (no billing).

Skips (not fails) when the free daily GPU quota is exhausted — that is the documented, expected
limit of the free tier, reported by the tool as QUOTA_EXHAUSTED.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from quantum_ads.connectors.video.providers import generate_with_fallback

pytestmark = pytest.mark.live


def test_free_video_generates_a_playable_mp4_live() -> None:
    sdk = pytest.importorskip("quantum_ads.connectors.video.sdk")
    pytest.importorskip("gradio_client")
    import os

    token = os.environ.get("HF_TOKEN")
    call = sdk.free_video_factory({"hf_token": token} if token else {}, "")
    result = generate_with_fallback(
        call,
        prompt="a red sports car driving along a coastal road at sunset, cinematic",
        duration_seconds=2,
        aspect_ratio="16:9",
    )
    error = result.get("error")
    if isinstance(error, dict) and error.get("code") == "QUOTA_EXHAUSTED":
        pytest.skip("Hugging Face ZeroGPU free daily quota exhausted (resets ~24 h)")
    assert error is None, result
    clip = Path(str(result["path"]))
    data = clip.read_bytes()
    assert len(data) > 10_000
    assert data[4:8] == b"ftyp"  # ISO-BMFF / mp4 container
