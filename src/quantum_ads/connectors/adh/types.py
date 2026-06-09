"""Shared type aliases for the Ads Data Hub (ADH) connector.

The read plane talks to a generic ``ReadFn`` backend (keyed ``"adh.api"``): the first argument
names the operation and the second carries the params. ADH (the Ads Data Hub API, ``adsdatahub``
v1) exposes account/query listing plus a query-run lifecycle: ``customers.list`` and
``queries.list`` enumerate accounts and stored analysis queries, ``query.start`` launches a stored
analysis query over a date range (returning a long-running operation / job reference), and
``jobs.get`` polls that operation for status + the result table reference. This mirrors the
operation/params ``ReadFn`` boundary used by Search Console / SA360 rather than threading a live
query client — the backend owns the SDK call.

ADH enforces privacy checks (aggregation thresholds + difference checks) server-side: every
result is privacy-filtered and never row-level. This connector submits and polls; it does not — and
cannot — bypass ADH's privacy layer.
"""

from __future__ import annotations

from collections.abc import Callable

# (operation, params) -> rows. operation names the call; params carry the args.
ReadFn = Callable[[str, dict[str, object]], list[dict[str, object]]]
