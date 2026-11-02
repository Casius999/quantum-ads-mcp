"""Google Ads generic mutate: offline validation against the v26 protos, schema, builders."""

from __future__ import annotations

import pytest

from quantum_ads.connectors.google_ads.write.operations import (
    InvalidOperation,
    build_search_campaign,
    operation_kinds,
    resource_fields,
    validate_operations,
)
from quantum_ads.core.versioning.version_manager import DEFAULT_API_VERSION as V


def test_every_mutable_resource_is_reachable():
    kinds = operation_kinds(V)
    assert len(kinds) >= 60
    assert {"campaign_operation", "asset_group_operation", "experiment_operation"} <= set(kinds)


def test_schema_lists_the_resource_fields():
    schema = resource_fields(V, "campaign_budget_operation")
    assert schema["resource"].endswith("CampaignBudget")  # type: ignore[union-attr]
    assert schema["fields"]["amount_micros"] == "int64"  # type: ignore[index]
    with pytest.raises(InvalidOperation, match="unknown operation kind"):
        resource_fields(V, "nope_operation")


def test_valid_operations_parse_and_typos_are_located():
    ops = [
        {
            "campaign_operation": {
                "update": {"resource_name": "customers/1/campaigns/2", "status": "PAUSED"},
                "update_mask": "status",
            }
        },
    ]
    assert len(validate_operations(ops, V)) == 1
    with pytest.raises(InvalidOperation, match="operation 1: .*nme"):
        validate_operations([*ops, {"campaign_operation": {"create": {"nme": "x"}}}], V)
    with pytest.raises(InvalidOperation, match="exactly one"):
        validate_operations([{"a": {}, "b": {}}], V)
    with pytest.raises(InvalidOperation, match="empty"):
        validate_operations([], V)


def _search(**overrides: object) -> list[dict[str, object]]:
    args: dict[str, object] = {
        "customer_id": "123",
        "name": "Brand FR",
        "daily_budget_micros": 20_000_000,
        "final_url": "https://example.com",
        "keywords": ["chaussures running", "basket course"],
        "headlines": ["Chaussures Running", "Livraison Gratuite", "Nouvelle Collection"],
        "descriptions": ["Les meilleures chaussures.", "Retours gratuits sous 30 jours."],
        "geo_target_ids": ["2250"],
        "language_ids": ["1002"],
        "negative_keywords": ["gratuit"],
    }
    args.update(overrides)
    return build_search_campaign(**args)  # type: ignore[arg-type]


def test_search_campaign_is_a_valid_linked_operation_list():
    ops = _search()
    parsed = validate_operations(ops, V)  # every built operation matches the API schema
    kinds = [next(iter(op)) for op in ops]
    assert kinds[:2] == ["campaign_budget_operation", "campaign_operation"]
    assert kinds.count("ad_group_criterion_operation") == 2
    assert kinds[-1] == "ad_group_ad_operation"
    campaign = ops[1]["campaign_operation"]["create"]  # type: ignore[index]
    assert campaign["campaign_budget"] == "customers/123/campaignBudgets/-1"
    assert campaign["status"] == "PAUSED"
    assert len(parsed) == len(ops)


def test_search_campaign_rejects_invalid_creatives():
    with pytest.raises(InvalidOperation, match="3 to 15 headlines"):
        _search(headlines=["a", "b"])
    with pytest.raises(InvalidOperation, match="over 30"):
        _search(headlines=["x" * 31, "b", "c"])
    with pytest.raises(InvalidOperation, match="bidding"):
        _search(bidding="WHATEVER")


def test_target_cpa_and_other_bidding_strategies_validate():
    for bidding, extra in (
        ("MAXIMIZE_CONVERSIONS", {"target_cpa_micros": 5_000_000}),
        ("MAXIMIZE_CLICKS", {}),
        ("MANUAL_CPC", {}),
    ):
        validate_operations(_search(bidding=bidding, **extra), V)
