"""Demand Gen and experiment builders: schema-valid, linked, limits enforced."""

from __future__ import annotations

import base64

import pytest

from quantum_ads.connectors.google_ads.write.lifecycle import (
    build_demand_gen_campaign,
    build_experiment,
)
from quantum_ads.connectors.google_ads.write.operations import InvalidOperation, validate_operations
from quantum_ads.core.versioning.version_manager import DEFAULT_API_VERSION as V

_IMG = base64.b64encode(b"\x89PNG fake").decode()


def _demand_gen(**overrides: object) -> list[dict[str, object]]:
    args: dict[str, object] = {
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
        "geo_target_ids": ["2250"],
        "language_ids": ["1002"],
    }
    args.update(overrides)
    return build_demand_gen_campaign(**args)  # type: ignore[arg-type]


def test_demand_gen_is_one_valid_batch_with_ad_group_targeting():
    ops = _demand_gen()
    assert len(validate_operations(ops, V)) == len(ops)
    kinds = [next(iter(op)) for op in ops]
    assert kinds.count("ad_group_criterion_operation") == 2
    assert kinds[-1] == "ad_group_ad_operation"
    campaign = ops[1]["campaign_operation"]["create"]  # type: ignore[index]
    assert campaign["advertising_channel_type"] == "DEMAND_GEN"


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"headlines": []}, "headlines"),
        ({"descriptions": ["x" * 91]}, "descriptions"),
        ({"square_images_base64": []}, "square image"),
        ({"business_name": "x" * 26}, "business_name"),
    ],
)
def test_demand_gen_limits(overrides: dict[str, object], message: str):
    with pytest.raises(InvalidOperation, match=message):
        _demand_gen(**overrides)


def test_experiment_has_control_and_treatment_arms():
    ops = build_experiment(
        customer_id="1", name="E", base_campaign_id="9", treatment_traffic_percent=30
    )
    validate_operations(ops, V)
    control = ops[1]["experiment_arm_operation"]["create"]  # type: ignore[index]
    treatment = ops[2]["experiment_arm_operation"]["create"]  # type: ignore[index]
    assert control["control"] is True and control["traffic_split"] == 70
    assert control["campaigns"] == ["customers/1/campaigns/9"]
    assert treatment["control"] is False and treatment["traffic_split"] == 30
    with pytest.raises(InvalidOperation, match="between 1 and 99"):
        build_experiment(
            customer_id="1", name="E", base_campaign_id="9", treatment_traffic_percent=0
        )
