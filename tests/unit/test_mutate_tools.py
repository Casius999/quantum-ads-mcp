from quantum_ads.connectors.google_ads.write.mutate_tools import (
    build_set_campaign_status_ops,
    build_update_budget_ops,
)


def test_set_campaign_status_ops():
    ops = build_set_campaign_status_ops("123", "PAUSED")
    assert ops == [
        {"entity": "campaign", "action": "update", "campaign_id": "123", "status": "PAUSED"}
    ]


def test_update_budget_ops_coerces_amount_to_int():
    ops = build_update_budget_ops("456", 5_000_000)
    assert ops[0]["entity"] == "campaign_budget"
    assert ops[0]["amount_micros"] == 5_000_000
