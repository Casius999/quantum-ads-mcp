"""Shared type aliases for the YouTube connector.

Two read backends, both speaking the same resource-oriented ``ReadFn`` contract (the first
argument names the operation/resource, the second carries ids/params):
  - ``youtube.data``      -> Data API v3        (channels / videos / batch stats / playlistItems)
  - ``youtube.analytics`` -> YouTube Analytics+Reporting (analytics query + report-job ensure)

The write backend is a ``MutateFn`` (re-exported from the safety spine) keyed ``youtube.mutate``;
its ``account_id`` positional is the channel id.
"""

from __future__ import annotations

from collections.abc import Callable

# (operation, params) -> rows. operation names the resource; params carry the ids.
ReadFn = Callable[[str, dict[str, object]], list[dict[str, object]]]
