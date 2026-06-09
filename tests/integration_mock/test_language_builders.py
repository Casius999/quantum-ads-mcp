"""Pure request-builder unit tests for the Cloud Translation + Natural Language connector.

No SDK, no server: exercises the ``build_*`` helpers directly to pin their param-dict shapes and
the shared ``target_language`` / optional ``source_language`` (auto-detect) contract.
"""

from quantum_ads.connectors.language import language_tools


def test_build_translate_request_shape_and_auto_detect_default():
    request = language_tools.build_translate_request(text="hello", target_language="fr")
    # Empty source_language -> auto-detect: the key is omitted entirely.
    assert request == {"text": "hello", "target_language": "fr"}


def test_build_translate_request_includes_source_when_given():
    request = language_tools.build_translate_request(
        text="hello", target_language="fr", source_language="en"
    )
    assert request == {"text": "hello", "target_language": "fr", "source_language": "en"}


def test_build_detect_language_request_shape():
    request = language_tools.build_detect_language_request(text="Bonjour")
    assert request == {"text": "Bonjour"}


def test_build_sentiment_request_shape():
    request = language_tools.build_sentiment_request(text="I love it")
    assert request == {"text": "I love it"}


def test_build_entities_request_shape():
    request = language_tools.build_entities_request(text="Acme Corp ships shoes")
    assert request == {"text": "Acme Corp ships shoes"}


def test_build_batch_translate_request_shape_and_auto_detect_default():
    request = language_tools.build_batch_translate_request(
        texts=["one", "two"], target_language="es"
    )
    assert request == {"texts": ["one", "two"], "target_language": "es"}


def test_build_batch_translate_request_includes_source_when_given():
    request = language_tools.build_batch_translate_request(
        texts=["one"], target_language="es", source_language="en"
    )
    assert request == {"texts": ["one"], "target_language": "es", "source_language": "en"}


def test_operation_constants_are_stable():
    assert language_tools.OP_TRANSLATE == "translate"
    assert language_tools.OP_DETECT == "detect"
    assert language_tools.OP_SENTIMENT == "sentiment"
    assert language_tools.OP_ENTITIES == "entities"
    assert language_tools.OP_BATCH_TRANSLATE == "batch_translate"
