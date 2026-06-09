"""Shared type alias for the BigQuery connector read plane.

The read plane talks to a generic ``ReadFn`` backend (keyed ``"bigquery.api"``): the first
argument names the operation and the second carries the project id / sql / params. This mirrors
the Merchant API resource-oriented boundary rather than the Google Ads query-oriented one, because
the BigQuery surface here is a small set of named operations (list datasets/tables, dry-run a
query, run a query) rather than a single query language.
"""

from __future__ import annotations

from collections.abc import Callable

# (operation, params) -> rows. operation names the API call; params carry project_id / sql / etc.
ReadFn = Callable[[str, dict[str, object]], list[dict[str, object]]]
