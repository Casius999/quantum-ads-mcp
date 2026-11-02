"""Progressive disclosure: with QUANTUM_ADS_TOOL_SEARCH the catalog collapses to search + call."""

from __future__ import annotations

import asyncio
import json

from fastmcp import Client

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


def _run(env: dict[str, str]) -> tuple[list[str], str, object]:
    app = build_server(env={**_ENV, **env}, stream_factory=_stream).app

    async def scenario() -> tuple[list[str], str, object]:
        async with Client(app) as client:
            names = [tool.name for tool in await client.list_tools()]
            found = await client.call_tool("search_tools", {"query": "update campaign budget"})
            called = await client.call_tool("call_tool", {"name": "health", "arguments": {}})
            return names, json.dumps(found.structured_content or str(found.content)), called

    return asyncio.run(scenario())


def test_search_mode_exposes_a_small_catalog_and_finds_hidden_tools():
    names, found, called = _run({"QUANTUM_ADS_TOOL_SEARCH": "true"})
    assert set(names) == {
        "search_tools",
        "call_tool",
        "health",
        "list_capabilities",
        "describe_tool",
    }
    assert "ads.budget.update" in found
    assert "api_version" in json.dumps(getattr(called, "structured_content", None) or str(called))


def test_default_lists_every_tool():
    app = build_server(env=_ENV, stream_factory=_stream).app

    async def scenario() -> int:
        async with Client(app) as client:
            return len(await client.list_tools())

    assert asyncio.run(scenario()) >= 131
