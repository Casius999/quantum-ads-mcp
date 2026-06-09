"""Mount the Vertex AI generative tools onto the FastMCP app + register their capabilities.

The single backend is keyed ``"vertex.api"`` (a ``ReadFn`` dispatching gemini/imagen/veo). It is
read lazily per call via ``ctx.backend(...)`` so the connector degrades gracefully (structured
``BACKEND_NOT_CONFIGURED`` error) when the backend is not wired.

All four tools are flagged ``read_only=True``: they perform no account mutation and are therefore
NOT guarded by the ``WriteExecutor`` (no validate-only preview / two-step confirm). They DO incur
Vertex AI generation cost — the operator controls spend — which each tool description documents.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from fastmcp import FastMCP

from ...core.context import ServerContext
from ...core.mcp.register import add_tool
from ...core.registry.registry import Capability, ToolSpec
from . import gen_tools
from .types import ReadFn

BACKEND_KEY = "vertex.api"

_NOT_CONFIGURED: dict[str, object] = {
    "error": {"code": "BACKEND_NOT_CONFIGURED", "message": f"{BACKEND_KEY} not wired"}
}


def register_vertex(app: FastMCP, ctx: ServerContext) -> None:
    def backend() -> ReadFn | None:
        raw = ctx.backend(BACKEND_KEY)
        if raw is None:
            return None
        return cast(ReadFn, raw)

    def vertex_gemini_generate(
        prompt: str,
        model: str = gen_tools.DEFAULT_GEMINI_MODEL,
        max_tokens: int = gen_tools.DEFAULT_MAX_TOKENS,
    ) -> dict[str, object]:
        read = backend()
        if read is None:
            return dict(_NOT_CONFIGURED)
        return gen_tools.generate_gemini(
            prompt=prompt, model=model, max_tokens=max_tokens, backend=read
        )

    def vertex_imagen_generate(
        prompt: str,
        n: int = gen_tools.DEFAULT_IMAGE_COUNT,
        aspect_ratio: str = gen_tools.DEFAULT_ASPECT_RATIO,
    ) -> dict[str, object]:
        read = backend()
        if read is None:
            return dict(_NOT_CONFIGURED)
        return gen_tools.generate_imagen(
            prompt=prompt, n=n, aspect_ratio=aspect_ratio, backend=read
        )

    def vertex_veo_generate(
        prompt: str,
        duration_seconds: int = gen_tools.DEFAULT_VIDEO_DURATION_SECONDS,
    ) -> dict[str, object]:
        read = backend()
        if read is None:
            return dict(_NOT_CONFIGURED)
        return gen_tools.generate_veo(
            prompt=prompt, duration_seconds=duration_seconds, backend=read
        )

    def vertex_gemini_generate_ad_copy(
        product: str,
        audience: str,
        n: int = gen_tools.DEFAULT_AD_COPY_VARIANTS,
    ) -> dict[str, object]:
        read = backend()
        if read is None:
            return dict(_NOT_CONFIGURED)
        return gen_tools.generate_ad_copy(product=product, audience=audience, n=n, backend=read)

    tools: list[tuple[str, str, Callable[..., Any]]] = [
        (
            "vertex.gemini.generate",
            "Generate text with Gemini (creative copy/long-form). Incurs Vertex generation cost.",
            vertex_gemini_generate,
        ),
        (
            "vertex.imagen.generate",
            "Generate n images with Imagen 4. Incurs Vertex generation cost per image.",
            vertex_imagen_generate,
        ),
        (
            "vertex.veo.generate",
            "Generate a video clip with Veo 3 (returns an op ref to poll). Incurs Vertex cost.",
            vertex_veo_generate,
        ),
        (
            "vertex.gemini.generate_ad_copy",
            "Build a structured brief and ask Gemini for n ad-copy variants. Incurs Vertex cost.",
            vertex_gemini_generate_ad_copy,
        ),
    ]
    for name, description, fn in tools:
        add_tool(app, name, description, fn)

    ctx.registry.register(
        Capability(
            connector="vertex",
            domain="read",
            tools=[ToolSpec(name=name, summary=description) for name, description, _ in tools],
        )
    )
