"""End-to-end MCP protocol test: the fully assembled server driven by a real MCP client.

Every other test exercises the pure payload functions or the registry. This one goes through
the actual MCP wire protocol (an in-memory ``fastmcp.Client`` bound to the assembled app), so it
is the regression guard for framework upgrades (fastmcp / mcp SDK majors): if a tool stops being
advertised, changes its call contract, or a no-backend tool starts raising instead of returning a
structured error, it fails here.
"""

from __future__ import annotations

import asyncio
import json

from fastmcp import Client

from quantum_ads.core.query.runner import StreamFn
from quantum_ads.server import build_server


def _env() -> dict[str, str]:
    return {
        "GOOGLE_ADS_DEVELOPER_TOKEN": "d",
        "GOOGLE_ADS_CLIENT_ID": "c",
        "GOOGLE_ADS_CLIENT_SECRET": "s",
        "GOOGLE_ADS_REFRESH_TOKEN": "r",
    }


def _stream(creds: dict[str, object], version: str) -> StreamFn:
    return lambda cid, q: []


def _payload(result: object) -> object:
    """Decode a tool result into Python data, independent of the client's result shape."""
    structured = getattr(result, "structured_content", None)
    if isinstance(structured, dict):
        return structured.get("result", structured)
    for item in getattr(result, "content", []) or []:
        text = getattr(item, "text", None)
        if text is not None:
            return json.loads(text)
    raise AssertionError(f"tool result carried no decodable payload: {result!r}")


def _run(scenario):  # type: ignore[no-untyped-def]
    return asyncio.run(scenario())


def test_every_registered_tool_is_advertised_over_mcp():
    assembled = build_server(env=_env(), stream_factory=_stream)
    registered = {t.name for t in assembled.registry.all_tools()}

    async def scenario() -> set[str]:
        async with Client(assembled.app) as client:
            return {tool.name for tool in await client.list_tools()}

    advertised = _run(scenario)
    assert registered, "the assembled server registered no tools"
    assert registered == advertised, {
        "missing_over_mcp": sorted(registered - advertised),
        "unregistered_but_advertised": sorted(advertised - registered),
    }


def test_core_tools_round_trip_over_mcp():
    assembled = build_server(env=_env(), stream_factory=_stream)

    async def scenario() -> tuple[object, object, object]:
        async with Client(assembled.app) as client:
            health = _payload(await client.call_tool("health", {}))
            caps = _payload(await client.call_tool("list_capabilities", {}))
            described = _payload(await client.call_tool("describe_tool", {"name": "health"}))
            return health, caps, described

    health, caps, described = _run(scenario)
    assert isinstance(health, dict)
    assert isinstance(caps, list) and caps
    assert {c["connector"] for c in caps} >= {"core", "google_ads"}
    assert described == {
        "name": "health",
        "summary": "Server + API version health.",
        "read_only": True,
    }


def test_unwired_backend_returns_structured_error_not_protocol_error():
    # bigquery's backend is not wired in this assembly: the tool must answer with a structured
    # error envelope, never raise through the protocol.
    assembled = build_server(env=_env(), stream_factory=_stream)

    async def scenario() -> object:
        async with Client(assembled.app) as client:
            result = await client.call_tool(
                "bigquery.datasets.list", {"project_id": "p"}, raise_on_error=False
            )
            assert not getattr(result, "is_error", False), result
            return _payload(result)

    out = _run(scenario)
    assert isinstance(out, dict)
    assert out["error"]["code"] == "BACKEND_NOT_CONFIGURED"


def _broken_stream_factory(creds: dict[str, object], version: str) -> StreamFn:
    # Mirrors the real factory with missing/invalid Google Ads creds: building the client
    # authenticates (token refresh) and fails.
    raise RuntimeError("invalid_client: The OAuth client was not found.")


def test_server_starts_and_serves_even_when_google_ads_auth_fails():
    # Building the Google Ads client must not happen at startup: bad Ads creds would otherwise
    # crash the whole server (every other connector with it) before it can answer anything.
    assembled = build_server(env=_env(), stream_factory=_broken_stream_factory)

    async def scenario() -> object:
        async with Client(assembled.app) as client:
            assert _payload(await client.call_tool("health", {}))
            result = await client.call_tool(
                "ads.gaql.query",
                {"customer_id": "1", "query": "SELECT customer.id FROM customer"},
                raise_on_error=False,
            )
            assert not getattr(result, "is_error", False), result
            return _payload(result)

    out = _run(scenario)
    assert isinstance(out, dict)
    assert out["error"]["code"] == "RuntimeError"
    assert "invalid_client" in out["error"]["message"]
