"""Free text-to-video: provider argument mapping and quota-aware fallback."""

from __future__ import annotations

import pytest

from quantum_ads.connectors.video.providers import (
    LTX_VIDEO,
    PROVIDERS,
    WAN_22,
    generate_with_fallback,
    is_quota_error,
)


def test_wan_is_tried_before_ltx():
    assert [p.name for p in PROVIDERS] == ["wan-2.2", "ltx-video"]


def test_wan_arguments():
    kwargs = WAN_22.build_kwargs("a red car", duration_seconds=3, aspect_ratio="9:16", seed=7)
    assert kwargs == {
        "prompt": "a red car",
        "aspect_ratio": "9:16 (480x832)",
        "steps": 4,
        "duration_seconds": 3,
        "seed": 7,
        "randomize_seed": False,
    }


def test_ltx_arguments_follow_the_aspect_ratio():
    kwargs = LTX_VIDEO.build_kwargs("a red car", duration_seconds=4, aspect_ratio="16:9", seed=None)
    assert (kwargs["width_ui"], kwargs["height_ui"]) == (704, 512)
    assert kwargs["mode"] == "text-to-video" and kwargs["duration_ui"] == 4
    assert kwargs["randomize_seed"] is True


def test_unsupported_aspect_ratio_is_refused():
    with pytest.raises(ValueError, match="aspect_ratio"):
        WAN_22.build_kwargs("x", duration_seconds=3, aspect_ratio="21:9", seed=None)


def test_result_shapes_are_normalized_to_a_path():
    assert WAN_22.extract_path(("C:/tmp/a.mp4", 42)) == "C:/tmp/a.mp4"
    assert LTX_VIDEO.extract_path(({"video": "/tmp/b.mp4"}, 1)) == "/tmp/b.mp4"
    assert LTX_VIDEO.extract_path("/tmp/c.mp4") == "/tmp/c.mp4"


@pytest.mark.parametrize(
    "message",
    [
        "You have exceeded your ZeroGPU runs limit. Authenticate with a Hugging Face token",
        "You have exceeded your ZeroGPU quota (120s requested vs. -60s left)",
        "The requested GPU duration (300s) is larger than the maximum allowed",
    ],
)
def test_quota_errors_are_recognized(message: str):
    assert is_quota_error(message)


def test_other_errors_are_not_quota():
    assert not is_quota_error("Connection refused")


def test_first_provider_success_is_returned():
    calls: list[str] = []

    def call(space: str, api_name: str, kwargs: dict[str, object]) -> object:
        calls.append(space)
        return ("/tmp/wan.mp4", 1)

    result = generate_with_fallback(call, prompt="p", duration_seconds=3, aspect_ratio="16:9")
    assert result["provider"] == "wan-2.2" and result["path"] == "/tmp/wan.mp4"
    assert calls == [WAN_22.space]


def test_quota_on_the_first_provider_falls_back_to_the_next():
    def call(space: str, api_name: str, kwargs: dict[str, object]) -> object:
        if space == WAN_22.space:
            raise RuntimeError("You have exceeded your ZeroGPU runs limit.")
        return ({"video": "/tmp/ltx.mp4"}, 2)

    result = generate_with_fallback(call, prompt="p", duration_seconds=3, aspect_ratio="16:9")
    assert result["provider"] == "ltx-video"
    assert result["attempts"] == [{"provider": "wan-2.2", "quota_exhausted": True}]


def test_all_quotas_exhausted_is_a_structured_error_with_the_fix():
    def call(space: str, api_name: str, kwargs: dict[str, object]) -> object:
        raise RuntimeError("You have exceeded your ZeroGPU quota")

    result = generate_with_fallback(call, prompt="p", duration_seconds=3, aspect_ratio="16:9")
    error = result["error"]
    assert isinstance(error, dict)
    assert error["code"] == "QUOTA_EXHAUSTED"
    assert "HF_TOKEN" in str(error["message"])


def test_non_quota_failures_are_reported_per_provider():
    def call(space: str, api_name: str, kwargs: dict[str, object]) -> object:
        raise RuntimeError(f"{space} is down")

    result = generate_with_fallback(call, prompt="p", duration_seconds=3, aspect_ratio="16:9")
    error = result["error"]
    assert isinstance(error, dict) and error["code"] == "GENERATION_FAILED"
    assert [a["provider"] for a in error["attempts"]] == ["wan-2.2", "ltx-video"]  # type: ignore[index]


def test_a_named_provider_is_the_only_one_tried():
    calls: list[str] = []

    def call(space: str, api_name: str, kwargs: dict[str, object]) -> object:
        calls.append(space)
        return "/tmp/x.mp4"

    generate_with_fallback(
        call, prompt="p", duration_seconds=3, aspect_ratio="16:9", provider="ltx-video"
    )
    assert calls == [LTX_VIDEO.space]


def test_unknown_provider_is_refused():
    with pytest.raises(ValueError, match="provider"):
        generate_with_fallback(
            lambda *a: None, prompt="p", duration_seconds=3, aspect_ratio="16:9", provider="sora"
        )


@pytest.mark.parametrize("duration", [0, 11])
def test_duration_is_bounded(duration: int):
    with pytest.raises(ValueError, match="duration"):
        generate_with_fallback(
            lambda *a: None, prompt="p", duration_seconds=duration, aspect_ratio="16:9"
        )


def test_wan_aspect_labels_match_the_space_api():
    # Literal values published by the Space's /generate_video endpoint (view_api, 2026-11-01).
    published = {
        "16:9 (832x480)",
        "9:16 (480x832)",
        "1:1 (640x640)",
        "4:3 (768x576)",
        "3:4 (576x768)",
    }
    labels = {
        WAN_22.build_kwargs("p", duration_seconds=3, aspect_ratio=a, seed=1)["aspect_ratio"]
        for a in ("16:9", "9:16", "1:1", "4:3", "3:4")
    }
    assert labels == published
