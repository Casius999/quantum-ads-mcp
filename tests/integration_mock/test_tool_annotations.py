"""Every tool advertises MCP annotations derived from the registry (read/write, destructive...)."""

from __future__ import annotations

import asyncio

import pytest
from fastmcp import Client

from quantum_ads.core.mcp.annotations import annotations_for
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


def _listed() -> dict[str, object]:
    app = build_server(env=_ENV, stream_factory=_stream).app

    async def scenario() -> dict[str, object]:
        async with Client(app) as client:
            return {tool.name: tool.annotations for tool in await client.list_tools()}

    return asyncio.run(scenario())


def test_every_tool_is_annotated():
    listed = _listed()
    assert len(listed) >= 131
    missing = [name for name, ann in listed.items() if ann is None or ann.title is None]
    assert missing == []


def test_reads_are_read_only_and_writes_are_not():
    listed = _listed()
    assert listed["ads.gaql.query"].read_only_hint is True  # type: ignore[attr-defined]
    assert listed["ads.budget.update"].read_only_hint is False  # type: ignore[attr-defined]
    assert listed["merchant.product.delete"].destructive_hint is True  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    ("name", "read_only", "destructive", "idempotent", "open_world"),
    [
        ("health", True, False, True, False),
        ("ads.gaql.query", True, False, True, True),
        ("ads.campaign.set_status", False, True, True, True),
        ("merchant.product.delete", False, True, True, True),
        ("merchant.product.insert", False, False, False, True),
        ("gtm.create_tag", False, False, False, True),
        ("datamanager.audience.upload_members", False, False, False, True),
        ("audit.anchor", False, False, False, True),
    ],
)
def test_hints_follow_the_operation(
    name: str, read_only: bool, destructive: bool, idempotent: bool, open_world: bool
):
    connector = "core" if name in {"health", "audit.anchor"} else name.split(".")[0]
    ann = annotations_for(name, connector=connector, read_only=read_only)
    assert (ann.read_only_hint, ann.destructive_hint, ann.idempotent_hint, ann.open_world_hint) == (
        read_only,
        destructive,
        idempotent,
        open_world,
    )
    assert ann.title
