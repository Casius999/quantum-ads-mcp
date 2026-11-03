"""Insights analytics, creative validation and image fitting (pure, offline)."""

from __future__ import annotations

import base64
import datetime as dt
import io

import pytest
from hypothesis import given
from hypothesis import strategies as st

from quantum_ads.connectors.google_ads.write.operations import validate_operations
from quantum_ads.connectors.insights import analytics, creative
from quantum_ads.core.versioning.version_manager import DEFAULT_API_VERSION as V


def _days(values: list[float], metric: str = "cost_micros") -> list[dict[str, object]]:
    return [
        {
            "campaign.id": "1",
            "campaign.name": "C",
            "segments.date": f"2026-10-{i + 1:02d}",
            f"metrics.{metric}": v,
        }
        for i, v in enumerate(values)
    ]


def test_spike_on_the_latest_day_is_flagged():
    findings = analytics.detect_anomalies(
        _days([100, 102, 98, 101, 99, 400]), metrics=("cost_micros",)
    )
    assert len(findings) == 1
    assert findings[0]["direction"] == "spike" and findings[0]["date"] == "2026-10-06"


def test_steady_series_and_short_history_are_quiet():
    assert (
        analytics.detect_anomalies(_days([100, 101, 99, 100, 102]), metrics=("cost_micros",)) == []
    )
    assert analytics.detect_anomalies(_days([1, 900]), metrics=("cost_micros",)) == []


def test_drop_to_zero_after_flat_history_is_flagged():
    findings = analytics.detect_anomalies(
        _days([5, 5, 5, 5, 0], "conversions"), metrics=("conversions",)
    )
    assert findings and findings[0]["direction"] == "drop"


@given(
    st.lists(st.floats(min_value=0, max_value=1e9, allow_nan=False), min_size=3, max_size=30),
    st.floats(min_value=0, max_value=1e9),
)
def test_robust_z_is_finite(history: list[float], value: float):
    score = analytics.robust_z(history, value)
    assert score == score and abs(score) < float("inf")


def test_pacing_projects_and_classifies():
    today = dt.date(2026, 11, 11)  # 10 complete days
    rows = [
        {
            "campaign.id": "1",
            "campaign.name": "Fast",
            "campaign_budget.amount_micros": 10_000_000,
            "metrics.cost_micros": 150_000_000,
        },
        {
            "campaign.id": "2",
            "campaign.name": "Slow",
            "campaign_budget.amount_micros": 10_000_000,
            "metrics.cost_micros": 40_000_000,
        },
        {
            "campaign.id": "3",
            "campaign.name": "Ok",
            "campaign_budget.amount_micros": 10_000_000,
            "metrics.cost_micros": 100_000_000,
        },
        {
            "campaign.id": "4",
            "campaign.name": "NoBudget",
            "campaign_budget.amount_micros": 0,
            "metrics.cost_micros": 1,
        },
    ]
    by_name = {r["campaign"]: r for r in analytics.pacing(rows, today=today)}
    assert by_name["Fast"]["status"] == "overpacing" and by_name["Fast"]["projected_month"] == 450.0
    assert by_name["Slow"]["status"] == "underpacing"
    assert by_name["Ok"]["status"] == "on_pace"
    assert "NoBudget" not in by_name


def test_search_term_mining_returns_valid_ready_operations():
    rows = [
        {
            "search_term_view.search_term": "free shoes",
            "campaign.id": "1",
            "ad_group.id": "2",
            "metrics.cost_micros": 9_000_000,
            "metrics.clicks": 30,
            "metrics.conversions": 0,
        },
        {
            "search_term_view.search_term": "trail shoes men",
            "campaign.id": "1",
            "ad_group.id": "2",
            "metrics.cost_micros": 4_000_000,
            "metrics.clicks": 10,
            "metrics.conversions": 3,
        },
        {
            "search_term_view.search_term": "running shoes",
            "campaign.id": "1",
            "ad_group.id": "2",
            "metrics.cost_micros": 4_000_000,
            "metrics.clicks": 10,
            "metrics.conversions": 5,
        },
        {
            "search_term_view.search_term": "cheap",
            "campaign.id": "1",
            "ad_group.id": "2",
            "metrics.cost_micros": 1_000_000,
            "metrics.clicks": 2,
            "metrics.conversions": 0,
        },
    ]
    mined = analytics.mine_search_terms(rows, customer_id="9", keywords=["Running Shoes"])
    assert [n["term"] for n in mined["negative_keywords"]] == ["free shoes"]
    assert [a["term"] for a in mined["new_keywords"]] == ["trail shoes men"]
    validate_operations(
        [n["operation"] for n in mined["negative_keywords"] + mined["new_keywords"]], V
    )  # type: ignore[misc]


def test_reconcile_flags_gaps_per_day():
    ads = [
        {"segments.date": "2026-10-01", "metrics.conversions": 10},
        {"segments.date": "2026-10-02", "metrics.conversions": 10},
    ]
    ga4 = [{"date": "20261001", "keyEvents": "9"}, {"date": "20261002", "keyEvents": "4"}]
    out = analytics.reconcile(ads, ga4)
    assert out["flagged_days"] == 1 and out["ads_total"] == 20 and out["ga4_total"] == 13


def test_parse_json_object_tolerates_fences_and_prose():
    text = (
        'Here you go:\n```json\n{"headlines": ["A {b}", "C"], "descriptions": ["D"]}\n```\nThanks'
    )
    assert creative.parse_json_object(text)["headlines"] == ["A {b}", "C"]
    for bad in ("no json", '{"a": [1, 2}', "[1, 2]"):
        with pytest.raises(creative.CreativeError):
            creative.parse_json_object(bad)


def test_validated_copy_respects_limits_and_dedupes():
    payload = {
        "headlines": ["Run Fast", "run  fast", "x" * 31, "", "Free Returns", "New In"],
        "descriptions": ["Ok.", "y" * 91, "Fine too."],
    }
    out = creative.validated(payload, creative.SEARCH_LIMITS, {"headlines": 3, "descriptions": 2})
    assert out == {
        "headlines": ["Run Fast", "Free Returns", "New In"],
        "descriptions": ["Ok.", "Fine too."],
    }
    with pytest.raises(creative.CreativeError, match="headlines"):
        creative.validated(
            {"headlines": ["a"], "descriptions": ["b", "c"]},
            creative.SEARCH_LIMITS,
            {"headlines": 3, "descriptions": 2},
        )


def test_images_are_fitted_to_google_ads_specs():
    from PIL import Image

    from quantum_ads.connectors.insights.images import fit

    buffer = io.BytesIO()
    Image.new("RGB", (1792, 1024), (10, 20, 30)).save(buffer, format="PNG")
    source = base64.b64encode(buffer.getvalue()).decode()
    for kind, size in (("landscape", (1200, 628)), ("square", (1200, 1200))):
        with Image.open(io.BytesIO(base64.b64decode(fit(source, kind)))) as fitted:
            assert fitted.size == size


def test_parse_json_object_repairs_small_model_slips():
    text = '{"headlines": ["A", "B",],\n "descriptions": [\n  "one"\n  "two"\n ]}'
    assert creative.parse_json_object(text) == {
        "headlines": ["A", "B"],
        "descriptions": ["one", "two"],
    }


def test_repair_prompt_names_every_overlong_item():
    prompt = creative.repair_prompt(
        {"headlines": ["ok", "x" * 35], "descriptions": "short"}, creative.SEARCH_LIMITS
    )
    assert "has 35 characters (max 30)" in prompt and "return 4 items" in prompt
    assert '"descriptions": "short"' in prompt
