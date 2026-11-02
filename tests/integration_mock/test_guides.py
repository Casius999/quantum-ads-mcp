"""MCP resources and prompts: readable context and playbooks that only name real tools."""

from __future__ import annotations

import asyncio
import json
import re

from fastmcp import Client

from quantum_ads.core.mcp.guides import PROMPTS
from quantum_ads.core.query.runner import StreamFn
from quantum_ads.server import build_server

_ENV = {
    "GOOGLE_ADS_DEVELOPER_TOKEN": "d",
    "GOOGLE_ADS_CLIENT_ID": "c",
    "GOOGLE_ADS_CLIENT_SECRET": "s",
    "GOOGLE_ADS_REFRESH_TOKEN": "r",
    "QUANTUM_ADS_WRITE_MODE": "auto",
}


def _stream(creds: dict[str, object], version: str) -> StreamFn:
    return lambda customer_id, query: []


def _assembled():  # type: ignore[no-untyped-def]
    return build_server(env=_ENV, stream_factory=_stream)


def test_prompts_only_name_registered_tools():
    registry = _assembled().registry
    known = {t.name for cap in registry.list_capabilities() for t in cap.tools}
    for name, (_, template) in PROMPTS.items():
        named = set(re.findall(r"\b([a-z0-9_]+(?:\.[a-z0-9_]+)+)\b", template))
        assert named <= known, (name, sorted(named - known))


def test_resources_and_prompts_over_mcp():
    app = _assembled().app

    async def scenario() -> tuple[set[str], dict[str, object], set[str], str]:
        async with Client(app) as client:
            uris = {str(r.uri) for r in await client.list_resources()}
            session = json.loads((await client.read_resource("quantum-ads://session"))[0].text)
            prompts = {p.name for p in await client.list_prompts()}
            rendered = await client.get_prompt("weekly_account_audit", {"customer_id": "123"})
            return uris, session, prompts, rendered.messages[0].content.text  # type: ignore[union-attr]

    uris, session, prompts, text = asyncio.run(scenario())
    assert {
        "quantum-ads://capabilities",
        "quantum-ads://google-ads/versions",
        "quantum-ads://google-ads/field-deltas",
        "quantum-ads://session",
    } <= uris
    assert session["tenant"] == "operator" and session["write_mode"] == "auto"
    assert set(PROMPTS) <= prompts
    assert "customer 123" in text and "ads.report.campaign" in text


def test_prompt_defaults_fill_optional_fields():
    app = _assembled().app

    async def scenario() -> str:
        async with Client(app) as client:
            rendered = await client.get_prompt("search_terms_mining", {"customer_id": "9"})
            return rendered.messages[0].content.text  # type: ignore[union-attr]

    assert "last 30 days" in asyncio.run(scenario())
