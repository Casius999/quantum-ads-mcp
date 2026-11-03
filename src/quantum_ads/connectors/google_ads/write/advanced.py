"""Google Ads write tools beyond single-field edits: any mutation, full campaigns, recommendations.

All of them run through the shared ``WriteExecutor`` (read-only/scope guard, optional policy,
validate_only preview, commit per the write mode, signed audit) and are validated offline
against the pinned API version before any network call.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastmcp import FastMCP

from ....core.context import ServerContext
from ....core.mcp.register import add_tool
from ....core.registry.registry import ToolSpec
from ....core.safety.write_executor import WriteExecutor
from ....core.tenancy import current_principal
from .operations import InvalidOperation, build_search_campaign, validate_operations
from .pmax import build_pmax_campaign
from .rollback import with_update_masks

_NOT_CONFIGURED: dict[str, object] = {
    "error": {"code": "MUTATE_NOT_CONFIGURED", "message": "no mutate_factory wired"}
}


def _invalid(exc: InvalidOperation) -> dict[str, object]:
    return {"applied": False, "error": {"code": "INVALID_OPERATION", "message": str(exc)}}


def register_google_ads_advanced_write(app: FastMCP, ctx: ServerContext) -> list[ToolSpec]:
    def run(
        op: str, customer_id: str, operations: list[dict[str, object]], confirm: str | None
    ) -> dict[str, object]:
        if ctx.mutate_factory is None:
            return dict(_NOT_CONFIGURED)
        executor = WriteExecutor(ctx.mutate(), ctx.safety, ctx.audit)
        return executor.execute(
            op=op, customer_id=customer_id, operations=operations, confirm=confirm
        )

    def ads_mutate(
        customer_id: str,
        operations: list[dict[str, Any]],
        partial_failure: bool = False,
        confirm: str | None = None,
    ) -> dict[str, object]:
        operations = with_update_masks(operations)
        try:
            validate_operations(operations, ctx.version)
        except InvalidOperation as exc:
            return _invalid(exc)
        batch: dict[str, object] = {
            "entity": "mutate",
            "operations": operations,
            "partial_failure": partial_failure,
        }
        return run("ads.mutate", customer_id, [batch], confirm)

    def ads_campaign_create_search(
        customer_id: str,
        name: str,
        daily_budget_micros: int,
        final_url: str,
        keywords: list[str],
        headlines: list[str],
        descriptions: list[str],
        geo_target_ids: list[str] | None = None,
        language_ids: list[str] | None = None,
        negative_keywords: list[str] | None = None,
        match_type: str = "PHRASE",
        bidding: str = "MAXIMIZE_CONVERSIONS",
        target_cpa_micros: int | None = None,
        status: str = "PAUSED",
        confirm: str | None = None,
    ) -> dict[str, object]:
        try:
            operations = build_search_campaign(
                customer_id=customer_id,
                name=name,
                daily_budget_micros=daily_budget_micros,
                final_url=final_url,
                keywords=keywords,
                headlines=headlines,
                descriptions=descriptions,
                geo_target_ids=geo_target_ids or (),
                language_ids=language_ids or (),
                negative_keywords=negative_keywords or (),
                match_type=match_type,
                bidding=bidding,
                target_cpa_micros=target_cpa_micros,
                status=status,
            )
            validate_operations(operations, ctx.version)
        except InvalidOperation as exc:
            return _invalid(exc)
        batch: dict[str, object] = {"entity": "mutate", "operations": operations}
        return run("ads.campaign.create_search", customer_id, [batch], confirm)

    def ads_campaign_create_pmax(
        customer_id: str,
        name: str,
        daily_budget_micros: int,
        final_url: str,
        business_name: str,
        headlines: list[str],
        long_headlines: list[str],
        descriptions: list[str],
        logo_base64: str,
        images: list[dict[str, str]],
        geo_target_ids: list[str] | None = None,
        language_ids: list[str] | None = None,
        bidding: str = "MAXIMIZE_CONVERSIONS",
        target_cpa_micros: int | None = None,
        target_roas: float | None = None,
        status: str = "PAUSED",
        confirm: str | None = None,
    ) -> dict[str, object]:
        try:
            operations = build_pmax_campaign(
                customer_id=customer_id,
                name=name,
                daily_budget_micros=daily_budget_micros,
                final_url=final_url,
                business_name=business_name,
                headlines=headlines,
                long_headlines=long_headlines,
                descriptions=descriptions,
                logo_base64=logo_base64,
                images=images,
                geo_target_ids=geo_target_ids or (),
                language_ids=language_ids or (),
                bidding=bidding,
                target_cpa_micros=target_cpa_micros,
                target_roas=target_roas,
                status=status,
            )
            validate_operations(operations, ctx.version)
        except InvalidOperation as exc:
            return _invalid(exc)
        batch: dict[str, object] = {"entity": "mutate", "operations": operations}
        return run("ads.campaign.create_pmax", customer_id, [batch], confirm)

    def ads_rollback(
        audit_index: int | None = None, confirm: str | None = None
    ) -> dict[str, object]:
        principal = current_principal()
        tenant = principal.tenant_id if principal is not None else None
        records = list(ctx.audit.records)
        candidates = [
            (index, record)
            for index, record in enumerate(records)
            if record.op.startswith("ads.")
            and record.payload.get("inverse_operations")
            and (tenant is None or record.actor.split(":", 1)[0] == tenant)
        ]
        if audit_index is not None:
            candidates = [(i, r) for i, r in candidates if i == audit_index]
        if not candidates:
            return _invalid(InvalidOperation("no reversible Google Ads change found in the audit"))
        index, record = candidates[-1]
        inverse = list(record.payload["inverse_operations"])  # type: ignore[call-overload]
        batch: dict[str, object] = {"entity": "mutate", "operations": inverse}
        result = run("ads.rollback", str(record.payload["customer_id"]), [batch], confirm)
        return {**result, "rolled_back": {"audit_index": index, "op": record.op, "ts": record.ts}}

    def recommendations(entity: str, op: str) -> Callable[..., dict[str, object]]:
        def tool(
            customer_id: str, resource_names: list[str], confirm: str | None = None
        ) -> dict[str, object]:
            if not resource_names:
                return _invalid(InvalidOperation("resource_names is empty"))
            batch: dict[str, object] = {"entity": entity, "resource_names": resource_names}
            return run(op, customer_id, [batch], confirm)

        return tool

    tools: list[tuple[str, str, Callable[..., Any]]] = [
        (
            "ads.mutate",
            "Create/update/remove ANY Google Ads resource: MutateOperation JSON list "
            "(e.g. {'campaign_operation': {'create': {...}}}), temporary ids (-1) link new "
            "objects, atomic unless partial_failure. See ads.mutate.schema.",
            ads_mutate,
        ),
        (
            "ads.campaign.create_search",
            "Create a complete Search campaign in one atomic call: budget, bidding, geo/language "
            "targeting, negatives, ad group, keywords and a responsive search ad.",
            ads_campaign_create_search,
        ),
        (
            "ads.campaign.create_pmax",
            "Create a complete Performance Max campaign in one atomic call: budget, bidding, "
            "targeting, text + image assets (base64, e.g. from vertex.imagen.generate), asset "
            "group, and brand assets (business name, logo) under brand guidelines.",
            ads_campaign_create_pmax,
        ),
        (
            "ads.rollback",
            "Undo a Google Ads change from the signed audit trail (latest reversible change of "
            "this tenant, or audit_index): restores updated fields, removes created objects.",
            ads_rollback,
        ),
        (
            "ads.recommendations.apply",
            "Apply Google Ads recommendations by resource name (from ads.recommendations.list).",
            recommendations("recommendation_apply", "ads.recommendations.apply"),
        ),
        (
            "ads.recommendations.dismiss",
            "Dismiss Google Ads recommendations by resource name.",
            recommendations("recommendation_dismiss", "ads.recommendations.dismiss"),
        ),
    ]
    for name, description, fn in tools:
        add_tool(app, name, description, fn)
    return [ToolSpec(name=n, summary=d, read_only=False) for n, d, _ in tools]
