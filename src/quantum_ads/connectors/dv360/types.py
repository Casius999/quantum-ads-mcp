"""Shared type aliases for the Display & Video 360 connector.

The read plane talks to a generic ``ReadFn`` backend (keyed ``"dv360.api"``): the first
argument names the resource/operation (``advertisers.list`` / ``campaigns.list`` /
``insertionOrders.list`` / ``lineItems.list``) and the second carries the parent ids/params.
This mirrors the Merchant ``ReadFn`` boundary — resource-oriented rather than query-oriented,
because the Display Video API is a set of REST resources rather than a single query language.

The write plane talks to a ``MutateFn`` (keyed ``"dv360.mutate"``) where ``account_id`` carries
the DV360 advertiser id (the parent every line-item mutation hangs off).
"""

from __future__ import annotations

from collections.abc import Callable

# (operation, params) -> rows. operation names the resource; params carry the parent ids.
ReadFn = Callable[[str, dict[str, object]], list[dict[str, object]]]
