"""Live boundary — smoke-gated, not unit-tested.

Real Meridian SDK glue: a lazy factory building the MMM ReadFn dispatching the four operations
(summary / roi / optimize / fit). Isolated at the untyped third-party boundary (``meridian.*`` is
mypy-ignored; this module is coverage-omitted via the live gate). Imports are local so importing
this module stays cheap and credential-free. SDK-derived values stay implicitly typed (``Any``) —
they are never annotated, mirroring the other connector SDK boundaries.

Meridian is Google's open-source **Bayesian** Marketing Mix Modeling library: it runs MCMC sampling
under TensorFlow Probability to estimate channel contribution, ROI, and response curves from
aggregate (cookieless) time-series data. Fitting is heavy compute (minutes-to-hours); this live
boundary just bridges the MCP tool calls to the library — ``fit`` builds + samples a model and
registers it under a ``model_id``, while the read-back operations recover summaries/ROI/optimal
allocation from a fitted model held in the backend's model registry.

Python package: ``google-meridian`` (provides the ``meridian`` namespace).
"""

from __future__ import annotations

from collections.abc import Callable

ReadFn = Callable[[str, dict[str, object]], list[dict[str, object]]]


def mmm_read_factory(creds: dict[str, object], version: str) -> ReadFn:
    """Build the Meridian ReadFn dispatching summary / roi / optimize / fit operations.

    Holds an in-process registry mapping ``model_id`` -> fitted Meridian model so the read-back
    operations can recover posterior summaries from a model produced by a prior ``fit`` call.
    """
    from meridian.analysis import analyzer, optimizer, summarizer
    from meridian.data import load
    from meridian.model import model, spec

    models: dict[str, object] = {}

    def _fit(params: dict[str, object]) -> list[dict[str, object]]:
        config = dict(params["config"])  # type: ignore[arg-type]
        loader = load.DataFrameDataLoader(dataset_ref=str(params["dataset_ref"]), **config)
        data = loader.load()
        mmm = model.Meridian(input_data=data, model_spec=spec.ModelSpec())
        mmm.sample_posterior()
        model_id = str(config.get("model_id") or f"meridian-{len(models) + 1}")
        models[model_id] = mmm
        return [{"model_id": model_id, "status": "fitted"}]

    def _summary(params: dict[str, object]) -> list[dict[str, object]]:
        mmm = models[str(params["model_id"])]
        rows = summarizer.Summarizer(mmm).summary_table()
        return [dict(row) for row in rows]

    def _roi(params: dict[str, object]) -> list[dict[str, object]]:
        mmm = models[str(params["model_id"])]
        roi = analyzer.Analyzer(mmm).roi()
        return [dict(row) for row in roi]

    def _optimize(params: dict[str, object]) -> list[dict[str, object]]:
        mmm = models[str(params["model_id"])]
        result = optimizer.BudgetOptimizer(mmm).optimize(budget=int(params["total_budget"]))
        return [dict(row) for row in result.optimized_allocation]

    handlers: dict[str, Callable[[dict[str, object]], list[dict[str, object]]]] = {
        "summary": _summary,
        "roi": _roi,
        "optimize": _optimize,
        "fit": _fit,
    }

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        handler = handlers.get(operation)
        if handler is None:
            raise ValueError(f"unsupported meridian operation: {operation!r}")
        return handler(params)

    return read
