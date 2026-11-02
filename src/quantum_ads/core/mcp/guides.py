"""MCP resources (context the agent can read) and prompts (end-to-end playbooks).

Resources give the agent the facts it needs without spending tool calls: what this server can
do, the Google Ads version calendar, the curated field deltas, and who it is acting as (tenant,
scopes, write mode, effective policy). Prompts are playbooks that chain existing tools into a
complete job — audit, diagnose, mine, reallocate, optimise — and end with concrete actions.
Every tool a prompt names is checked against the registry by tests.
"""

from __future__ import annotations

import dataclasses
import datetime as dt

from fastmcp import FastMCP

from ...connectors.google_ads.catalogs import deltas_2026
from ..context import ServerContext
from ..tenancy import current_principal
from ..versioning.version_manager import DEFAULT_API_VERSION, SUNSET_SCHEDULE

_FOOTER = (
    "Decide and act: you hold the data. Prefer GAQL date ranges of the last 30 days unless "
    "asked otherwise, convert *_micros to currency (/1,000,000), and finish with a ranked list of "
    "actions with expected impact. Apply the ones you are confident in with the write tools "
    "(validate_only runs first; a failed validation never applies)."
)

PROMPTS: dict[str, tuple[str, str]] = {
    "weekly_account_audit": (
        "Full weekly audit of a Google Ads account with prioritised fixes.",
        "Audit Google Ads customer {customer_id}.\n"
        "1. ads.report.campaign for spend, conversions, CPA/ROAS per campaign vs the prior week.\n"
        "2. ads.report.search_terms for wasted spend (cost, zero conversions) and new winners.\n"
        "3. ads.report.pmax_asset_groups and ads.report.ai_max for automation performance.\n"
        "4. ads.report.conversions to check conversion actions are recording.\n"
        "5. ads.change_history for what changed this week and its effect.\n"
        "6. ads.gaql.query for anything else you need (budgets, impression share, auctions).",
    ),
    "pmax_diagnosis": (
        "Diagnose a Performance Max campaign and its asset groups.",
        "Diagnose Performance Max campaign {campaign_id} in customer {customer_id}.\n"
        "1. ads.report.pmax_asset_groups: spend, conversions and ad strength per asset group.\n"
        "2. ads.gaql.query on asset_group_asset for low-performing assets and missing formats.\n"
        "3. ads.report.search_terms (campaign insights) for query themes and brand leakage.\n"
        "4. Generate replacement copy with vertex.gemini.generate_ad_copy, images with "
        "vertex.imagen.generate and a short video with video.generate for weak formats.",
    ),
    "search_terms_mining": (
        "Mine search terms for negatives and new keyword opportunities.",
        "Mine search terms for customer {customer_id} over the last {days} days.\n"
        "1. ads.report.search_terms: cost, clicks, conversions per term.\n"
        "2. Cluster terms by intent; flag irrelevant or non-converting spend as negatives.\n"
        "3. Flag converting terms not yet targeted as new keywords.\n"
        "4. Cross-check demand with trends.related_queries and searchconsole.search_analytics.",
    ),
    "budget_reallocation": (
        "Reallocate budget across campaigns using performance and marginal ROI.",
        "Reallocate budget for customer {customer_id}.\n"
        "1. ads.report.campaign: spend, conversions, value and lost impression share (budget).\n"
        "2. If a Meridian model exists, meridian.roi.by_channel and meridian.budget.optimize.\n"
        "3. Move budget from saturated or inefficient campaigns to budget-limited efficient "
        "ones; apply with ads.budget.update.",
    ),
    "merchant_feed_optimization": (
        "Fix product issues and improve titles/descriptions in Merchant Center.",
        "Optimise the Merchant Center feed of account {merchant_id}.\n"
        "1. merchant.product_statuses.list for disapprovals and warnings; fix with "
        "merchant.product.update.\n"
        "2. merchant.products.list; rewrite weak titles and descriptions with "
        "vertex.gemini.generate (brand, product type, key attributes first), then "
        "merchant.product.update.",
    ),
    "ga4_ads_reconciliation": (
        "Reconcile Google Ads conversions with GA4 and find tracking gaps.",
        "Reconcile Google Ads customer {customer_id} with GA4 property {property_id}.\n"
        "1. ads.report.conversions per conversion action and day.\n"
        "2. ga4.report for the matching key events (session source google / cpc) and "
        "ga4.admin.list_key_events.\n"
        "3. Explain gaps (attribution model, conversion lag, consent, missing key events); "
        "create missing key events with ga4.admin.create_key_event; upload offline "
        "conversions with datamanager.conversions.upload when the CRM has them.",
    ),
    "demand_research": (
        "Research demand and seasonality before launching or scaling.",
        "Research demand for {topic} in {geo}.\n"
        "1. trends.interest_over_time and trends.interest_by_region for seasonality and geography.\n"
        "2. trends.related_queries and trends.trending_now for rising themes.\n"
        "3. searchconsole.search_analytics for organic demand already captured.\n"
        "4. Recommend campaign themes, geos, timing and budget weighting.",
    ),
    "creative_studio": (
        "Produce a complete creative pack (copy, images, video) for a product or offer.",
        "Produce a creative pack for {product} aimed at {audience}.\n"
        "1. vertex.gemini.generate_ad_copy for responsive search ad headlines (30 chars) and "
        "descriptions (90 chars).\n"
        "2. vertex.imagen.generate for landscape, square and portrait images.\n"
        "3. video.generate (free) for a short vertical and a landscape video.\n"
        "4. Return the assets with the formats each Google Ads placement needs.",
    ),
}


