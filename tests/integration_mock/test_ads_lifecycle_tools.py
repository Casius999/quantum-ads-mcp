"""Demand Gen, experiments, batch jobs and Reach Planner tools over a real MCP client."""

from __future__ import annotations

import asyncio
import base64

from fastmcp import Client

from quantum_ads.connectors.google_ads.read.connector import register_google_ads_read
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
_IMG = base64.b64encode(b"\x89PNG fake").decode()


class Fake:
    def __init__(self) -> None:
        self.mutations: list[tuple[list[dict[str, object]], bool]] = []
        self.services: list[tuple[str, dict[str, object]]] = []

    def mutate_factory(self, creds, version):  # type: ignore[no-untyped-def]
        def mutate(customer_id, operations, validate_only):  # type: ignore[no-untyped-def]
            self.mutations.append((operations, validate_only))
            return {"validate_only": validate_only, "results": [{}]}

        return mutate

    def services_factory(self, creds, version):  # type: ignore[no-untyped-def]
        def call(op: str, params: dict[str, object]) -> list[dict[str, object]]:
            self.services.append((op, params))
            return [{"op": op}]

        return call


def _call(fake: Fake, name: str, args: dict[str, object]) -> dict[str, object]:
    app = build_server(
        env=_ENV,
        stream_factory=lambda c, v: lambda cid, q: [],
        mutate_factory=fake.mutate_factory,
        services_factory=fake.services_factory,
        connectors=[register_google_ads_read, register_google_ads_write],
    ).app

    async def scenario() -> dict[str, object]:
        async with Client(app) as client:
            result = await client.call_tool(name, args)
            assert isinstance(result.structured_content, dict)
            return result.structured_content

    return asyncio.run(scenario())


def test_demand_gen_campaign_goes_through_the_guarded_mutate():
    fake = Fake()
    result = _call(
        fake,
        "ads.campaign.create_demand_gen",
        {
            "customer_id": "1",
            "name": "DG",
            "daily_budget_micros": 5_000_000,
            "final_url": "https://example.com",
            "business_name": "Example",
            "headlines": ["Run faster"],
            "descriptions": ["Free returns."],
            "logo_base64": _IMG,
            "marketing_images_base64": [_IMG],
            "square_images_base64": [_IMG],
        },
    )
    assert result["applied"] is True
    assert fake.mutations[0][0][0]["entity"] == "mutate"


def test_experiment_create_and_lifecycle():
    fake = Fake()
    created = _call(
        fake, "ads.experiment.create", {"customer_id": "1", "name": "E", "base_campaign_id": "9"}
    )
    assert created["applied"] is True
    for action in ("schedule", "promote", "end"):
        out = _call(
            fake,
            f"ads.experiment.{action}",
            {"customer_id": "1", "experiment": "customers/1/experiments/5"},
        )
        assert out["applied"] is True
    entities = [ops[0]["entity"] for ops, validate in fake.mutations if not validate]
    assert entities == ["mutate", "experiment_schedule", "experiment_promote", "experiment_end"]


def test_batch_submit_validates_offline_then_submits():
    fake = Fake()
    op = {
        "campaign_operation": {
            "update": {"resource_name": "customers/1/campaigns/2", "status": "PAUSED"},
            "update_mask": "status",
        }
    }
    result = _call(fake, "ads.batch.submit", {"customer_id": "1", "operations": [op] * 3})
    assert result["applied"] is True
    assert fake.mutations[-1][0][0] == {"entity": "batch_submit", "operations": [op] * 3}
    bad = _call(fake, "ads.batch.submit", {"customer_id": "1", "operations": [{"x_operation": {}}]})
    assert bad["error"]["code"] == "INVALID_OPERATION"  # type: ignore[index]


def test_batch_status_and_reach_reads():
    fake = Fake()
    assert (
        _call(
            fake, "ads.batch.status", {"customer_id": "1", "batch_job": "customers/1/batchJobs/3"}
        )["row_count"]
        == 1
    )
    _call(fake, "ads.reach.locations", {})
    _call(fake, "ads.reach.products", {"location_id": "2250"})
    _call(
        fake,
        "ads.reach.forecast",
        {
            "customer_id": "1",
            "location_id": "2250",
            "currency_code": "EUR",
            "duration_days": 28,
            "products": [{"code": "TRUEVIEW_IN_STREAM", "budget_micros": 1_000_000_000}],
        },
    )
    assert [op for op, _ in fake.services] == [
        "batch_status",
        "reach_locations",
        "reach_products",
        "reach_forecast",
    ]
