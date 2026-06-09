"""Shared type aliases for the Merchant API connector.

The read plane talks to a generic ``ReadFn`` backend (keyed ``"merchant.api"``): the first
argument names the resource/operation and the second carries the ids/params. This mirrors the
Google Ads ``StreamFn`` boundary but is resource-oriented rather than query-oriented, because
the Merchant API is a set of REST resources rather than a single query language.
"""

from __future__ import annotations

from collections.abc import Callable

# (operation, params) -> rows. operation names the resource; params carry the ids.
ReadFn = Callable[[str, dict[str, object]], list[dict[str, object]]]
