"""Insights and creative tools over a real MCP client with fake Ads / GA4 / Vertex backends."""

from __future__ import annotations

import asyncio
import base64
import io
import json

from fastmcp import Client

from quantum_ads.connectors.insights import register_insights
from quantum_ads.server import build_server

_ENV = {
    "GOOGLE_ADS_DEVELOPER_TOKEN": "d",
    "GOOGLE_ADS_CLIENT_ID": "c",
    "GOOGLE_ADS_CLIENT_SECRET": "s",
    "GOOGLE_ADS_REFRESH_TOKEN": "r",
}


def _png(size: tuple[int, int]) -> str:
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", size, (1, 2, 3)).save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()


def _stream_factory(creds, version):  # type: ignore[no-untyped-def]
    def stream(customer_id: str, query: str) -> list[dict[str, object]]:
        if "search_term_view" in query:
            return [
                {
                    "search_term_view.search_term": "free",
                    "campaign.id": "1",
                    "ad_group.id": "2",
                    "metrics.cost_micros": 9_000_000,
                    "metrics.clicks": 3,
                    "metrics.conversions": 0,
                }
            ]
        if "ad_group_criterion" in query:
            return [{"ad_group_criterion.keyword.text": "shoes"}]
        if "FROM customer" in query:
            return [{"segments.date": "2026-10-01", "metrics.conversions": 10}]
        if "THIS_MONTH" in query:
            return [
                {
                    "campaign.id": "1",
                    "campaign.name": "C",
                    "campaign_budget.amount_micros": 10_000_000,
                    "metrics.cost_micros": 1,
                }
            ]
        return [
            {
                "campaign.id": "1",
                "campaign.name": "C",
                "segments.date": f"2026-10-0{i}",
                "metrics.cost_micros": v,
            }
            for i, v in enumerate([10, 11, 9, 10, 90], 1)
        ]

    return stream


def _vertex(op: str, params: dict[str, object]) -> list[dict[str, object]]:
    if op == "gemini":
        payload = {
            "headlines": ["Run Fast", "Free Returns", "New Season", "x" * 40],
            "long_headlines": ["A long headline for the campaign"],
            "descriptions": ["Short one.", "Another description."],
            "image_prompts": ["a runner at dawn"],
        }
        return [{"text": "```json\n" + json.dumps(payload) + "\n```"}]
    size = (1792, 1024) if params["aspect_ratio"] == "16:9" else (1024, 1024)
    return [{"image_base64": _png(size)}]


def _ga4(op: str, params: dict[str, object]) -> list[dict[str, object]]:
    return [
        {
            "dimensionValues": [{"value": "20261001"}, {"value": "google / cpc"}],
            "metricValues": [{"value": "8"}],
        },
        {
            "dimensionValues": [{"value": "20261001"}, {"value": "bing / cpc"}],
            "metricValues": [{"value": "99"}],
        },
    ]


def _call(name: str, args: dict[str, object]) -> dict[str, object]:
    app = build_server(
        env=_ENV,
        stream_factory=_stream_factory,
        connectors=[register_insights],
        backends={"vertex.api": _vertex, "ga4.data": _ga4},
    ).app

    async def scenario() -> dict[str, object]:
        async with Client(app) as client:
            result = await client.call_tool(name, args)
            assert isinstance(result.structured_content, dict)
            return result.structured_content

    return asyncio.run(scenario())


def test_anomalies_pacing_and_search_terms():
    assert _call("insights.anomalies", {"customer_id": "1"})["count"] == 1
    assert _call("insights.pacing", {"customer_id": "1"})["campaigns"][0]["campaign"] == "C"  # type: ignore[index]
    mined = _call("insights.search_terms", {"customer_id": "1"})
    assert mined["negative_keywords"][0]["term"] == "free"  # type: ignore[index]


def test_ga4_reconcile_keeps_only_google_cpc():
    out = _call("insights.ga4_reconcile", {"customer_id": "1", "property_id": "123"})
    assert out["ga4_total"] == 8.0 and out["ads_total"] == 10.0


