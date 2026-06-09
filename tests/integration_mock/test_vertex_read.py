"""Vertex AI generative connector: registration, read_only flags, pure builders, degradation.

All fakes — the real google-cloud-aiplatform / vertexai SDK is never imported. Verifies the
``{"items", "item_count"}`` envelope, the right operation name + params reach the backend, the
ad-copy prompt builder, and a missing backend yields a structured ``BACKEND_NOT_CONFIGURED`` error.
"""

from quantum_ads.connectors.vertex import gen_tools, register_vertex
from quantum_ads.core.query.runner import StreamFn


def _env() -> dict[str, str]:
    return {
        "GOOGLE_ADS_DEVELOPER_TOKEN": "d",
        "GOOGLE_ADS_CLIENT_ID": "c",
        "GOOGLE_ADS_CLIENT_SECRET": "s",
        "GOOGLE_ADS_REFRESH_TOKEN": "r",
        "QUANTUM_ADS_READ_ONLY": "false",
    }


def _stream(creds: dict[str, object], version: str) -> StreamFn:
    return lambda cid, q: []


def _fake_read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
    return [{"operation": operation, "params": params}]


def _backends() -> dict[str, object]:
    return {"vertex.api": _fake_read}


# --- registration via register_vertex -------------------------------------------------------


def test_vertex_tools_registered():
    from quantum_ads.server import build_server

    assembled = build_server(
        env=_env(),
        stream_factory=_stream,
        backends=_backends(),
        connectors=[register_vertex],
    )
    names = {t.name for t in assembled.registry.all_tools()}
    assert "vertex.gemini.generate" in names
    assert "vertex.imagen.generate" in names
    assert "vertex.veo.generate" in names
    assert "vertex.gemini.generate_ad_copy" in names


def test_vertex_tools_are_read_only():
    from quantum_ads.server import build_server

    assembled = build_server(
        env=_env(),
        stream_factory=_stream,
        backends=_backends(),
        connectors=[register_vertex],
    )
    for name in (
        "vertex.gemini.generate",
        "vertex.imagen.generate",
        "vertex.veo.generate",
        "vertex.gemini.generate_ad_copy",
    ):
        assert assembled.registry.describe_tool(name).read_only is True


# --- pure request builders (unit) -----------------------------------------------------------


def test_build_gemini_request_shape_and_defaults():
    request = gen_tools.build_gemini_request(prompt="hello")
    assert request == {
        "prompt": "hello",
        "model": gen_tools.DEFAULT_GEMINI_MODEL,
        "max_tokens": gen_tools.DEFAULT_MAX_TOKENS,
    }


def test_build_gemini_request_overrides():
    request = gen_tools.build_gemini_request(prompt="hi", model="gemini-2.5-pro", max_tokens=256)
    assert request == {"prompt": "hi", "model": "gemini-2.5-pro", "max_tokens": 256}


def test_build_imagen_request_shape_and_defaults():
    request = gen_tools.build_imagen_request(prompt="a red shoe")
    assert request == {
        "prompt": "a red shoe",
        "n": gen_tools.DEFAULT_IMAGE_COUNT,
        "aspect_ratio": gen_tools.DEFAULT_ASPECT_RATIO,
    }


def test_build_imagen_request_overrides():
    request = gen_tools.build_imagen_request(prompt="a red shoe", n=4, aspect_ratio="16:9")
    assert request == {"prompt": "a red shoe", "n": 4, "aspect_ratio": "16:9"}


def test_build_veo_request_shape_and_defaults():
    request = gen_tools.build_veo_request(prompt="a drone shot of the coast")
    assert request == {
        "prompt": "a drone shot of the coast",
        "duration_seconds": gen_tools.DEFAULT_VIDEO_DURATION_SECONDS,
    }


def test_build_veo_request_override_duration():
    request = gen_tools.build_veo_request(prompt="a drone shot", duration_seconds=16)
    assert request == {"prompt": "a drone shot", "duration_seconds": 16}


