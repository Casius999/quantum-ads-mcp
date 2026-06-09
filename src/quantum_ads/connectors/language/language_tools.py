"""Language tools: translate, detect language, sentiment, entities, batch translate.

Pure builders (``build_*``) construct the request param dict handed to the injected backend
``ReadFn``; the thin ``do_*`` wrappers do the None-check + structured error envelope and wrap the
returned items in the shared ``{"items", "item_count"}`` envelope. The backend ReadFn signature is
``(operation, params) -> items`` where operation is one of ``"translate"`` / ``"detect"`` /
``"sentiment"`` / ``"entities"`` / ``"batch_translate"``.

``build_translate_request`` and ``build_batch_translate_request`` share the same ``target_language``
+ optional ``source_language`` contract (empty ``source_language`` means "auto-detect", omitted from
the params so the backend lets the API infer it).

NOTE: every ``do_*`` tool incurs Cloud Translation / Natural Language API cost — these are NOT
account mutations and are intentionally not guarded by the WriteExecutor; the operator controls
spend.
"""

from __future__ import annotations

from .types import ReadFn

# Operation names passed as the first ReadFn argument (one per call).
OP_TRANSLATE = "translate"
OP_DETECT = "detect"
OP_SENTIMENT = "sentiment"
OP_ENTITIES = "entities"
OP_BATCH_TRANSLATE = "batch_translate"

_BACKEND_NOT_CONFIGURED: dict[str, object] = {
    "error": {"code": "BACKEND_NOT_CONFIGURED", "message": "language.api not wired"}
}


# --- pure request builders ------------------------------------------------------------------


def build_translate_request(
    *,
    text: str,
    target_language: str,
    source_language: str = "",
) -> dict[str, object]:
    """Build the single-text translation request params.

    ``target_language`` is an ISO-639 code (e.g. ``"fr"``). An empty ``source_language`` means
    "auto-detect": the key is omitted so the backend lets the API infer the source.
    """
    request: dict[str, object] = {
        "text": text,
        "target_language": target_language,
    }
    if source_language:
        request["source_language"] = source_language
    return request


def build_detect_language_request(*, text: str) -> dict[str, object]:
    """Build the language-detection request params (just the text to inspect)."""
    request: dict[str, object] = {"text": text}
    return request


def build_sentiment_request(*, text: str) -> dict[str, object]:
    """Build the sentiment-analysis request params (the text to score)."""
    request: dict[str, object] = {"text": text}
    return request


def build_entities_request(*, text: str) -> dict[str, object]:
    """Build the entity-analysis request params (the text to extract salient entities from)."""
    request: dict[str, object] = {"text": text}
    return request


def build_batch_translate_request(
    *,
    texts: list[str],
    target_language: str,
    source_language: str = "",
) -> dict[str, object]:
    """Build the batch translation request params (many texts, one target language).

    Same ``target_language`` + optional ``source_language`` contract as the single-text builder:
    an empty ``source_language`` is omitted so the API auto-detects each text's source.
    """
    request: dict[str, object] = {
        "texts": texts,
        "target_language": target_language,
    }
    if source_language:
        request["source_language"] = source_language
    return request


def _wrap(items: list[dict[str, object]]) -> dict[str, object]:
    """Wrap result items in the shared language envelope."""
    return {"items": items, "item_count": len(items)}


# --- tool wrappers against the injected ReadFn ----------------------------------------------


def do_translate(
    *,
    text: str,
    target_language: str,
    source_language: str = "",
    backend: ReadFn | None,
) -> dict[str, object]:
    """Tool: translate ``text`` into ``target_language``. Incurs Translation API cost."""
    if backend is None:
        return dict(_BACKEND_NOT_CONFIGURED)
    request = build_translate_request(
        text=text, target_language=target_language, source_language=source_language
    )
    return _wrap(backend(OP_TRANSLATE, request))


def do_detect_language(
    *,
    text: str,
    backend: ReadFn | None,
) -> dict[str, object]:
    """Tool: detect the dominant language of ``text``. Incurs Translation API cost."""
    if backend is None:
        return dict(_BACKEND_NOT_CONFIGURED)
    request = build_detect_language_request(text=text)
    return _wrap(backend(OP_DETECT, request))


def do_analyze_sentiment(
    *,
    text: str,
    backend: ReadFn | None,
) -> dict[str, object]:
    """Tool: analyze sentiment (score + magnitude) of ``text``. Incurs Natural Language API cost."""
    if backend is None:
        return dict(_BACKEND_NOT_CONFIGURED)
    request = build_sentiment_request(text=text)
    return _wrap(backend(OP_SENTIMENT, request))


def do_analyze_entities(
    *,
    text: str,
    backend: ReadFn | None,
) -> dict[str, object]:
    """Tool: extract salient entities from ``text``. Incurs Natural Language API cost."""
    if backend is None:
        return dict(_BACKEND_NOT_CONFIGURED)
    request = build_entities_request(text=text)
    return _wrap(backend(OP_ENTITIES, request))


def do_batch_translate(
    *,
    texts: list[str],
    target_language: str,
    source_language: str = "",
    backend: ReadFn | None,
) -> dict[str, object]:
    """Tool: translate many ``texts`` into ``target_language`` in one call. Incurs Translation cost."""
    if backend is None:
        return dict(_BACKEND_NOT_CONFIGURED)
    request = build_batch_translate_request(
        texts=texts, target_language=target_language, source_language=source_language
    )
    return _wrap(backend(OP_BATCH_TRANSLATE, request))
