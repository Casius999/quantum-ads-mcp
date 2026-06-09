"""Shared type aliases for the Search Ads 360 connector.

The read plane talks to a generic ``ReadFn`` backend (keyed ``"sa360.api"``): the first argument
names the operation and the second carries the params. SA360 exposes a GAQL-like query language
(``SELECT ... FROM ... WHERE``) through ``searchAds360:search`` plus a ``customers:listAccessible``
endpoint, so the ``search`` operation carries ``{"customer_id", "query"}`` while the report
shortcuts pre-build the query string and route through the same ``search`` operation. This mirrors
the operation/params ``ReadFn`` boundary used by Search Console / Merchant rather than threading a
live query client — the backend owns the SDK call.
"""

from __future__ import annotations

from collections.abc import Callable

# (operation, params) -> rows. operation names the call; params carry the query/args.
ReadFn = Callable[[str, dict[str, object]], list[dict[str, object]]]
