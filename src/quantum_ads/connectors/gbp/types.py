"""Shared type aliases for the Google Business Profile connector.

The read plane talks to a generic ``ReadFn`` backend: the first argument names the operation and
the second carries the params. This mirrors the Search Console / Merchant ReadFn boundary —
resource/operation-oriented rather than query-oriented, because the GBP surface is a set of REST
endpoints across several discovery documents (accounts / locations / performance / reviews) rather
than a single query language.

There are two read backends because reviews live on a different host:
  - ``"gbp.api"``      — the v1 API family (accounts, locations, performance time series)
  - ``"gbp.reviews"``  — the legacy v4 ``mybusiness`` host (Reviews/Media/LocalPosts), which is
    allowlist-gated by Google and degrades to ``BACKEND_NOT_CONFIGURED`` when not wired.
"""

from __future__ import annotations

from collections.abc import Callable

# (operation, params) -> rows. operation names the call; params carry the args.
ReadFn = Callable[[str, dict[str, object]], list[dict[str, object]]]
