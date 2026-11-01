"""The server's audit ledger: persistent when QUANTUM_ADS_AUDIT_DIR is set, inspectable via a tool."""

from __future__ import annotations

import asyncio
from pathlib import Path

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


def _audit_status(env: dict[str, str]) -> dict[str, object]:
    assembled = build_server(env=env, stream_factory=_stream, connectors=[])

    async def scenario() -> dict[str, object]:
        async with Client(assembled.app) as client:
            result = await client.call_tool("audit.status", {})
            assert isinstance(result.structured_content, dict)
            return result.structured_content

    return asyncio.run(scenario())


def test_audit_is_in_memory_without_an_audit_dir():
    status = _audit_status(_ENV)
    assert status["persistent"] is False
    assert status["chain"] == {"ok": True, "records": 0, "first_bad_index": None}


def test_audit_dir_makes_the_ledger_persistent(tmp_path: Path):
    status = _audit_status({**_ENV, "QUANTUM_ADS_AUDIT_DIR": str(tmp_path)})
    assert status["persistent"] is True
    assert status["path"] == str(tmp_path / "audit.jsonl")
    assert (tmp_path / "audit_ed25519.pem").exists()


def test_audit_status_is_a_registered_read_only_core_tool():
    assembled = build_server(env=_ENV, stream_factory=_stream, connectors=[])
    assert assembled.registry.describe_tool("audit.status").read_only is True


def test_confirmed_write_over_mcp_lands_in_the_persistent_chain(tmp_path: Path):
    from quantum_ads.connectors.gtm.connector import register_gtm

    def fake_read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        return []

    def fake_mutate(
        parent: str, operations: list[dict[str, object]], validate_only: bool
    ) -> dict[str, object]:
        return {"ok": True, "validate_only": validate_only}

    env = {**_ENV, "QUANTUM_ADS_READ_ONLY": "false", "QUANTUM_ADS_AUDIT_DIR": str(tmp_path)}
    assembled = build_server(
        env=env,
        stream_factory=_stream,
        connectors=[register_gtm],
        backends={"gtm.api": fake_read, "gtm.mutate": fake_mutate},
    )
    args: dict[str, object] = {
        "workspace_path": "accounts/1/containers/2/workspaces/3",
        "tag_name": "GA4",
        "tag_type": "googtag",
    }

    async def scenario() -> tuple[dict[str, object], dict[str, object]]:
        async with Client(assembled.app) as client:
            preview = (await client.call_tool("gtm.create_tag", args)).structured_content
            assert isinstance(preview, dict) and preview["applied"] is False
            confirmed = {**args, "confirm": preview["confirm_token"]}
            applied = (await client.call_tool("gtm.create_tag", confirmed)).structured_content
            status = (await client.call_tool("audit.status", {})).structured_content
            assert isinstance(applied, dict) and isinstance(status, dict)
            return applied, status

    applied, status = asyncio.run(scenario())
    assert applied["applied"] is True
    assert status["chain"] == {"ok": True, "records": 1, "first_bad_index": None}
    line = (tmp_path / "audit.jsonl").read_text(encoding="utf-8").strip()
    assert '"op":"gtm.create_tag"' in line
    assert '"ts":"1970' not in line  # real timestamp, not the old placeholder


def test_anchor_tools_are_registered_and_explain_an_in_memory_ledger():
    assembled = build_server(env=_ENV, stream_factory=_stream, connectors=[])
    assert {"audit.anchor", "audit.anchor_status"} <= {
        t.name for cap in assembled.registry.list_capabilities() for t in cap.tools
    }

    async def scenario() -> dict[str, object]:
        async with Client(assembled.app) as client:
            result = await client.call_tool("audit.anchor", {})
            assert isinstance(result.structured_content, dict)
            return result.structured_content

    error = asyncio.run(scenario())["error"]
    assert isinstance(error, dict) and error["code"] == "ANCHOR_FAILED"
    assert "persistent" in str(error["message"])
