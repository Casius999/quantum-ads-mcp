"""video.generate over a real MCP client, with a fake Space backend."""

from __future__ import annotations

import asyncio
import base64
from pathlib import Path

from fastmcp import Client

from quantum_ads.connectors.video import register_video
from quantum_ads.core.query.runner import StreamFn
from quantum_ads.server import build_server

_ENV = {
    "GOOGLE_ADS_DEVELOPER_TOKEN": "d",
    "GOOGLE_ADS_CLIENT_ID": "c",
    "GOOGLE_ADS_CLIENT_SECRET": "s",
    "GOOGLE_ADS_REFRESH_TOKEN": "r",
}


def _stream(creds: dict[str, object], version: str) -> StreamFn:
    return lambda customer_id, query: []


def _call(backends: dict[str, object], args: dict[str, object]) -> dict[str, object]:
    app = build_server(
        env=_ENV, stream_factory=_stream, connectors=[register_video], backends=backends
    ).app

    async def scenario() -> dict[str, object]:
        async with Client(app) as client:
            result = await client.call_tool("video.generate", args)
            assert isinstance(result.structured_content, dict)
            return result.structured_content

    return asyncio.run(scenario())


def test_generates_with_the_first_provider_and_inlines_on_request(tmp_path: Path):
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"\x00\x00\x00\x18ftypmp42fake")
    seen: list[str] = []

    def space(space_id: str, api_name: str, kwargs: dict[str, object]) -> object:
        seen.append(f"{space_id}{api_name}")
        return (str(clip), 7)

    result = _call({"video.free": space}, {"prompt": "red car", "include_base64": True})
    assert result["provider"] == "wan-2.2"
    assert result["size_bytes"] == clip.stat().st_size
    assert base64.b64decode(str(result["video_base64"])) == clip.read_bytes()
    assert seen == ["Upsampler/wan-2-2-14b-text-to-video/generate_video"]


def test_quota_exhaustion_is_reported_not_raised():
    def space(space_id: str, api_name: str, kwargs: dict[str, object]) -> object:
        raise RuntimeError("You have exceeded your ZeroGPU quota")

    result = _call({"video.free": space}, {"prompt": "red car"})
    assert result["error"]["code"] == "QUOTA_EXHAUSTED"  # type: ignore[index]


def test_invalid_arguments_are_a_structured_error():
    result = _call({"video.free": lambda *a: None}, {"prompt": "x", "aspect_ratio": "21:9"})
    assert result["error"]["code"] == "INVALID_ARGUMENT"  # type: ignore[index]


def test_unwired_backend():
    assert _call({}, {"prompt": "x"})["error"]["code"] == "BACKEND_NOT_CONFIGURED"  # type: ignore[index]
