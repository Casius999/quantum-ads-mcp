"""Mount the Cloud Translation + Natural Language tools onto the FastMCP app + register them.

The single backend is keyed ``"language.api"`` (a ``ReadFn`` dispatching translate / detect /
sentiment / entities / batch_translate). It is read lazily per call via ``ctx.backend(...)`` so the
connector degrades gracefully (structured ``BACKEND_NOT_CONFIGURED`` error) when the backend is not
wired.

All five tools are flagged ``read_only=True``: they perform no account mutation and are therefore
NOT guarded by the ``WriteExecutor`` (no validate-only preview / two-step confirm). They DO incur
Cloud Translation / Natural Language API cost — the operator controls spend — which each tool
description documents.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from fastmcp import FastMCP

from ...core.context import ServerContext
from ...core.mcp.register import add_tool
from ...core.registry.registry import Capability, ToolSpec
from . import language_tools
from .types import ReadFn

BACKEND_KEY = "language.api"

_NOT_CONFIGURED: dict[str, object] = {
    "error": {"code": "BACKEND_NOT_CONFIGURED", "message": f"{BACKEND_KEY} not wired"}
}


def register_language(app: FastMCP, ctx: ServerContext) -> None:
    def backend() -> ReadFn | None:
        raw = ctx.backend(BACKEND_KEY)
        if raw is None:
            return None
        return cast(ReadFn, raw)

    def language_translate(
        text: str,
        target_language: str,
        source_language: str = "",
    ) -> dict[str, object]:
        read = backend()
        if read is None:
            return dict(_NOT_CONFIGURED)
        return language_tools.do_translate(
            text=text,
            target_language=target_language,
            source_language=source_language,
            backend=read,
        )

    def language_detect_language(text: str) -> dict[str, object]:
        read = backend()
        if read is None:
            return dict(_NOT_CONFIGURED)
        return language_tools.do_detect_language(text=text, backend=read)

    def language_analyze_sentiment(text: str) -> dict[str, object]:
        read = backend()
        if read is None:
            return dict(_NOT_CONFIGURED)
        return language_tools.do_analyze_sentiment(text=text, backend=read)

    def language_analyze_entities(text: str) -> dict[str, object]:
        read = backend()
        if read is None:
            return dict(_NOT_CONFIGURED)
        return language_tools.do_analyze_entities(text=text, backend=read)

    def language_batch_translate(
        texts: list[str],
        target_language: str,
        source_language: str = "",
    ) -> dict[str, object]:
        read = backend()
        if read is None:
            return dict(_NOT_CONFIGURED)
        return language_tools.do_batch_translate(
            texts=texts,
            target_language=target_language,
            source_language=source_language,
            backend=read,
        )

    tools: list[tuple[str, str, Callable[..., Any]]] = [
        (
            "language.translate",
            "Translate text into a target language (auto-detects source if omitted). "
            "Incurs Cloud Translation API cost.",
            language_translate,
        ),
        (
            "language.detect_language",
            "Detect the dominant language of a text. Incurs Cloud Translation API cost.",
            language_detect_language,
        ),
        (
            "language.analyze_sentiment",
            "Analyze sentiment (score + magnitude) of ad content. "
            "Incurs Cloud Natural Language API cost.",
            language_analyze_sentiment,
        ),
        (
            "language.analyze_entities",
            "Extract salient entities from ad content. Incurs Cloud Natural Language API cost.",
            language_analyze_entities,
        ),
        (
            "language.batch_translate",
            "Translate many texts into a target language in one call for multi-market reach. "
            "Incurs Cloud Translation API cost per text.",
            language_batch_translate,
        ),
    ]
    for name, description, fn in tools:
        add_tool(app, name, description, fn)

    ctx.registry.register(
        Capability(
            connector="language",
            domain="read",
            tools=[ToolSpec(name=name, summary=description) for name, description, _ in tools],
        )
    )
