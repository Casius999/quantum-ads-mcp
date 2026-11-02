"""Google Ads generic mutate, campaign builder, recommendations and planning over MCP."""

from __future__ import annotations

import asyncio

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


class FakeAds:
    def __init__(self) -> None:
        self.mutations: list[tuple[list[dict[str, object]], bool]] = []
        self.service_calls: list[tuple[str, dict[str, object]]] = []
        self.queries: list[str] = []

    def stream_factory(self, creds, version):  # type: ignore[no-untyped-def]
        def stream(customer_id: str, query: str) -> list[dict[str, object]]:
            self.queries.append(query)
            return [{"recommendation": {"resource_name": "customers/1/recommendations/9"}}]

        return stream

    def mutate_factory(self, creds, version):  # type: ignore[no-untyped-def]
        def mutate(customer_id, operations, validate_only):  # type: ignore[no-untyped-def]
            self.mutations.append((operations, validate_only))
            return {"validate_only": validate_only, "results": [{"ok": True}]}

        return mutate

    def services_factory(self, creds, version):  # type: ignore[no-untyped-def]
        def call(op: str, params: dict[str, object]) -> list[dict[str, object]]:
            self.service_calls.append((op, params))
            return [{"keyword": "running shoes", "avg_monthly_searches": 1000}]

        return call


def _call(fake: FakeAds, name: str, args: dict[str, object]) -> dict[str, object]:
    app = build_server(
        env=_ENV,
        stream_factory=fake.stream_factory,
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


_UPDATE = {
    "campaign_operation": {
        "update": {"resource_name": "customers/1/campaigns/2", "status": "PAUSED"},
        "update_mask": "status",
    }
}


def test_generic_mutate_validates_then_applies_atomically():
    fake = FakeAds()
    result = _call(fake, "ads.mutate", {"customer_id": "1", "operations": [_UPDATE]})
    assert result["applied"] is True
    assert [validate for _, validate in fake.mutations] == [True, False]
    batch = fake.mutations[0][0][0]
    assert batch["entity"] == "mutate" and batch["operations"] == [_UPDATE]


def test_generic_mutate_rejects_schema_errors_before_any_call():
    fake = FakeAds()
    bad = {"campaign_operation": {"create": {"nme": "typo"}}}
    result = _call(fake, "ads.mutate", {"customer_id": "1", "operations": [bad]})
    assert result["error"]["code"] == "INVALID_OPERATION"  # type: ignore[index]
    assert fake.mutations == []


def test_search_campaign_builder_sends_one_linked_batch():
    fake = FakeAds()
    result = _call(
        fake,
        "ads.campaign.create_search",
        {
            "customer_id": "1",
            "name": "Shoes",
            "daily_budget_micros": 10_000_000,
            "final_url": "https://example.com",
            "keywords": ["running shoes"],
            "headlines": ["Running Shoes", "Free Delivery", "New Season"],
            "descriptions": ["Best shoes for runners.", "Free returns for 30 days."],
        },
    )
    assert result["applied"] is True
    ops = fake.mutations[0][0][0]["operations"]
    assert len(ops) == 5  # type: ignore[arg-type]


def test_recommendations_apply_and_list():
    fake = FakeAds()
    names = ["customers/1/recommendations/9"]
    applied = _call(
        fake, "ads.recommendations.apply", {"customer_id": "1", "resource_names": names}
    )
    assert applied["applied"] is True
    assert fake.mutations[0][0][0] == {"entity": "recommendation_apply", "resource_names": names}
    listed = _call(fake, "ads.recommendations.list", {"customer_id": "1", "types": ["KEYWORD"]})
    assert listed["row_count"] == 1
    assert "recommendation.type IN ('KEYWORD')" in fake.queries[-1]


def test_keyword_ideas_and_schema():
    fake = FakeAds()
    ideas = _call(fake, "ads.keyword_ideas", {"customer_id": "1", "keywords": ["shoes"]})
    assert ideas["rows"][0]["keyword"] == "running shoes"  # type: ignore[index]
    assert fake.service_calls[0][0] == "keyword_ideas"
    missing = _call(fake, "ads.keyword_ideas", {"customer_id": "1"})
    assert missing["error"]["code"] == "INVALID_ARGUMENT"  # type: ignore[index]
    kinds = _call(fake, "ads.mutate.schema", {})
    assert "campaign_operation" in kinds["operation_kinds"]  # type: ignore[operator]
    fields = _call(fake, "ads.mutate.schema", {"operation_kind": "campaign_budget_operation"})
    assert "amount_micros" in fields["fields"]  # type: ignore[operator]
