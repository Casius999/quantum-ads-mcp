"""Performance Max builder: complete, linked, schema-valid; creative limits enforced."""

from __future__ import annotations

import base64

import pytest

from quantum_ads.connectors.google_ads.write.operations import InvalidOperation, validate_operations
from quantum_ads.connectors.google_ads.write.pmax import build_pmax_campaign
from quantum_ads.core.versioning.version_manager import DEFAULT_API_VERSION as V

_IMG = base64.b64encode(b"\x89PNG fake").decode()


def _pmax(**overrides: object) -> list[dict[str, object]]:
    args: dict[str, object] = {
        "customer_id": "1",
        "name": "PMax",
        "daily_budget_micros": 5_000_000,
        "final_url": "https://example.com",
        "business_name": "Example",
        "headlines": ["One", "Two", "Three"],
        "long_headlines": ["A longer headline for the campaign"],
        "descriptions": ["Short description.", "Another description that is fine."],
        "logo_base64": _IMG,
        "images": [
            {"field_type": "MARKETING_IMAGE", "data_base64": _IMG},
            {"field_type": "SQUARE_MARKETING_IMAGE", "data_base64": _IMG},
        ],
        "geo_target_ids": ["2250"],
    }
    args.update(overrides)
    return build_pmax_campaign(**args)  # type: ignore[arg-type]


def test_pmax_is_one_valid_linked_batch():
    ops = _pmax()
    assert len(validate_operations(ops, V)) == len(ops)
    kinds = [next(iter(op)) for op in ops]
    assert kinds.count("asset_operation") == 2 + 6 + 2  # brand + texts + images
    assert kinds.count("asset_group_asset_operation") == 8
    assert kinds[-2:] == ["campaign_asset_operation", "campaign_asset_operation"]
    campaign = ops[1]["campaign_operation"]["create"]  # type: ignore[index]
    assert campaign["advertising_channel_type"] == "PERFORMANCE_MAX"
    assert campaign["brand_guidelines_enabled"] is True


def test_value_bidding_with_target_roas_validates():
    validate_operations(_pmax(bidding="MAXIMIZE_CONVERSION_VALUE", target_roas=4.0), V)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"headlines": ["a", "b"]}, "headlines: 3 to 15"),
        ({"long_headlines": []}, "long_headlines: 1 to 5"),
        ({"descriptions": ["x" * 70, "y" * 70]}, "60 characters"),
        ({"business_name": "x" * 26}, "business_name"),
        (
            {"images": [{"field_type": "MARKETING_IMAGE", "data_base64": _IMG}]},
            "SQUARE_MARKETING_IMAGE",
        ),
        ({"bidding": "MANUAL_CPC"}, "bidding"),
    ],
)
def test_creative_and_bidding_limits(overrides: dict[str, object], message: str):
    with pytest.raises(InvalidOperation, match=message):
        _pmax(**overrides)
