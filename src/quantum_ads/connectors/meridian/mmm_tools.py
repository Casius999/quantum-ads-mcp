"""Meridian MMM tools: model summary, per-channel ROI, budget optimization, model fitting.

Pure builders (``build_*``) construct the params dict handed to the injected backend ``ReadFn``;
the thin tool wrappers (``model_summary`` / ``roi_by_channel`` / ``optimize_budget`` / ``fit_model``)
do the None-check + structured error envelope and wrap the returned rows in the shared
``{"rows", "row_count"}`` envelope, matching the other read connectors. The backend ReadFn signature
is ``(operation, params) -> rows`` where operation is one of
``"summary"`` / ``"roi"`` / ``"optimize"`` / ``"fit"``.

NOTE: Meridian is a Bayesian MMM (TensorFlow Probability under the hood). ``fit_model`` kicks off
MCMC sampling and is **compute-heavy** (minutes-to-hours on real data) — it is "read-only" only in
the sense that it never mutates a marketing account; it is intentionally not guarded by the
WriteExecutor. The read-back tools (summary/roi/optimize) operate on an already-fitted ``model_id``
and are comparatively cheap, though ``optimize`` may itself run posterior simulations.
"""

from __future__ import annotations

from .types import ReadFn

# Operation names passed as the first ReadFn argument (one per MMM call).
OP_SUMMARY = "summary"
OP_ROI = "roi"
OP_OPTIMIZE = "optimize"
OP_FIT = "fit"

# Default total budget (in account currency minor/major units, backend-defined) for optimization
# when the caller does not supply one. Conservative placeholder; the operator overrides per call.
DEFAULT_TOTAL_BUDGET = 100_000


def _wrap(rows: list[dict[str, object]]) -> dict[str, object]:
    """Wrap MMM result rows in the shared read envelope."""
    return {"rows": rows, "row_count": len(rows)}


# --- pure request builders ------------------------------------------------------------------


def build_summary_params(model_id: str) -> dict[str, object]:
    """Build the params for a fit-summary read (identified by fitted ``model_id``)."""
    params: dict[str, object] = {"model_id": model_id}
    return params


def build_roi_params(model_id: str) -> dict[str, object]:
    """Build the params for a per-channel ROI/contribution read (by fitted ``model_id``)."""
    params: dict[str, object] = {"model_id": model_id}
    return params


def build_optimize_params(model_id: str, total_budget: int) -> dict[str, object]:
    """Build the params for a budget-optimization run (fitted ``model_id`` + ``total_budget``).

    Pure builder (no SDK): the optimizer searches for the channel allocation maximizing modeled
    response subject to the supplied total spend.
    """
    params: dict[str, object] = {"model_id": model_id, "total_budget": total_budget}
    return params


def build_fit_params(dataset_ref: str, config: dict[str, object]) -> dict[str, object]:
    """Build the params for a model-fit job (input ``dataset_ref`` + Bayesian-MMM ``config``).

    Pure builder (no SDK): ``dataset_ref`` points the backend at the aggregate time-series input;
    ``config`` carries the MMM specification (e.g. media/control columns, priors, sampler settings)
    forwarded verbatim to Meridian.
    """
    params: dict[str, object] = {"dataset_ref": dataset_ref, "config": config}
    return params


# --- tool wrappers against the injected ReadFn ----------------------------------------------


def model_summary(*, model_id: str, read: ReadFn | None) -> dict[str, object]:
    """Tool: return fit-summary rows for an already-fitted MMM (by ``model_id``).

    Read-only (no account mutation). Reads back posterior summaries from a fitted model; cheap
    relative to fitting.
    """
    if read is None:
        return dict(_BACKEND_NOT_CONFIGURED)
    return _wrap(read(OP_SUMMARY, build_summary_params(model_id)))


def roi_by_channel(*, model_id: str, read: ReadFn | None) -> dict[str, object]:
    """Tool: return per-channel ROI / contribution rows for a fitted MMM (by ``model_id``).

    Read-only (no account mutation). Reads back the posterior ROI/contribution decomposition.
    """
    if read is None:
        return dict(_BACKEND_NOT_CONFIGURED)
    return _wrap(read(OP_ROI, build_roi_params(model_id)))


def optimize_budget(
    *, model_id: str, total_budget: int = DEFAULT_TOTAL_BUDGET, read: ReadFn | None
) -> dict[str, object]:
    """Tool: return the optimal per-channel allocation for ``total_budget`` under a fitted MMM.

    Read-only (no account mutation), but compute-bearing: the optimizer may run posterior
    simulations to search the allocation space. Does not place or change any spend — it only
    recommends.
    """
    if read is None:
        return dict(_BACKEND_NOT_CONFIGURED)
    return _wrap(read(OP_OPTIMIZE, build_optimize_params(model_id, total_budget)))


def fit_model(
    *, dataset_ref: str, config: dict[str, object], read: ReadFn | None
) -> dict[str, object]:
    """Tool: fit a Bayesian MMM on ``dataset_ref`` with ``config``; return a model/job handle row.

    Read-only with respect to marketing accounts (no mutation), but **compute-heavy**: this kicks
    off MCMC sampling under TensorFlow Probability and can take minutes-to-hours on real data. The
    backend returns a handle (e.g. a ``model_id`` / job ref) rather than the full posterior inline;
    callers then poll via ``model_summary`` / ``roi_by_channel``.
    """
    if read is None:
        return dict(_BACKEND_NOT_CONFIGURED)
    return _wrap(read(OP_FIT, build_fit_params(dataset_ref, config)))


_BACKEND_NOT_CONFIGURED: dict[str, object] = {
    "error": {"code": "BACKEND_NOT_CONFIGURED", "message": "meridian.api not wired"}
}
