"""Meridian connector: cookieless cross-channel measurement via Marketing Mix Modeling (MMM).

Public entry point: :func:`register_meridian` mounts the Meridian tools onto the FastMCP app.

This is the **incrementality / cross-channel measurement** surface. Meridian is Google's
open-source MMM library — a *Bayesian* model (TensorFlow Probability under the hood) that estimates
the causal contribution and ROI of each marketing channel from aggregate time-series data, with no
user-level tracking or cookies. It complements the per-platform measurement connectors by answering
"how much did each channel actually drive, and where should the next dollar go?".

Four tools, all flagged ``read_only=True`` — they perform **no account mutation** and are therefore
NOT guarded by the ``WriteExecutor`` (no validate-only preview / two-step confirm). NOTE, however,
that ``meridian.fit`` (and, depending on the backend, the read-back tools) is **compute-heavy**:
fitting a Bayesian MMM runs MCMC sampling and can take minutes-to-hours on real data. "Read-only"
here means "no marketing-account side effects", not "cheap". Every tool docstring says so.

Single backend, keyed ``"meridian.api"`` (a ``ReadFn``): ``(operation, params) -> rows`` where
operation is one of ``"summary"`` / ``"roi"`` / ``"optimize"`` / ``"fit"``. When it is not wired the
tools degrade gracefully, returning a structured ``BACKEND_NOT_CONFIGURED`` error rather than raising.
"""

from .connector import register_meridian

__all__ = ["register_meridian"]
