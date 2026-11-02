"""Long-running tools run as MCP background tasks when QUANTUM_ADS_TASKS=true."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastmcp import Client

from quantum_ads.connectors.video import register_video
from quantum_ads.core.mcp.register import LONG_RUNNING
from quantum_ads.core.query.runner import StreamFn
from quantum_ads.server import build_server

pytest.importorskip("fastmcp_tasks")

_ENV = {
    "GOOGLE_ADS_DEVELOPER_TOKEN": "d",
    "GOOGLE_ADS_CLIENT_ID": "c",
    "GOOGLE_ADS_CLIENT_SECRET": "s",
    "GOOGLE_ADS_REFRESH_TOKEN": "r",
}


def _stream(creds: dict[str, object], version: str) -> StreamFn:
    return lambda customer_id, query: []


def _server(tmp_path: Path, tasks: bool):  # type: ignore[no-untyped-def]
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"\x00\x00\x00\x18ftypisom" + b"\x00" * 64)
    env = {**_ENV, **({"QUANTUM_ADS_TASKS": "true"} if tasks else {})}
    return build_server(
        env=env,
        stream_factory=_stream,
        connectors=[register_video],
        backends={"video.free": lambda space, api, kwargs: (str(clip), 1)},
    ).app


def test_long_running_tool_runs_as_a_task(tmp_path: Path):
    from fastmcp_tasks.client import call_tool_task

    app = _server(tmp_path, tasks=True)

    async def scenario() -> tuple[str, object]:
        async with Client(app) as client:
            handle = await call_tool_task(client, "video.generate", {"prompt": "car"})
            first = (await handle.status()).status
            result = await handle.result()
            return first, result.structured_content

    first, content = asyncio.run(scenario())
    assert first in {"working", "completed"}
    assert isinstance(content, dict) and content["provider"] == "wan-2.2"


def test_task_tools_stay_transparent_to_plain_calls(tmp_path: Path):
    app = _server(tmp_path, tasks=True)

    async def scenario() -> object:
        async with Client(app) as client:
            return (await client.call_tool("video.generate", {"prompt": "car"})).structured_content

    content = asyncio.run(scenario())
    assert isinstance(content, dict) and content["size_bytes"] > 0


def test_long_running_tools_have_timeouts_even_without_tasks(tmp_path: Path):
    app = _server(tmp_path, tasks=False)

    async def scenario() -> object:
        tool = await app.get_tool("video.generate")
        return tool.timeout if tool is not None else None

    assert asyncio.run(scenario()) == LONG_RUNNING["video.generate"]
