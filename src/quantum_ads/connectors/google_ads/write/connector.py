"""Mount guarded Google Ads write tools (mutations) onto the FastMCP app."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastmcp import FastMCP

from ....core.context import ServerContext
from ....core.mcp.register import add_tool
from ....core.registry.registry import Capability, ToolSpec
from .executor import WriteExecutor
from .mutate_tools import build_set_campaign_status_ops, build_update_budget_ops

_NOT_CONFIGURED: dict[str, object] = {
    "error": {"code": "MUTATE_NOT_CONFIGURED", "message": "no mutate_factory wired"}
}


def register_google_ads_write(app: FastMCP, ctx: ServerContext) -> None:
    holder: dict[str, WriteExecutor] = {}

    def executor() -> WriteExecutor | None:
        if ctx.mutate_factory is None:
            return None
        if "ex" not in holder:
            holder["ex"] = WriteExecutor(
                ctx.mutate_factory(ctx.creds, ctx.version), ctx.safety, ctx.audit
            )
        return holder["ex"]

    def ads_campaign_set_status(
        customer_id: str, campaign_id: str, status: str, confirm: str | None = None
    ) -> dict[str, object]:
        ex = executor()
        if ex is None:
            return dict(_NOT_CONFIGURED)
        return ex.execute(
            op="ads.campaign.set_status",
            customer_id=customer_id,
            operations=build_set_campaign_status_ops(campaign_id, status),
            confirm=confirm,
        )

    def ads_budget_update(
        customer_id: str, budget_id: str, amount_micros: int, confirm: str | None = None
    ) -> dict[str, object]:
        ex = executor()
        if ex is None:
            return dict(_NOT_CONFIGURED)
        return ex.execute(
            op="ads.budget.update",
            customer_id=customer_id,
            operations=build_update_budget_ops(budget_id, amount_micros),
            confirm=confirm,
        )

    tools: list[tuple[str, str, Callable[..., Any]]] = [
        (
            "ads.campaign.set_status",
            "Pause/enable a campaign (guarded: validate_only preview + confirm token).",
            ads_campaign_set_status,
        ),
        (
            "ads.budget.update",
            "Update a campaign budget amount in micros (guarded).",
            ads_budget_update,
        ),
    ]
    for name, description, fn in tools:
        add_tool(app, name, description, fn)

    ctx.registry.register(
        Capability(
            connector="google_ads",
            domain="write",
            tools=[
                ToolSpec(name=name, summary=description, read_only=False)
                for name, description, _ in tools
            ],
        )
    )
