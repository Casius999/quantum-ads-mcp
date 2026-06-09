"""Shared type aliases for the Data Manager API connector.

The read plane talks to a generic ``ReadFn`` backend (keyed ``"datamanager.read"``): the first
argument names the resource/operation and the second carries the ids/params. This mirrors the
Merchant API read boundary — resource-oriented rather than query-oriented, because the Data
Manager API is a set of REST resources rather than a single query language.
"""

from __future__ import annotations

from collections.abc import Callable

# (operation, params) -> rows. operation names the resource; params carry the ids.
ReadFn = Callable[[str, dict[str, object]], list[dict[str, object]]]
