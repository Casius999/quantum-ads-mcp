"""Pure operation builders for Google Ads mutations (entity-agnostic dict operations)."""

from __future__ import annotations


def build_set_campaign_status_ops(campaign_id: str, status: str) -> list[dict[str, object]]:
    op: dict[str, object] = {
        "entity": "campaign",
        "action": "update",
        "campaign_id": campaign_id,
        "status": status,
    }
    return [op]


def build_update_budget_ops(budget_id: str, amount_micros: int) -> list[dict[str, object]]:
    op: dict[str, object] = {
        "entity": "campaign_budget",
        "action": "update",
        "budget_id": budget_id,
        "amount_micros": int(amount_micros),
    }
    return [op]
