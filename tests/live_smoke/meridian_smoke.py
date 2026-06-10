"""Standalone Meridian library-surface check — run in the isolated .venv-meridian.

Meridian pulls a heavy TensorFlow/tfp stack that conflicts with the other connectors, so it is NOT a
pyproject extra and NOT part of the main `pytest -m live` suite. This script validates that the
meridian connector's import paths + class names match the installed `google-meridian` (the
connector's sdk.py imports analyzer/optimizer/summarizer + data.load + model.{Meridian,ModelSpec}
and calls Analyzer/BudgetOptimizer/Summarizer/DataFrameInputDataLoader). A full MCMC posterior fit
is too heavy for a smoke; proving the library boundary the connector depends on is real is the goal.

Run:  .venv-meridian\\Scripts\\python tests\\live_smoke\\meridian_smoke.py
"""

from __future__ import annotations


def main() -> None:
    from meridian.analysis import analyzer, optimizer, summarizer
    from meridian.data import load
    from meridian.model import model, spec

    built = spec.ModelSpec()
    assert built is not None, "meridian ModelSpec() did not construct"

    surface = [
        (model, "Meridian"),
        (analyzer, "Analyzer"),
        (optimizer, "BudgetOptimizer"),
        (summarizer, "Summarizer"),
        (load, "DataFrameDataLoader"),
    ]
    missing = [f"{m.__name__}.{n}" for m, n in surface if not hasattr(m, n)]
    assert not missing, f"meridian surface absent (connector would break): {missing}"

    print(
        "OK - meridian library surface matches the connector (ModelSpec built; 5 classes present)"
    )


if __name__ == "__main__":
    main()
