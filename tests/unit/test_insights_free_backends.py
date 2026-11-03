"""Free creative backends: OpenAI-compatible chat and FLUX on Hugging Face (network faked)."""

from __future__ import annotations

import base64
import io
import json
import sys
import types
from pathlib import Path

import pytest

from quantum_ads.backends import build_backends
from quantum_ads.connectors.insights import sdk


class _Response(io.BytesIO):
    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def test_chat_posts_openai_payload_with_bearer(monkeypatch: pytest.MonkeyPatch):
    seen: dict[str, object] = {}

    def fake_urlopen(request, timeout):  # type: ignore[no-untyped-def]
        seen.update(url=request.full_url, auth=request.get_header("Authorization"))
        seen["body"] = json.loads(request.data)
        return _Response(
            json.dumps({"choices": [{"message": {"content": "hi"}}], "model": "m"}).encode()
        )

    monkeypatch.setattr(sdk.urllib.request, "urlopen", fake_urlopen)
    read = sdk.openai_chat_factory({"base_url": "https://x/v1/", "api_key": "k", "model": "m"}, "")
    assert read("chat", {"prompt": "p", "max_tokens": 10}) == [{"text": "hi", "model": "m"}]
    assert seen["url"] == "https://x/v1/chat/completions" and seen["auth"] == "Bearer k"
    assert seen["body"]["messages"] == [{"role": "user", "content": "p"}]  # type: ignore[index]
    with pytest.raises(ValueError):
        read("embed", {})


def test_keyless_chat_sends_no_authorization(monkeypatch: pytest.MonkeyPatch):
    headers: list[object] = []

    def fake_urlopen(request, timeout):  # type: ignore[no-untyped-def]
        headers.append(request.get_header("Authorization"))
        return _Response(json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode())

    monkeypatch.setattr(sdk.urllib.request, "urlopen", fake_urlopen)
    read = sdk.openai_chat_factory({"base_url": "https://x/v1", "model": "m"}, "")
    assert read("chat", {"prompt": "p"})[0]["model"] == "m"
    assert headers == [None]


def test_flux_image_reads_generated_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    image = tmp_path / "out.webp"
    image.write_bytes(b"IMG")
    calls: list[dict[str, object]] = []

    class FakeClient:
        def __init__(self, space: str, token: str | None, verbose: bool) -> None:
            assert space == sdk.FLUX_SPACE and token == "hf"

        def predict(self, **kwargs: object) -> tuple[object, int]:
            calls.append(kwargs)
            return ({"path": str(image)}, 42)

    monkeypatch.setitem(sys.modules, "gradio_client", types.SimpleNamespace(Client=FakeClient))
    read = sdk.free_image_factory({"hf_token": "hf"}, "")
    out = read("image", {"prompt": "a shoe", "width": 1216, "height": 640})
    assert base64.b64decode(out[0]["image_base64"]) == b"IMG"  # type: ignore[arg-type]
    assert calls[0]["width"] == 1216 and calls[0]["api_name"] == "/infer"
    read("image", {"prompt": "again"})  # client is built once and reused
    with pytest.raises(ValueError):
        read("video", {})


def test_llm_backend_is_wired_only_with_a_base_url():
    assert "llm.chat" not in build_backends({})
    assert "image.free" in build_backends({})  # public Space, token optional
    assert "llm.chat" in build_backends({"QUANTUM_ADS_LLM_BASE_URL": "https://x/v1"})


def test_chat_waits_out_rate_limits_then_gives_up(monkeypatch: pytest.MonkeyPatch):
    import urllib.error
    from email.message import Message

    def limited(after: str) -> urllib.error.HTTPError:
        headers = Message()
        headers["Retry-After"] = after
        return urllib.error.HTTPError("u", 429, "Too Many Requests", headers, None)

    responses: list[object] = [
        limited("1"),
        limited("soon"),
        _Response(json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode()),
    ]
    sleeps: list[float] = []

    def fake_urlopen(request, timeout):  # type: ignore[no-untyped-def]
        item = responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(sdk.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(sdk.time, "sleep", sleeps.append)
    read = sdk.openai_chat_factory({"base_url": "https://x", "model": "m"}, "")
    assert read("chat", {"prompt": "p"})[0]["text"] == "ok"
    assert sleeps == [1.0, 30.0]
    responses[:] = [limited("1"), limited("1"), limited("1")]
    with pytest.raises(urllib.error.HTTPError):
        read("chat", {"prompt": "p"})
    responses[:] = [urllib.error.HTTPError("u", 500, "boom", Message(), None)]
    with pytest.raises(urllib.error.HTTPError):
        read("chat", {"prompt": "p"})


def test_openai_images_request_b64_at_the_asked_size(monkeypatch: pytest.MonkeyPatch):
    bodies: list[dict[str, object]] = []

    def fake_urlopen(request, timeout):  # type: ignore[no-untyped-def]
        assert request.full_url == "https://x/v1/images/generations"
        assert request.get_header("Authorization") is None
        bodies.append(json.loads(request.data))
        return _Response(json.dumps({"data": [{"b64_json": "QUJD"}]}).encode())

    monkeypatch.setattr(sdk.urllib.request, "urlopen", fake_urlopen)
    read = sdk.openai_image_factory({"base_url": "https://x/v1", "image_model": "sdxl"}, "")
    out = read("image", {"prompt": "shoes", "width": 1344, "height": 768})
    assert out == [{"image_base64": "QUJD", "provider": "sdxl"}]
    assert bodies[0]["size"] == "1344x768" and bodies[0]["response_format"] == "b64_json"
    with pytest.raises(ValueError, match="unsupported"):
        read("video", {})
    keyed = sdk.openai_image_factory({"base_url": "https://x/v1", "api_key": "k"}, "")
    with pytest.raises(ValueError, match="QUANTUM_ADS_IMAGE_MODEL"):
        keyed("image", {"prompt": "p"})
