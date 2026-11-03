"""Live: insights GAQL on the real account, and the creative studio over the free fallback chain.

The creative test needs QUANTUM_ADS_LLM_BASE_URL (any OpenAI-compatible endpoint, e.g. the keyless
OVHcloud AI Endpoints) and, for images, QUANTUM_ADS_IMAGE_MODEL; Vertex is used first if billed.
"""

from __future__ import annotations

import asyncio
import base64
import io
import os

import pytest
from fastmcp import Client

from quantum_ads.backends import build_backends
from quantum_ads.connectors.insights import register_insights
from quantum_ads.server import build_server

pytestmark = pytest.mark.live


def _call(name: str, args: dict[str, object]) -> dict[str, object]:
    from quantum_ads.connectors.google_ads.sdk import default_stream_factory

    app = build_server(
        env=dict(os.environ),
        stream_factory=default_stream_factory,
        connectors=[register_insights],
        backends=build_backends(os.environ),
    ).app

    async def scenario() -> dict[str, object]:
        async with Client(app, timeout=900) as client:
            result = await client.call_tool(name, args)
            assert isinstance(result.structured_content, dict)
            return result.structured_content

    return asyncio.run(scenario())


def _customer() -> str:
    if not os.environ.get("GOOGLE_ADS_DEVELOPER_TOKEN"):
        pytest.skip("Google Ads credentials not set")
    customer = os.environ.get("GOOGLE_ADS_TEST_CUSTOMER_ID")
    if not customer:
        pytest.skip("GOOGLE_ADS_TEST_CUSTOMER_ID not set")
    return customer


def test_insights_queries_run_live() -> None:
    customer = _customer()
    assert "count" in _call("insights.anomalies", {"customer_id": customer})
    assert "campaigns" in _call("insights.pacing", {"customer_id": customer})
    mined = _call("insights.search_terms", {"customer_id": customer})
    assert {"negative_keywords", "new_keywords"} <= set(mined)


def test_creative_pack_over_free_fallback_live() -> None:
    if not os.environ.get("QUANTUM_ADS_LLM_BASE_URL"):
        pytest.skip("QUANTUM_ADS_LLM_BASE_URL not set")
    pack = _call(
        "creative.pmax_pack",
        {"product": "chaussures de running homme", "audience": "coureurs reguliers"},
    )
    assert "error" not in pack, pack
    assert len(pack["headlines"]) >= 3  # type: ignore[arg-type]
    if not os.environ.get("QUANTUM_ADS_IMAGE_MODEL"):
        return
    from PIL import Image

    sizes = {
        image["field_type"]: Image.open(io.BytesIO(base64.b64decode(image["data_base64"]))).size
        for image in pack["images"]  # type: ignore[union-attr]
    }
    assert sizes == {"MARKETING_IMAGE": (1200, 628), "SQUARE_MARKETING_IMAGE": (1200, 1200)}
