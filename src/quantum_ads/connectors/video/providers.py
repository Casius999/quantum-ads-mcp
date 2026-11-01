"""Free text-to-video providers (Hugging Face ZeroGPU Spaces) and quota-aware fallback.

No card, no paid credits: these are public Gradio Spaces running on Hugging Face's shared
ZeroGPU pool. The daily GPU quota is per caller — about 2 min anonymous, 5 min with a free
Hugging Face account token (``HF_TOKEN``) — and a Space charges the GPU time it *requests*, so
exhaustion is expected and handled: a quota error moves on to the next provider, and when every
provider is exhausted the tool says so (with the fix) instead of falling back to paid Veo.

Measured November 2026 (anonymous): Wan 2.2 14B — 832x480 @16 fps, ~33 s for 3 s of video, real
motion; LTX-Video distilled (official Lightricks Space) — 704x512 @30 fps, ~12 s, low motion.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

# (space id, api_name, keyword arguments) -> raw Gradio result.
SpaceCall = Callable[[str, str, dict[str, object]], object]

MIN_SECONDS, MAX_SECONDS = 1, 10

_QUOTA_MARKERS = ("zerogpu", "exceeded your", "gpu duration", "quota")

# Exact Literal values of the Space's aspect_ratio input (view_api, 2026-11-01).
_WAN_ASPECTS = {
    "16:9": "16:9 (832x480)",
    "9:16": "9:16 (480x832)",
    "1:1": "1:1 (640x640)",
    "4:3": "4:3 (768x576)",
    "3:4": "3:4 (576x768)",
}
_LTX_SIZES = {  # (width, height), multiples of 32 as the model requires
    "16:9": (704, 512),
    "9:16": (512, 704),
    "1:1": (512, 512),
    "4:3": (640, 480),
    "3:4": (480, 640),
}


def _check_aspect(aspect_ratio: str) -> None:
    if aspect_ratio not in _LTX_SIZES:
        raise ValueError(f"aspect_ratio must be one of {sorted(_LTX_SIZES)}, got {aspect_ratio!r}")


def _wan_kwargs(
    prompt: str, duration_seconds: int, aspect_ratio: str, seed: int | None
) -> dict[str, object]:
    _check_aspect(aspect_ratio)
    return {
        "prompt": prompt,
        "aspect_ratio": _WAN_ASPECTS[aspect_ratio],
        "steps": 4,
        "duration_seconds": duration_seconds,
        "seed": seed if seed is not None else 42,
        "randomize_seed": seed is None,
    }


def _ltx_kwargs(
    prompt: str, duration_seconds: int, aspect_ratio: str, seed: int | None
) -> dict[str, object]:
    _check_aspect(aspect_ratio)
    width, height = _LTX_SIZES[aspect_ratio]
    return {
        "prompt": prompt,
        "negative_prompt": "worst quality, inconsistent motion, blurry, jittery, distorted",
        "input_image_filepath": None,
        "input_video_filepath": None,
        "height_ui": height,
        "width_ui": width,
        "mode": "text-to-video",
        "duration_ui": duration_seconds,
        "ui_frames_to_use": 9,
        "seed_ui": seed if seed is not None else 42,
        "randomize_seed": seed is None,
        "ui_guidance_scale": 1,
        "improve_texture_flag": True,
    }


def _extract_path(result: object) -> str:
    """Gradio returns ``(path, seed)``, ``({"video": path}, seed)`` or a bare path."""
    value = result[0] if isinstance(result, tuple | list) and result else result
    if isinstance(value, dict):
        value = value.get("video") or value.get("path")
    if not isinstance(value, str) or not value:
        raise ValueError(f"unexpected Space result shape: {type(result).__name__}")
    return value


@dataclass(frozen=True)
class VideoProvider:
    name: str
    space: str
    api_name: str
    model: str
    build: Callable[[str, int, str, int | None], dict[str, object]]

    def build_kwargs(
        self, prompt: str, *, duration_seconds: int, aspect_ratio: str, seed: int | None
    ) -> dict[str, object]:
        return self.build(prompt, duration_seconds, aspect_ratio, seed)

    def extract_path(self, result: object) -> str:
        return _extract_path(result)


WAN_22 = VideoProvider(
    name="wan-2.2",
    space="Upsampler/wan-2-2-14b-text-to-video",
    api_name="/generate_video",
    model="Wan 2.2 14B text-to-video",
    build=_wan_kwargs,
)
LTX_VIDEO = VideoProvider(
    name="ltx-video",
    space="Lightricks/ltx-video-distilled",
    api_name="/text_to_video",
    model="LTX-Video distilled",
    build=_ltx_kwargs,
)
PROVIDERS: tuple[VideoProvider, ...] = (WAN_22, LTX_VIDEO)

QUOTA_HINT = (
    "Hugging Face ZeroGPU daily quota exhausted on every free provider (~2 min/day anonymous, "
    "resets 24 h after first use). Set HF_TOKEN to a free Hugging Face account token for "
    "~5 min/day, or retry later. Paid Vertex Veo remains available as vertex.veo.generate."
)


def is_quota_error(message: str) -> bool:
    lowered = message.lower()
    return any(marker in lowered for marker in _QUOTA_MARKERS)


def generate_with_fallback(
    call: SpaceCall,
    *,
    prompt: str,
    duration_seconds: int,
    aspect_ratio: str,
    provider: str = "auto",
    seed: int | None = None,
) -> dict[str, object]:
    """Try providers in order; return the first video path or a structured error."""
    if not MIN_SECONDS <= duration_seconds <= MAX_SECONDS:
        raise ValueError(f"duration_seconds must be {MIN_SECONDS}-{MAX_SECONDS}")
    candidates = (
        PROVIDERS if provider == "auto" else tuple(p for p in PROVIDERS if p.name == provider)
    )
    if not candidates:
        raise ValueError(f"provider must be 'auto' or one of {[p.name for p in PROVIDERS]}")
    attempts: list[dict[str, object]] = []
    for candidate in candidates:
        kwargs = candidate.build_kwargs(
            prompt, duration_seconds=duration_seconds, aspect_ratio=aspect_ratio, seed=seed
        )
        try:
            path = candidate.extract_path(call(candidate.space, candidate.api_name, kwargs))
        except Exception as exc:  # noqa: BLE001 - every Space failure is reported, then skipped
            message = str(exc)
            if is_quota_error(message):
                attempts.append({"provider": candidate.name, "quota_exhausted": True})
            else:
                attempts.append({"provider": candidate.name, "error": message[:300]})
            continue
        return {
            "provider": candidate.name,
            "model": candidate.model,
            "space": candidate.space,
            "path": path,
            "attempts": attempts,
        }
    if attempts and all(a.get("quota_exhausted") for a in attempts):
        return {"error": {"code": "QUOTA_EXHAUSTED", "message": QUOTA_HINT, "attempts": attempts}}
    return {
        "error": {
            "code": "GENERATION_FAILED",
            "message": "every free video provider failed",
            "attempts": attempts,
        }
    }
