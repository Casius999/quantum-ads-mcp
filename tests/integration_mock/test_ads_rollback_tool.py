"""ads.rollback replays the inverse recorded in the signed audit trail."""

from __future__ import annotations

import asyncio

from fastmcp import Client

from quantum_ads.connectors.google_ads.write.connector import register_google_ads_write
from quantum_ads.server import build_server

_ENV = {
    "GOOGLE_ADS_DEVELOPER_TOKEN": "d",
    "GOOGLE_ADS_CLIENT_ID": "c",
    "GOOGLE_ADS_CLIENT_SECRET": "s",
    "GOOGLE_ADS_REFRESH_TOKEN": "r",
    "QUANTUM_ADS_READ_ONLY": "false",
    "QUANTUM_ADS_WRITE_MODE": "auto",
}
_UPDATE = {
    "campaign_operation": {
        "update": {"resource_name": "customers/1/campaigns/2", "status": "PAUSED"},
        "update_mask": "status",
    }
}
_INVERSE = {
    "campaign_operation": {
        "update": {"resource_name": "customers/1/campaigns/2", "status": "ENABLED"},
        "update_mask": "status",
    }
}


def test_rollback_applies_the_recorded_inverse():
    sent: list[tuple[list[dict[str, object]], bool]] = []

    def mutate_factory(creds, version):  # type: ignore[no-untyped-def]
        def mutate(customer_id, operations, validate_only):  # type: ignore[no-untyped-def]
            sent.append((operations, validate_only))
            result: dict[str, object] = {"validate_only": validate_only, "results": [{}]}
            if not validate_only and operations[0]["operations"] == [_UPDATE]:
                result["inverse_operations"] = [_INVERSE]
            return result

        return mutate

    app = build_server(
        env=_ENV,
        stream_factory=lambda c, v: lambda cid, q: [],
        mutate_factory=mutate_factory,
        connectors=[register_google_ads_write],
    ).app

    async def scenario() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
        async with Client(app) as client:
            first = await client.call_tool(
                "ads.mutate", {"customer_id": "1", "operations": [_UPDATE]}
            )
            undo = await client.call_tool("ads.rollback", {})
            nothing = await client.call_tool("ads.rollback", {"audit_index": 99})
            return first.structured_content, undo.structured_content, nothing.structured_content  # type: ignore[return-value]

    first, undo, nothing = asyncio.run(scenario())
    assert first["applied"] is True
    assert undo["applied"] is True
    assert undo["rolled_back"]["op"] == "ads.mutate"  # type: ignore[index]
    assert sent[-1][0][0]["operations"] == [_INVERSE] and sent[-1][1] is False
    assert nothing["error"]["code"] == "INVALID_OPERATION"  # type: ignore[index]