def test_creative_tools_validate_copy_and_fit_images():
    search = _call("creative.search_ads", {"product": "running shoes", "audience": "runners"})
    assert search["headlines"] == ["Run Fast", "Free Returns", "New Season"]
    pack = _call("creative.pmax_pack", {"product": "running shoes", "audience": "runners"})
    kinds = sorted(image["field_type"] for image in pack["images"])  # type: ignore[union-attr]
    assert kinds == ["MARKETING_IMAGE", "SQUARE_MARKETING_IMAGE"]


def _billing_disabled(op: str, params: dict[str, object]) -> list[dict[str, object]]:
    raise RuntimeError("403 BILLING_DISABLED")


def _call_with(
    backends: dict[str, object], name: str, args: dict[str, object]
) -> dict[str, object]:
    app = build_server(
        env=_ENV, stream_factory=_stream_factory, connectors=[register_insights], backends=backends
    ).app

    async def scenario() -> dict[str, object]:
        async with Client(app) as client:
            result = await client.call_tool(name, args)
            assert isinstance(result.structured_content, dict)
            return result.structured_content

    return asyncio.run(scenario())


def test_creative_falls_back_to_free_providers_when_vertex_fails():
    def chat(op: str, params: dict[str, object]) -> list[dict[str, object]]:
        return _vertex("gemini", params)

    def flux(op: str, params: dict[str, object]) -> list[dict[str, object]]:
        return [{"image_base64": _png((int(params["width"]), int(params["height"])))}]  # type: ignore[call-overload]

    backends = {"vertex.api": _billing_disabled, "llm.chat": chat, "image.free": flux}
    pack = _call_with(backends, "creative.pmax_pack", {"product": "shoes", "audience": "runners"})
    assert len(pack["images"]) == 2 and "image_errors" not in pack  # type: ignore[arg-type]


def test_creative_reports_every_provider_failure():
    out = _call_with(
        {"vertex.api": _billing_disabled}, "creative.search_ads", {"product": "x", "audience": "y"}
    )
    message = out["error"]["message"]  # type: ignore[index]
    assert "BILLING_DISABLED" in message and "llm.chat: not wired" in message
    backends = {"vertex.api": _vertex, "image.free": _billing_disabled}

    def no_images(op: str, params: dict[str, object]) -> list[dict[str, object]]:
        if op == "imagen":
            raise RuntimeError("quota")
        return _vertex(op, params)

    pack = _call_with(
        {**backends, "vertex.api": no_images},
        "creative.pmax_pack",
        {"product": "x", "audience": "y"},
    )
    assert pack["images"] == [] and len(pack["image_errors"]) == 2  # type: ignore[arg-type]


def test_overlong_copy_gets_one_repair_round():
    prompts: list[str] = []
    good = {"headlines": [f"Run {i}" for i in range(15)], "descriptions": ["a.", "b.", "c.", "d."]}

    def chat(op: str, params: dict[str, object]) -> list[dict[str, object]]:
        prompts.append(str(params["prompt"]))
        if len(prompts) == 1:
            return [{"text": json.dumps({"headlines": ["x" * 40] * 15, "descriptions": ["d"] * 4})}]
        return [{"text": json.dumps(good)}]

    out = _call_with({"llm.chat": chat}, "creative.search_ads", {"product": "x", "audience": "y"})
    assert len(out["headlines"]) == 15 and "has 40 characters" in prompts[1]  # type: ignore[arg-type]


def test_failed_repair_keeps_the_usable_first_answer():
    calls: list[int] = []

    def chat(op: str, params: dict[str, object]) -> list[dict[str, object]]:
        calls.append(1)
        if len(calls) == 1:
            return [
                {"text": json.dumps({"headlines": ["A", "B", "C"], "descriptions": ["d", "e"]})}
            ]
        return [{"text": "sorry, no JSON"}]

    out = _call_with({"llm.chat": chat}, "creative.search_ads", {"product": "x", "audience": "y"})
    assert out["headlines"] == ["A", "B", "C"] and len(calls) == 2
    calls.clear()

    def hopeless(op: str, params: dict[str, object]) -> list[dict[str, object]]:
        calls.append(1)
        return [{"text": json.dumps({"headlines": ["x" * 40], "descriptions": []})}]

    out = _call_with(
        {"llm.chat": hopeless}, "creative.search_ads", {"product": "x", "audience": "y"}
    )
    assert out["error"]["code"] == "CREATIVE_FAILED" and len(calls) == 2  # type: ignore[index]
