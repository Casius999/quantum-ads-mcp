"""Vertex AI generative connector: the creative-production plane for the ads agency.

Public entry point: :func:`register_vertex` mounts the generation tools onto the FastMCP app.

This is the **creative production** surface, pairing the paid/organic measurement connectors
with content generation: Gemini text (copy/long-form), Imagen 4 images, and Veo 3 video. A
convenience ``vertex.gemini.generate_ad_copy`` tool builds a structured prompt and asks for N
ad-copy variants in one call.

All tools are flagged ``read_only=True``: they perform **no account mutation** and are therefore
NOT guarded by the ``WriteExecutor`` (no validate-only preview / two-step confirm). They DO,
however, incur Vertex AI generation cost — the operator controls spend. Every tool docstring
documents this explicitly.

Single backend, keyed ``"vertex.api"`` (a ``ReadFn``): ``(operation, params) -> generated items``
where operation is one of ``"gemini"`` / ``"imagen"`` / ``"veo"``. When it is not wired the tools
degrade gracefully, returning a structured ``BACKEND_NOT_CONFIGURED`` error rather than raising.
"""

from .connector import register_vertex

__all__ = ["register_vertex"]
