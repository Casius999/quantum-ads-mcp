"""Mount the Meridian MMM tools onto the FastMCP app + register their capabilities.

The single backend is keyed ``"meridian.api"`` (a ``ReadFn`` dispatching summary/roi/optimize/fit).
It is read lazily per call via ``ctx.backend(...)`` so the connector degrades gracefully (structured
``BACKEND_NOT_CONFIGURED`` error) when the backend is not wired.

All four tools are flagged ``read_only=True``: they perform no account mutation and are therefore
NOT guarded by the ``WriteExecutor`` (no validate-only preview / two-step confirm). NOTE that
``meridian.fit`` is **compute-heavy** (Bayesian MCMC sampling, minutes-to-hours) — "read-only" means
"no marketing-account side effects", not "cheap"; each tool description documents this.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from fastmcp import FastMCP

from ...core.context import ServerContext
from ...core.mcp.register import add_tool
from ...core.registry.registry import Capability, ToolSpec
from . import mmm_tools
from .mmm_tools import DEFAULT_TOTAL_BUDGET
from .types import ReadFn

BACKEND_KEY = "meridian.api"

_NOT_CONFIGURED: dict[str, object] = {
    "error": {"code": "BACKEND_NOT_CONFIGURED", "message": f"{BACKEND_KEY} not wired"}
}


def register_meridian(app: FastMCP, ctx: ServerContext) -> None:
    def backend() -> ReadFn | None:
        raw = ctx.backend(BACKEND_KEY)
        if raw is None:
            return None
        return cast(ReadFn, raw)

    def meridian_model_summary(model_id: str) -> dict[str, object]:
        read = backend()
        if read is None:
            return dict(_NOT_CONFIGURED)
        return mmm_tools.model_summary(model_id=model_id, read=read)

    def meridian_roi_by_channel(model_id: str) -> dict[str, object]:
        read = backend()
        if read is None:
            return dict(_NOT_CONFIGURED)
        return mmm_tools.roi_by_channel(model_id=model_id, read=read)

    def meridian_budget_optimize(
        model_id: str, total_budget: int = DEFAULT_TOTAL_BUDGET
    ) -> dict[str, object]:
        read = backend()
        if read is None:
            return dict(_NOT_CONFIGURED)
        return mmm_tools.optimize_budget(model_id=model_id, total_budget=total_budget, read=read)

    def meridian_fit(dataset_ref: str, config: dict[str, object]) -> dict[str, object]:
        read = backend()
        if read is None:
            return dict(_NOT_CONFIGURED)
        return mmm_tools.fit_model(dataset_ref=dataset_ref, config=config, read=read)

    tools: list[tuple[str, str, Callable[..., Any]]] = [
        (
            "meridian.model.summary",
            "Fit-summary rows for an already-fitted MMM (by model_id). Read-only; cheap.",
            meridian_model_summary,
        ),
        (
            "meridian.roi.by_channel",
            "Per-channel ROI / contribution rows for a fitted MMM (by model_id). Read-only.",
            meridian_roi_by_channel,
        ),
        (
            "meridian.budget.optimize",
            "Optimal per-channel allocation for total_budget under a fitted MMM. "
            "Read-only (recommends only); may run posterior simulations.",
            meridian_budget_optimize,
        ),
        (
            "meridian.fit",
            "Fit a Bayesian MMM on dataset_ref with config; returns a model/job handle. "
            "Read-only (no account mutation) but COMPUTE-HEAVY: MCMC sampling, minutes-to-hours.",
            meridian_fit,
        ),
    ]
    for name, description, fn in tools:
        add_tool(app, name, description, fn)

    ctx.registry.register(
        Capability(
            connector="meridian",
            domain="read",
            tools=[ToolSpec(name=name, summary=description) for name, description, _ in tools],
        )
    )
