"""Vertex AI generative tools: Gemini text, images, Veo 3.1 video (+ polling), ad-copy variants.

Pure builders (``build_*``) construct the request param dict handed to the injected backend
``ReadFn``; the thin ``generate_*`` wrappers do the None-check + structured error envelope and wrap
the returned items in the shared ``{"items", "item_count"}`` envelope. The backend ReadFn signature
is ``(operation, params) -> items`` where operation is one of ``"gemini"`` / ``"imagen"`` / ``"veo"``
/ ``"veo.status"`` (poll a long-running Veo operation and fetch the finished videos).

``build_ad_copy_prompt`` is a pure prompt builder (unit-tested directly): it composes a structured
brief from product + audience + variant count, reused by ``generate_ad_copy`` which then runs a
single Gemini generation.

NOTE: every ``generate_*`` tool incurs Vertex AI generation cost — these are NOT account mutations
and are intentionally not guarded by the WriteExecutor; the operator controls spend.
"""

from __future__ import annotations

from .types import ReadFn

# Operation names passed as the first ReadFn argument (one per modality).
OP_GEMINI = "gemini"
OP_IMAGEN = "imagen"
OP_VEO = "veo"
OP_VEO_STATUS = "veo.status"

# Defaults — conservative model + sizes; the operator can override per call.
DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"
DEFAULT_MAX_TOKENS = 1024
DEFAULT_IMAGE_COUNT = 1
DEFAULT_ASPECT_RATIO = "1:1"
DEFAULT_VIDEO_DURATION_SECONDS = 8
DEFAULT_AD_COPY_VARIANTS = 3

_BACKEND_NOT_CONFIGURED: dict[str, object] = {
    "error": {"code": "BACKEND_NOT_CONFIGURED", "message": "vertex.api not wired"}
}


# --- pure request builders ------------------------------------------------------------------


def build_gemini_request(
    *,
    prompt: str,
    model: str = DEFAULT_GEMINI_MODEL,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> dict[str, object]:
    """Build the Gemini text-generation request params (prompt + model + token budget)."""
    request: dict[str, object] = {
        "prompt": prompt,
        "model": model,
        "max_tokens": max_tokens,
    }
    return request


def build_imagen_request(
    *,
    prompt: str,
    n: int = DEFAULT_IMAGE_COUNT,
    aspect_ratio: str = DEFAULT_ASPECT_RATIO,
    model: str = "",
) -> dict[str, object]:
    """Build the image-generation request params (prompt + count + aspect ratio [+ model]).

    An empty ``model`` lets the backend use its default image model.
    """
    request: dict[str, object] = {
        "prompt": prompt,
        "n": n,
        "aspect_ratio": aspect_ratio,
    }
    if model:
        request["model"] = model
    return request


def build_veo_request(
    *,
    prompt: str,
    duration_seconds: int = DEFAULT_VIDEO_DURATION_SECONDS,
    model: str = "",
) -> dict[str, object]:
    """Build the Veo video-generation request params (prompt + clip duration [+ model]).

    Veo generation is long-running: the backend returns an operation reference to poll, not the
    finished asset inline.
    """
    request: dict[str, object] = {
        "prompt": prompt,
        "duration_seconds": duration_seconds,
    }
    if model:
        request["model"] = model
    return request


def build_veo_status_request(*, operation_name: str) -> dict[str, object]:
    """Build the params to poll a Veo long-running operation (returned by ``generate_veo``)."""
    request: dict[str, object] = {"operation_name": operation_name}
    return request


def build_ad_copy_prompt(product: str, audience: str, n: int) -> str:
    """Compose a structured ad-copy brief asking Gemini for ``n`` distinct variants.

    Pure string builder (no SDK): describes the product, the target audience, and the exact output
    contract (numbered variants, each a headline + body) so the variants come back parseable.
    """
    return (
        "You are a senior advertising copywriter. Write "
        f"{n} distinct ad-copy variants for the following product.\n\n"
        f"Product: {product}\n"
        f"Target audience: {audience}\n\n"
        "Requirements:\n"
        f"- Produce exactly {n} variants, numbered 1 to {n}.\n"
        "- Each variant must have a punchy headline (max 30 characters) and a body line "
        "(max 90 characters).\n"
        "- Tailor tone and angle to the target audience; make each variant meaningfully "
        "different.\n"
        "- Return plain text only, no preamble or commentary."
    )


def _wrap(items: list[dict[str, object]]) -> dict[str, object]:
    """Wrap generated items in the shared generation envelope."""
    return {"items": items, "item_count": len(items)}


# --- tool wrappers against the injected ReadFn ----------------------------------------------


def generate_gemini(
    *,
    prompt: str,
    model: str = DEFAULT_GEMINI_MODEL,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    backend: ReadFn | None,
) -> dict[str, object]:
    """Tool: generate text with Gemini. Incurs Vertex generation cost (operator controls spend)."""
    if backend is None:
        return dict(_BACKEND_NOT_CONFIGURED)
    request = build_gemini_request(prompt=prompt, model=model, max_tokens=max_tokens)
    return _wrap(backend(OP_GEMINI, request))


def generate_imagen(
    *,
    prompt: str,
    n: int = DEFAULT_IMAGE_COUNT,
    aspect_ratio: str = DEFAULT_ASPECT_RATIO,
    model: str = "",
    backend: ReadFn | None,
) -> dict[str, object]:
    """Tool: generate ``n`` images (base64). Incurs Vertex generation cost per image."""
    if backend is None:
        return dict(_BACKEND_NOT_CONFIGURED)
    request = build_imagen_request(prompt=prompt, n=n, aspect_ratio=aspect_ratio, model=model)
    return _wrap(backend(OP_IMAGEN, request))


def generate_veo(
    *,
    prompt: str,
    duration_seconds: int = DEFAULT_VIDEO_DURATION_SECONDS,
    model: str = "",
    backend: ReadFn | None,
) -> dict[str, object]:
    """Tool: generate a video clip with Veo (returns an operation to poll). Incurs Vertex cost."""
    if backend is None:
        return dict(_BACKEND_NOT_CONFIGURED)
    request = build_veo_request(prompt=prompt, duration_seconds=duration_seconds, model=model)
    return _wrap(backend(OP_VEO, request))


def get_veo_status(*, operation_name: str, backend: ReadFn | None) -> dict[str, object]:
    """Tool: poll a Veo operation; once ``done`` it carries the generated video URIs/bytes. Free."""
    if backend is None:
        return dict(_BACKEND_NOT_CONFIGURED)
    request = build_veo_status_request(operation_name=operation_name)
    return _wrap(backend(OP_VEO_STATUS, request))


def generate_ad_copy(
    *,
    product: str,
    audience: str,
    n: int = DEFAULT_AD_COPY_VARIANTS,
    backend: ReadFn | None,
) -> dict[str, object]:
    """Tool: build a structured prompt and ask Gemini for ``n`` ad-copy variants.

    Convenience over ``generate_gemini``: composes the brief via ``build_ad_copy_prompt`` then runs
    one Gemini generation. Incurs Vertex generation cost (operator controls spend).
    """
    if backend is None:
        return dict(_BACKEND_NOT_CONFIGURED)
    prompt = build_ad_copy_prompt(product, audience, n)
    request = build_gemini_request(prompt=prompt)
    return _wrap(backend(OP_GEMINI, request))
