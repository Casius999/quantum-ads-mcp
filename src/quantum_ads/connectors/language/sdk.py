"""Live boundary — smoke-gated, not unit-tested.

Real Cloud Translation + Natural Language SDK glue: a lazy factory building the ReadFn dispatching
the five operations (translate / detect / sentiment / entities / batch_translate). Isolated at the
untyped third-party boundary (``google.cloud.*`` is mypy-ignored; this module is coverage-omitted
via the live gate). Imports are local so importing this module stays cheap and credential-free.
SDK-derived values stay implicitly typed (``Any``) — they are never annotated, mirroring the other
connector SDK boundaries.

Auth mirrors the other Cloud connectors: the Translation / Natural Language clients use Application
Default Credentials (ADC) plus a GCP project, derived here from the shared creds dict (``project``
key). Translation calls are scoped to ``projects/{project}/locations/global``.

Python packages: ``google-cloud-translate`` (the ``google.cloud.translate`` namespace) and
``google-cloud-language`` (the ``google.cloud.language`` namespace).
"""

from __future__ import annotations

from collections.abc import Callable

ReadFn = Callable[[str, dict[str, object]], list[dict[str, object]]]

# Translation v3 scopes requests to a parent resource; "global" is the multi-region default.
_TRANSLATE_LOCATION = "global"


def language_read_factory(creds: dict[str, object], version: str) -> ReadFn:
    """Build the language ReadFn dispatching translate / detect / sentiment / entities ops."""
    from google.cloud import language_v2, translate_v3

    project = str(creds["project"])
    parent = f"projects/{project}/locations/{_TRANSLATE_LOCATION}"
    translate_client = translate_v3.TranslationServiceClient()
    language_client = language_v2.LanguageServiceClient()

    def _document(text: str) -> dict[str, object]:
        return {"content": text, "type_": language_v2.Document.Type.PLAIN_TEXT}

    def _translate(params: dict[str, object]) -> list[dict[str, object]]:
        request: dict[str, object] = {
            "parent": parent,
            "contents": [str(params["text"])],
            "target_language_code": str(params["target_language"]),
            "mime_type": "text/plain",
        }
        source = params.get("source_language")
        if source:
            request["source_language_code"] = str(source)
        response = translate_client.translate_text(request=request)
        return [
            {
                "translated_text": t.translated_text,
                "detected_language_code": t.detected_language_code,
            }
            for t in response.translations
        ]

    def _detect(params: dict[str, object]) -> list[dict[str, object]]:
        response = translate_client.detect_language(
            request={
                "parent": parent,
                "content": str(params["text"]),
                "mime_type": "text/plain",
            }
        )
        return [
            {"language_code": lang.language_code, "confidence": lang.confidence}
            for lang in response.languages
        ]

    def _sentiment(params: dict[str, object]) -> list[dict[str, object]]:
        response = language_client.analyze_sentiment(
            request={"document": _document(str(params["text"]))}
        )
        sentiment = response.document_sentiment
        return [{"score": sentiment.score, "magnitude": sentiment.magnitude}]

    def _entities(params: dict[str, object]) -> list[dict[str, object]]:
        response = language_client.analyze_entities(
            request={"document": _document(str(params["text"]))}
        )
        return [{"name": entity.name, "type": entity.type_.name} for entity in response.entities]

    def _batch_translate(params: dict[str, object]) -> list[dict[str, object]]:
        raw_texts = params["texts"]
        texts = raw_texts if isinstance(raw_texts, list) else [raw_texts]
        contents = [str(t) for t in texts]
        request: dict[str, object] = {
            "parent": parent,
            "contents": contents,
            "target_language_code": str(params["target_language"]),
            "mime_type": "text/plain",
        }
        source = params.get("source_language")
        if source:
            request["source_language_code"] = str(source)
        response = translate_client.translate_text(request=request)
        return [
            {
                "translated_text": t.translated_text,
                "detected_language_code": t.detected_language_code,
            }
            for t in response.translations
        ]

    handlers: dict[str, Callable[[dict[str, object]], list[dict[str, object]]]] = {
        "translate": _translate,
        "detect": _detect,
        "sentiment": _sentiment,
        "entities": _entities,
        "batch_translate": _batch_translate,
    }

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        handler = handlers.get(operation)
        if handler is None:
            raise ValueError(f"unsupported language operation: {operation!r}")
        return handler(params)

    return read
