"""Insights + creative studio: cross-product analysis and production in one call each.

Reads Google Ads with GAQL (the request tenant's client), GA4 through ``ga4.data`` and text /
images through ``vertex.api`` with free fallbacks (``llm.chat``, ``image.openai``, ``image.free``); analysis is pure (``analytics``), copy is validated
(``creative``) and images are fitted to Google Ads specs (``images``).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from typing import Any, cast

from fastmcp import FastMCP

from ...core.context import ServerContext
from ...core.mcp.register import add_tool
from ...core.registry.registry import Capability, ToolSpec
from . import analytics, creative

ReadFn = Callable[[str, dict[str, object]], list[dict[str, object]]]

# Providers in fallback order: billed Vertex first, then the free paths.
BACKEND_VERTEX = "vertex.api"
BACKEND_LLM = "llm.chat"
BACKEND_IMAGE_OPENAI = "image.openai"
BACKEND_IMAGE_FREE = "image.free"


def _window(days: int, today: dt.date | None = None) -> tuple[str, str]:
    end = (today or dt.date.today()) - dt.timedelta(days=1)
    return (end - dt.timedelta(days=days - 1)).isoformat(), end.isoformat()


def _ga4_named(
    rows: list[dict[str, Any]], dimensions: list[str], metrics: list[str]
) -> list[dict[str, Any]]:
    named = []
    for row in rows:
        values = [v.get("value") for v in row.get("dimensionValues", [])]
        numbers = [v.get("value") for v in row.get("metricValues", [])]
        named.append(
            {
                **dict(zip(dimensions, values, strict=False)),
                **dict(zip(metrics, numbers, strict=False)),
            }
        )
    return named


def _missing(name: str) -> dict[str, object]:
    return {"error": {"code": "BACKEND_NOT_CONFIGURED", "message": f"{name} not wired"}}


def register_insights(app: FastMCP, ctx: ServerContext) -> None:
    stream = ctx.stream()

    def insights_anomalies(
        customer_id: str, days: int = 28, threshold: float = 3.5
    ) -> dict[str, object]:
        start, end = _window(days)
        rows = stream(
            customer_id,
            "SELECT campaign.id, campaign.name, segments.date, metrics.cost_micros, "
            "metrics.conversions, metrics.clicks FROM campaign "
            f"WHERE segments.date BETWEEN '{start}' AND '{end}'",
        )
        findings = analytics.detect_anomalies(rows, threshold=threshold)
        return {"window": [start, end], "anomalies": findings, "count": len(findings)}

    def insights_pacing(customer_id: str) -> dict[str, object]:
        rows = stream(
            customer_id,
            "SELECT campaign.id, campaign.name, campaign_budget.amount_micros, metrics.cost_micros "
            "FROM campaign WHERE segments.date DURING THIS_MONTH AND campaign.status = 'ENABLED'",
        )
        return {"campaigns": analytics.pacing(rows, today=dt.date.today())}

    def insights_search_terms(
        customer_id: str,
        days: int = 30,
        min_waste_cost_micros: int = 5_000_000,
        min_conversions: float = 1.0,
    ) -> dict[str, object]:
        start, end = _window(days)
        terms = stream(
            customer_id,
            "SELECT search_term_view.search_term, campaign.id, ad_group.id, metrics.cost_micros, "
            "metrics.clicks, metrics.conversions FROM search_term_view "
            f"WHERE segments.date BETWEEN '{start}' AND '{end}'",
        )
        keywords = stream(
            customer_id,
            "SELECT ad_group_criterion.keyword.text FROM ad_group_criterion "
            "WHERE ad_group_criterion.type = 'KEYWORD' AND ad_group_criterion.negative = FALSE",
        )
        mined = analytics.mine_search_terms(
            terms,
            customer_id=customer_id,
            keywords=[str(k.get("ad_group_criterion.keyword.text", "")) for k in keywords],
            min_waste_cost_micros=min_waste_cost_micros,
            min_conversions=min_conversions,
        )
        return {
            "window": [start, end],
            **mined,
            "apply_with": "ads.mutate (pass the selected 'operation' objects)",
        }

    def insights_ga4_reconcile(
        customer_id: str, property_id: str, days: int = 28
    ) -> dict[str, object]:
        backend = ctx.backend("ga4.data")
        if backend is None:
            return _missing("ga4.data")
        start, end = _window(days)
        ads_rows = stream(
            customer_id,
            "SELECT segments.date, metrics.conversions FROM customer "
            f"WHERE segments.date BETWEEN '{start}' AND '{end}'",
        )
        dimensions, metrics = ["date", "sessionSourceMedium"], ["keyEvents"]
        raw = cast(ReadFn, backend)(
            "runReport",
            {
                "property_id": property_id,
                "dimensions": dimensions,
                "metrics": metrics,
                "start_date": start,
                "end_date": end,
            },
        )
        paid = [
            r
            for r in _ga4_named(raw, dimensions, metrics)
            if r.get("sessionSourceMedium") == "google / cpc"
        ]
        return {"window": [start, end], **analytics.reconcile(ads_rows, paid)}

    def first_success(
        attempts: list[tuple[str, str, dict[str, object]]],
    ) -> list[dict[str, object]]:
        """Run the first wired provider that answers; collect every failure for the error."""
        failures: list[str] = []
        for key, op, params in attempts:
            backend = ctx.backend(key)
            if backend is None:
                failures.append(f"{key}: not wired")
                continue
            try:
                return cast(ReadFn, backend)(op, params)
            except Exception as exc:  # noqa: BLE001 - fall through to the next provider
                failures.append(f"{key}: {str(exc)[:200]}")
        raise creative.CreativeError("no provider succeeded - " + "; ".join(failures))

    def gemini_json(prompt: str) -> dict[str, Any]:
        """Vertex Gemini first, then the free OpenAI-compatible endpoint (``llm.chat``)."""
        rows = first_success(
            [
                (
                    "vertex.api",
                    "gemini",
                    {"prompt": prompt, "model": "gemini-3.8-flash", "max_tokens": 4096},
                ),
                (BACKEND_LLM, "chat", {"prompt": prompt, "max_tokens": 2048}),
            ]
        )
        return creative.parse_json_object("".join(str(r.get("text", "")) for r in rows))

    def generate_image(prompt: str, aspect: str) -> str:
        """Vertex first, then an OpenAI-compatible images API, then free FLUX on Hugging Face."""
        width, height = {"16:9": (1216, 640), "1:1": (1024, 1024)}[aspect]
        rows = first_success(
            [
                (BACKEND_VERTEX, "imagen", {"prompt": prompt, "n": 1, "aspect_ratio": aspect}),
                (
                    BACKEND_IMAGE_OPENAI,
                    "image",
                    # 1024x1024 is the one size every OpenAI-compatible server accepts;
                    # fit() then centre-crops it to the landscape spec.
                    {"prompt": prompt, "width": 1024, "height": 1024},
                ),
                (BACKEND_IMAGE_FREE, "image", {"prompt": prompt, "width": width, "height": height}),
            ]
        )
        return str(rows[0]["image_base64"])

    def generate_copy(
        prompt: str, limits: dict[str, tuple[int, int]], minimums: dict[str, int]
    ) -> tuple[dict[str, Any], dict[str, list[str]]]:
        """Ask once; if items break the limits, send one targeted repair round and keep the best."""
        payload = gemini_json(prompt)
        try:
            copy = creative.validated(payload, limits, minimums)
        except creative.CreativeError:
            copy = None
        if copy is not None and all(
            len(copy[field]) >= count // 2 for field, (count, _) in limits.items()
        ):
            return payload, copy
        try:
            repaired = gemini_json(creative.repair_prompt(payload, limits))
            return {**payload, **repaired}, creative.validated(repaired, limits, minimums)
        except creative.CreativeError:
            if copy is None:
                raise
            return payload, copy

    def creative_search_ads(
        product: str, audience: str, language: str = "French", final_url: str | None = None
    ) -> dict[str, object]:
        try:
            _, copy = generate_copy(
                creative.search_ads_prompt(product, audience, language, final_url),
                creative.SEARCH_LIMITS,
                {"headlines": 3, "descriptions": 2},
            )
        except creative.CreativeError as exc:
            return {"error": {"code": "CREATIVE_FAILED", "message": str(exc)}}
        return {**copy, "use_with": "ads.campaign.create_search (headlines, descriptions)"}

    def creative_pmax_pack(
        product: str,
        audience: str,
        language: str = "French",
        with_images: bool = True,
        scenes: int = 1,
    ) -> dict[str, object]:
        try:
            payload, copy = generate_copy(
                creative.pmax_prompt(product, audience, language),
                creative.PMAX_LIMITS,
                {"headlines": 3, "long_headlines": 1, "descriptions": 2},
            )
        except creative.CreativeError as exc:
            return {"error": {"code": "CREATIVE_FAILED", "message": str(exc)}}
        result: dict[str, object] = {**copy}
        if with_images:
            from .images import fit

            # Each scene costs two image generations (landscape + square).
            prompts = [str(p) for p in (payload.get("image_prompts") or [product])][
                : max(1, scenes)
            ]
            images: list[dict[str, str]] = []
            image_errors: list[str] = []
            for prompt in prompts:
                for aspect, kind, field in (
                    ("16:9", "landscape", "MARKETING_IMAGE"),
                    ("1:1", "square", "SQUARE_MARKETING_IMAGE"),
                ):
                    try:
                        data = generate_image(prompt, aspect)
                    except creative.CreativeError as exc:
                        image_errors.append(str(exc))
                        continue
                    images.append({"field_type": field, "data_base64": fit(data, kind)})
            result["images"] = images
            if image_errors:
                result["image_errors"] = image_errors
        result["use_with"] = "ads.campaign.create_pmax (+ business_name, logo_base64)"
        return result

    tools: list[tuple[str, str, Callable[..., Any]]] = [
        (
            "insights.anomalies",
            "Campaign anomalies: latest day vs each campaign's own history (robust z on cost, conversions, clicks).",
            insights_anomalies,
        ),
        (
            "insights.pacing",
            "Month-to-date spend vs daily budgets, projected to month end; over/under-pacing campaigns.",
            insights_pacing,
        ),
        (
            "insights.search_terms",
            "Search-term mining: wasted terms -> negative keywords, converting untargeted terms -> new keywords, each with a ready ads.mutate operation.",
            insights_search_terms,
        ),
        (
            "insights.ga4_reconcile",
            "Daily Google Ads conversions vs GA4 key events from google / cpc, with flagged gaps.",
            insights_ga4_reconcile,
        ),
        (
            "creative.search_ads",
            "Generate validated responsive-search-ad copy (15 headlines <=30, 4 descriptions <=90) with Gemini.",
            creative_search_ads,
        ),
        (
            "creative.pmax_pack",
            "Generate a Performance Max pack: validated headlines, long headlines, descriptions, and images fitted to 1200x628 / 1200x1200.",
            creative_pmax_pack,
        ),
    ]
    for name, description, fn in tools:
        add_tool(app, name, description, fn)
    ctx.registry.register(
        Capability(
            connector="insights",
            domain="read",
            tools=[ToolSpec(name=n, summary=d) for n, d, _ in tools],
        )
    )