def register_guides(app: FastMCP, ctx: ServerContext) -> None:
    @app.resource("quantum-ads://capabilities", name="capabilities", mime_type="application/json")
    def capabilities() -> dict[str, object]:
        """Every connector, its domain and tools (read vs write)."""
        return {
            "connectors": [
                {
                    "connector": cap.connector,
                    "domain": cap.domain,
                    "tools": [
                        {"name": t.name, "summary": t.summary, "read_only": t.read_only}
                        for t in cap.tools
                    ],
                }
                for cap in ctx.registry.list_capabilities()
            ]
        }

    @app.resource(
        "quantum-ads://google-ads/versions",
        name="google_ads_versions",
        mime_type="application/json",
    )
    def versions() -> dict[str, object]:
        """Google Ads API versions, sunset dates and the version this server targets."""
        today = dt.date.today()
        return {
            "server_version": ctx.version,
            "default_version": DEFAULT_API_VERSION,
            "versions": {
                version: {"sunset": sunset.isoformat(), "days_left": (sunset - today).days}
                for version, sunset in sorted(SUNSET_SCHEDULE.items())
            },
        }

    @app.resource(
        "quantum-ads://google-ads/field-deltas",
        name="google_ads_field_deltas",
        mime_type="application/json",
    )
    def field_deltas() -> dict[str, object]:
        """Curated 2026 Google Ads surface changes (new views, metrics, removals)."""
        return {
            "new_views": deltas_2026.NEW_VIEWS_2026,
            "new_metric_families": deltas_2026.NEW_METRIC_FAMILIES_2026,
            "new_segment_families": deltas_2026.NEW_SEGMENT_FAMILIES_2026,
            "removed_fields": deltas_2026.REMOVED_FIELDS_2026,
            "new_resources_v25_v26": deltas_2026.NEW_RESOURCES_V25_V26,
        }

    @app.resource("quantum-ads://session", name="session", mime_type="application/json")
    def session() -> dict[str, object]:
        """Who the server acts as: tenant, scopes, write mode and the effective policy."""
        principal = current_principal()
        tenant = principal.tenant_id if principal is not None else "operator"
        policy = ctx.safety.policy_for(tenant)
        return {
            "tenant": tenant,
            "subject": principal.subject if principal is not None else None,
            "scopes": sorted(principal.scopes) if principal is not None else None,
            "read_only": ctx.safety.read_only,
            "write_mode": ctx.safety.write_mode,
            "policy": (
                {
                    f.name: getattr(policy, f.name)
                    for f in dataclasses.fields(policy)
                    if not f.name.startswith("_")
                }
                if policy is not None
                else None
            ),
        }

    for name, (description, template) in PROMPTS.items():
        _register_prompt(app, name, description, template)


def _register_prompt(app: FastMCP, name: str, description: str, template: str) -> None:
    import string

    fields = sorted({f for _, f, _, _ in string.Formatter().parse(template) if f})
    defaults = {"days": "30", "geo": "the target country"}

    def render(**kwargs: str) -> str:
        values = {**defaults, **{k: v for k, v in kwargs.items() if v}}
        return template.format(**values) + "\n\n" + _FOOTER

    # FastMCP derives prompt arguments from the signature, so build one with these fields.
    import inspect

    params = [
        inspect.Parameter(
            f,
            inspect.Parameter.KEYWORD_ONLY,
            annotation=str,
            default=defaults.get(f, inspect.Parameter.empty),
        )
        for f in fields
    ]
    render.__signature__ = inspect.Signature(params, return_annotation=str)  # type: ignore[attr-defined]
    render.__annotations__ = {**{f: str for f in fields}, "return": str}
    render.__name__ = name
    render.__doc__ = description
    app.prompt(name=name, description=description)(render)