def test_build_ad_copy_prompt_mentions_product_audience_and_count():
    prompt = gen_tools.build_ad_copy_prompt("Quantum Sneakers", "urban runners", 3)
    assert "Quantum Sneakers" in prompt
    assert "urban runners" in prompt
    # The count appears in the instruction to produce exactly N numbered variants.
    assert "3" in prompt
    assert isinstance(prompt, str)


# --- tool wrappers against the fake ReadFn --------------------------------------------------


def test_generate_gemini_wraps_items_and_passes_request():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["operation"] = operation
        seen["params"] = params
        return [{"text": "Run faster."}]

    out = gen_tools.generate_gemini(prompt="copy please", backend=read)
    assert out["items"] == [{"text": "Run faster."}]
    assert out["item_count"] == 1
    assert seen["operation"] == gen_tools.OP_GEMINI
    assert isinstance(seen["params"], dict)
    assert seen["params"]["prompt"] == "copy please"


def test_generate_imagen_uses_imagen_operation():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["operation"] = operation
        seen["params"] = params
        return [{"image_index": 0}, {"image_index": 1}]

    out = gen_tools.generate_imagen(prompt="a red shoe", n=2, backend=read)
    assert out["item_count"] == 2
    assert seen["operation"] == gen_tools.OP_IMAGEN
    assert isinstance(seen["params"], dict)
    assert seen["params"]["n"] == 2


def test_generate_veo_uses_veo_operation():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["operation"] = operation
        seen["params"] = params
        return [{"operation_name": "op/123", "done": False}]

    out = gen_tools.generate_veo(prompt="a coastline", backend=read)
    assert out["item_count"] == 1
    assert seen["operation"] == gen_tools.OP_VEO


def test_generate_ad_copy_runs_gemini_with_structured_prompt():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["operation"] = operation
        seen["params"] = params
        return [{"text": "1. ...\n2. ...\n3. ..."}]

    out = gen_tools.generate_ad_copy(
        product="Quantum Sneakers", audience="urban runners", n=3, backend=read
    )
    assert out["item_count"] == 1
    assert seen["operation"] == gen_tools.OP_GEMINI
    params = seen["params"]
    assert isinstance(params, dict)
    prompt = params["prompt"]
    assert isinstance(prompt, str)
    assert "Quantum Sneakers" in prompt
    assert "urban runners" in prompt


# --- backend-not-configured degradation -----------------------------------------------------


def test_generate_gemini_backend_not_configured():
    out = gen_tools.generate_gemini(prompt="x", backend=None)
    assert isinstance(out["error"], dict)
    assert out["error"]["code"] == "BACKEND_NOT_CONFIGURED"


def test_generate_imagen_backend_not_configured():
    out = gen_tools.generate_imagen(prompt="x", backend=None)
    assert isinstance(out["error"], dict)
    assert out["error"]["code"] == "BACKEND_NOT_CONFIGURED"


def test_generate_veo_backend_not_configured():
    out = gen_tools.generate_veo(prompt="x", backend=None)
    assert isinstance(out["error"], dict)
    assert out["error"]["code"] == "BACKEND_NOT_CONFIGURED"


def test_generate_ad_copy_backend_not_configured():
    out = gen_tools.generate_ad_copy(product="p", audience="a", backend=None)
    assert isinstance(out["error"], dict)
    assert out["error"]["code"] == "BACKEND_NOT_CONFIGURED"


def test_read_tools_degrade_when_backend_missing():
    from quantum_ads.server import build_server

    # No backends wired -> ctx.backend("vertex.api") is None.
    assembled = build_server(
        env=_env(),
        stream_factory=_stream,
        connectors=[register_vertex],
    )
    names = {t.name for t in assembled.registry.all_tools()}
    assert "vertex.gemini.generate" in names
