"""Write tools: Demand Gen campaigns, A/B experiments (create/schedule/promote/end), batch jobs."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastmcp import FastMCP

from ....core.context import ServerContext
from ....core.mcp.register import add_tool
from ....core.registry.registry import ToolSpec
from ....core.safety.write_executor import WriteExecutor
from .lifecycle import build_demand_gen_campaign, build_experiment
from .operations import InvalidOperation, validate_operations

MAX_BATCH_OPERATIONS = 1_000_000


def register_google_ads_lifecycle(app: FastMCP, ctx: ServerContext) -> list[ToolSpec]:
    def run(
        op: str, customer_id: str, batch: dict[str, object], confirm: str | None
    ) -> dict[str, object]:
        if ctx.mutate_factory is None:
            return {
                "error": {"code": "MUTATE_NOT_CONFIGURED", "message": "no mutate_factory wired"}
            }
        executor = WriteExecutor(ctx.mutate(), ctx.safety, ctx.audit)
        return executor.execute(op=op, customer_id=customer_id, operations=[batch], confirm=confirm)

    def invalid(exc: InvalidOperation) -> dict[str, object]:
        return {"applied": False, "error": {"code": "INVALID_OPERATION", "message": str(exc)}}

    def ads_campaign_create_demand_gen(
        customer_id: str,
        name: str,
        daily_budget_micros: int,
        final_url: str,
        business_name: str,
        headlines: list[str],
        descriptions: list[str],
        logo_base64: str,
        marketing_images_base64: list[str],
        square_images_base64: list[str],
        geo_target_ids: list[str] | None = None,
        language_ids: list[str] | None = None,
        target_cpa_micros: int | None = None,
        status: str = "PAUSED",
        confirm: str | None = None,
    ) -> dict[str, object]:
        try:
            operations = build_demand_gen_campaign(
                customer_id=customer_id,
                name=name,
                daily_budget_micros=daily_budget_micros,
                final_url=final_url,
                business_name=business_name,
                headlines=headlines,
                descriptions=descriptions,
                logo_base64=logo_base64,
                marketing_images_base64=marketing_images_base64,
                square_images_base64=square_images_base64,
                geo_target_ids=geo_target_ids or (),
                language_ids=language_ids or (),
                target_cpa_micros=target_cpa_micros,
                status=status,
            )
            validate_operations(operations, ctx.version)
        except InvalidOperation as exc:
            return invalid(exc)
        batch: dict[str, object] = {"entity": "mutate", "operations": operations}
        return run("ads.campaign.create_demand_gen", customer_id, batch, confirm)

    def ads_experiment_create(
        customer_id: str,
        name: str,
        base_campaign_id: str,
        treatment_traffic_percent: int = 50,
        suffix: str = "[experiment]",
        experiment_type: str = "SEARCH_CUSTOM",
        confirm: str | None = None,
    ) -> dict[str, object]:
        try:
            operations = build_experiment(
                customer_id=customer_id,
                name=name,
                base_campaign_id=base_campaign_id,
                treatment_traffic_percent=treatment_traffic_percent,
                suffix=suffix,
                experiment_type=experiment_type,
            )
            validate_operations(operations, ctx.version)
        except InvalidOperation as exc:
            return invalid(exc)
        batch: dict[str, object] = {"entity": "mutate", "operations": operations}
        return run("ads.experiment.create", customer_id, batch, confirm)

    def lifecycle(action: str) -> Callable[..., dict[str, object]]:
        def tool(
            customer_id: str, experiment: str, confirm: str | None = None
        ) -> dict[str, object]:
            batch: dict[str, object] = {
                "entity": f"experiment_{action}",
                "resource_name": experiment,
            }
            return run(f"ads.experiment.{action}", customer_id, batch, confirm)

        return tool

    def ads_batch_submit(
        customer_id: str, operations: list[dict[str, Any]], confirm: str | None = None
    ) -> dict[str, object]:
        if len(operations) > MAX_BATCH_OPERATIONS:
            return invalid(InvalidOperation(f"more than {MAX_BATCH_OPERATIONS} operations"))
        try:
            validate_operations(operations, ctx.version)
        except InvalidOperation as exc:
            return invalid(exc)
        batch: dict[str, object] = {"entity": "batch_submit", "operations": operations}
        return run("ads.batch.submit", customer_id, batch, confirm)

    tools: list[tuple[str, str, Callable[..., Any]]] = [
        (
            "ads.campaign.create_demand_gen",
            "Create a complete Demand Gen campaign in one atomic call: budget, campaign, ad group "
            "targeting, image/logo assets and a multi-asset ad.",
            ads_campaign_create_demand_gen,
        ),
        (
            "ads.experiment.create",
            "Create an A/B experiment on a campaign: control + treatment arms with a traffic split. "
            "Edit the treatment draft (arm in_design_campaigns) with ads.mutate, then schedule.",
            ads_experiment_create,
        ),
        ("ads.experiment.schedule", "Start (schedule) an experiment.", lifecycle("schedule")),
        (
            "ads.experiment.promote",
            "Promote an experiment's treatment changes to the base campaign.",
            lifecycle("promote"),
        ),
        ("ads.experiment.end", "End a running experiment.", lifecycle("end")),
        (
            "ads.batch.submit",
            "Submit a large mutation (thousands of MutateOperations) as an asynchronous BatchJob; "
            "track it with ads.batch.status.",
            ads_batch_submit,
        ),
    ]
    for name, description, fn in tools:
        add_tool(app, name, description, fn)
    return [ToolSpec(name=n, summary=d, read_only=False) for n, d, _ in tools]
