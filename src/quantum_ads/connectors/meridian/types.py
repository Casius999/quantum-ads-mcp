"""Shared type alias for the Meridian (Marketing Mix Modeling) connector.

The connector talks to a single generic ``ReadFn`` backend (keyed ``"meridian.api"``): the first
argument names the operation (``"summary"`` / ``"roi"`` / ``"optimize"`` / ``"fit"``) and the second
carries the request params (``model_id`` / ``dataset_ref`` / ``config`` / ``total_budget``). This
mirrors the BigQuery / Vertex ``ReadFn`` boundary — a small set of named operations rather than a
single query language — except here the returned rows are MMM outputs (fit summary, per-channel
ROI/contribution, optimal budget allocation) or, for ``fit``, a single-row model/job handle.
"""

from __future__ import annotations

from collections.abc import Callable

# (operation, params) -> rows. operation names the MMM call; params carry model_id / config / etc.
ReadFn = Callable[[str, dict[str, object]], list[dict[str, object]]]
