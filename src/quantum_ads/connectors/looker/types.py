"""Shared type alias for the Looker connector read plane.

The read plane talks to a generic ``ReadFn`` backend (keyed ``"looker.api"``): the first argument
names the operation and the second carries the look/query ids and parameters. This mirrors the
resource-oriented boundary of the BigQuery connector rather than a single query language, because
the Looker surface here is a small set of named operations (list dashboards/looks, run a look, run
an inline query).
"""

from __future__ import annotations

from collections.abc import Callable

# (operation, params) -> rows. operation names the API call; params carry look_id / query body / etc.
ReadFn = Callable[[str, dict[str, object]], list[dict[str, object]]]
