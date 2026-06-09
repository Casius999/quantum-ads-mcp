"""Cloud Translation + Natural Language connector: registration, read_only flags, degradation.

All fakes — the real google-cloud-translate / google-cloud-language SDK is never imported. Verifies
the ``{"items", "item_count"}`` envelope, the right operation name + params reach the backend, and a
missing backend yields a structured ``BACKEND_NOT_CONFIGURED`` error rather than raising.
"""

from quantum_ads.connectors.language import language_tools, register_language
from quantum_ads.core.query.runner import StreamFn


def _env() -> dict[str, str]:
    return {
        "GOOGLE_ADS_DEVELOPER_TOKEN": "d",
        "GOOGLE_ADS_CLIENT_ID": "c",
        "GOOGLE_ADS_CLIENT_SECRET": "s",
        "GOOGLE_ADS_REFRESH_TOKEN": "r",
        "QUANTUM_ADS_READ_ONLY": "true",
    }


def _stream(creds: dict[str, object], version: str) -> StreamFn:
    return lambda cid, q: []


def _fake_read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
    return [{"operation": operation, "params": params}]


def _backends() -> dict[str, object]:
    return {"language.api": _fake_read}


# --- registration via register_language -----------------------------------------------------


def test_language_tools_registered():
    from quantum_ads.server import build_server

    assembled = build_server(
        env=_env(),
        stream_factory=_stream,
        backends=_backends(),
        connectors=[register_language],
    )
    names = {t.name for t in assembled.registry.all_tools()}
    assert "language.translate" in names
    assert "language.detect_language" in names
    assert "language.analyze_sentiment" in names
    assert "language.analyze_entities" in names
    assert "language.batch_translate" in names


def test_language_tools_are_read_only():
    from quantum_ads.server import build_server

    assembled = build_server(
        env=_env(),
        stream_factory=_stream,
        backends=_backends(),
        connectors=[register_language],
    )
    for name in (
        "language.translate",
        "language.detect_language",
        "language.analyze_sentiment",
        "language.analyze_entities",
        "language.batch_translate",
    ):
        assert assembled.registry.describe_tool(name).read_only is True


# --- tool wrappers against the fake ReadFn --------------------------------------------------


def test_do_translate_wraps_items_and_passes_request():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["operation"] = operation
        seen["params"] = params
        return [{"translated_text": "Cours plus vite."}]

    out = language_tools.do_translate(text="Run faster.", target_language="fr", backend=read)
    assert out["items"] == [{"translated_text": "Cours plus vite."}]
    assert out["item_count"] == 1
    assert seen["operation"] == language_tools.OP_TRANSLATE
    assert isinstance(seen["params"], dict)
    assert seen["params"]["text"] == "Run faster."
    assert seen["params"]["target_language"] == "fr"


def test_do_translate_forwards_explicit_source_language():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["params"] = params
        return [{"translated_text": "Hola"}]

    language_tools.do_translate(
        text="Hello", target_language="es", source_language="en", backend=read
    )
    assert isinstance(seen["params"], dict)
    assert seen["params"]["source_language"] == "en"


def test_do_detect_language_uses_detect_operation():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["operation"] = operation
        seen["params"] = params
        return [{"language_code": "fr", "confidence": 0.99}]

    out = language_tools.do_detect_language(text="Bonjour le monde", backend=read)
    assert out["item_count"] == 1
    assert seen["operation"] == language_tools.OP_DETECT
    assert isinstance(seen["params"], dict)
    assert seen["params"]["text"] == "Bonjour le monde"


def test_do_analyze_sentiment_uses_sentiment_operation():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["operation"] = operation
        seen["params"] = params
        return [{"score": 0.9, "magnitude": 1.2}]

    out = language_tools.do_analyze_sentiment(text="I love this product!", backend=read)
    assert out["item_count"] == 1
    assert seen["operation"] == language_tools.OP_SENTIMENT
    assert isinstance(seen["params"], dict)
    assert seen["params"]["text"] == "I love this product!"


def test_do_analyze_entities_uses_entities_operation():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["operation"] = operation
        seen["params"] = params
        return [{"name": "Quantum Sneakers", "type": "CONSUMER_GOOD"}]

    out = language_tools.do_analyze_entities(text="Quantum Sneakers are great", backend=read)
    assert out["item_count"] == 1
    assert seen["operation"] == language_tools.OP_ENTITIES
    assert isinstance(seen["params"], dict)
    assert seen["params"]["text"] == "Quantum Sneakers are great"


def test_do_batch_translate_uses_batch_operation_and_passes_texts():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["operation"] = operation
        seen["params"] = params
        return [{"translated_text": "Un"}, {"translated_text": "Deux"}]

    out = language_tools.do_batch_translate(
        texts=["One", "Two"], target_language="fr", backend=read
    )
    assert out["item_count"] == 2
    assert seen["operation"] == language_tools.OP_BATCH_TRANSLATE
    assert isinstance(seen["params"], dict)
    assert seen["params"]["texts"] == ["One", "Two"]
    assert seen["params"]["target_language"] == "fr"


# --- backend-not-configured degradation -----------------------------------------------------


def test_do_translate_backend_not_configured():
    out = language_tools.do_translate(text="x", target_language="fr", backend=None)
    assert isinstance(out["error"], dict)
    assert out["error"]["code"] == "BACKEND_NOT_CONFIGURED"


def test_do_detect_language_backend_not_configured():
    out = language_tools.do_detect_language(text="x", backend=None)
    assert isinstance(out["error"], dict)
    assert out["error"]["code"] == "BACKEND_NOT_CONFIGURED"


def test_do_analyze_sentiment_backend_not_configured():
    out = language_tools.do_analyze_sentiment(text="x", backend=None)
    assert isinstance(out["error"], dict)
    assert out["error"]["code"] == "BACKEND_NOT_CONFIGURED"


def test_do_analyze_entities_backend_not_configured():
    out = language_tools.do_analyze_entities(text="x", backend=None)
    assert isinstance(out["error"], dict)
    assert out["error"]["code"] == "BACKEND_NOT_CONFIGURED"


def test_do_batch_translate_backend_not_configured():
    out = language_tools.do_batch_translate(texts=["x"], target_language="fr", backend=None)
    assert isinstance(out["error"], dict)
    assert out["error"]["code"] == "BACKEND_NOT_CONFIGURED"


def test_read_tools_degrade_when_backend_missing():
    from quantum_ads.server import build_server

    # No backends wired -> ctx.backend("language.api") is None.
    assembled = build_server(
        env=_env(),
        stream_factory=_stream,
        connectors=[register_language],
    )
    names = {t.name for t in assembled.registry.all_tools()}
    assert "language.translate" in names
