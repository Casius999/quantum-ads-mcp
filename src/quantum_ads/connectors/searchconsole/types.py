"""Shared type aliases for the Search Console connector.

The read plane talks to a generic ``ReadFn`` backend (keyed ``"searchconsole.api"``): the first
argument names the operation and the second carries the params. This mirrors the Merchant API
``ReadFn`` boundary — resource/operation-oriented rather than query-oriented, because the Search
Console API is a small set of REST endpoints (searchAnalytics.query, sites.list, sitemaps.list,
urlInspection.index.inspect) rather than a single query language.
"""

from __future__ import annotations

from collections.abc import Callable

# (operation, params) -> rows. operation names the call; params carry the args.
ReadFn = Callable[[str, dict[str, object]], list[dict[str, object]]]
