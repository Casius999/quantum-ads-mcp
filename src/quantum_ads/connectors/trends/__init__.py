"""Google Trends connector: demand / seasonality research for the ads agency.

Public entry point: :func:`register_trends` mounts the read-only tool plane. Trends has **no
writes** — it is a pure research surface (interest over time, related queries, trending now,
interest by region) that complements the paid Google Ads connectors with demand signal.

The read plane talks to a generic ``ReadFn`` backend keyed ``"trends.api"`` (operation-oriented:
the first argument names the call, the second carries the params). See :mod:`.sdk` for the live
boundary notes — Trends has no official stable API in June 2026, so the unofficial ``pytrends``
library is used as the live backend.
"""

from __future__ import annotations

from .connector import register_trends

__all__ = ["register_trends"]
