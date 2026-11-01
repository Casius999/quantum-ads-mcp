"""Mount the free text-to-video tool (``video.generate``) and register its capability.

Backend keyed ``"video.free"``: a ``SpaceCall`` (space id, api name, kwargs) -> Gradio result,
built by :mod:`.sdk` over ``gradio_client``. Unwired, the tool answers
``BACKEND_NOT_CONFIGURED`` instead of raising.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import cast

from fastmcp import FastMCP

from ...core.context import ServerContext
from ...core.mcp.register import add_tool
from ...core.registry.registry import Capability, ToolSpec
from .providers import SpaceCall, generate_with_fallback

BACKEND_KEY = "video.free"
# Inline base64 is capped so a long clip cannot blow up the MCP response.
MAX_INLINE_BYTES = 20 * 1024 * 1024
_SUMMARY = (
    "Generate a short video from a text prompt for free (Wan 2.2 -> LTX-Video on Hugging Face "
    "ZeroGPU; no billing). Returns the mp4 path (+ base64 on request). Daily GPU quota applies."
)
_NOT_CONFIGURED: dict[str, object] = {
    "error": {"code": "BACKEND_NOT_CONFIGURED", "message": f"{BACKEND_KEY} not wired"}
}


def _with_file(result: dict[str, object], include_base64: bool) -> dict[str, object]:
    if "error" in result:
        return result
    path = Path(str(result["path"]))
    data = path.read_bytes()
    enriched: dict[str, object] = {**result, "path": str(path), "mime_type": "video/mp4"}
    enriched["size_bytes"] = len(data)
    if include_base64:
        if len(data) > MAX_INLINE_BYTES:
            enriched["base64_omitted"] = f"larger than {MAX_INLINE_BYTES} bytes; read the path"
        else:
            enriched["video_base64"] = base64.b64encode(data).decode()
    return enriched


def register_video(app: FastMCP, ctx: ServerContext) -> None:
    def video_generate(
        prompt: str,
        duration_seconds: int = 3,
        aspect_ratio: str = "16:9",
        provider: str = "auto",
        seed: int | None = None,
        include_base64: bool = False,
    ) -> dict[str, object]:
        backend = ctx.backend(BACKEND_KEY)
        if backend is None:
            return dict(_NOT_CONFIGURED)
        try:
            result = generate_with_fallback(
                cast(SpaceCall, backend),
                prompt=prompt,
                duration_seconds=duration_seconds,
                aspect_ratio=aspect_ratio,
                provider=provider,
                seed=seed,
            )
        except ValueError as exc:
            return {"error": {"code": "INVALID_ARGUMENT", "message": str(exc)}}
        return _with_file(result, include_base64)

    add_tool(app, "video.generate", _SUMMARY, video_generate)
    ctx.registry.register(
        Capability(
            connector="video",
            domain="read",
            tools=[ToolSpec(name="video.generate", summary=_SUMMARY)],
        )
    )
