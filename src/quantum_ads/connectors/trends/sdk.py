"""Real Google Trends SDK glue: a single read (ReadFn) factory over ``pytrends``.

Live boundary — smoke-gated, not unit-tested. Isolated at the untyped third-party boundary
(``pytrends.*`` is mypy-ignored; this module is coverage-omitted via the live gate). Imports are
local so importing this module stays cheap and dependency-free.

NO OFFICIAL STABLE API. As of June 2026 Google Trends has **no official, generally available
API** — the Google-provided Trends API is **alpha / limited-access** (closed allow-list, not
suitable for production). This connector therefore uses **pytrends**, an **unofficial** library
that scrapes the public Trends web endpoints. Consequences callers must accept:
  - **Unofficial & unsupported**: pytrends can break without notice if Google changes the
    internal endpoints; there is no SLA and no Google support.
  - **Rate-limited**: the endpoints aggressively throttle (HTTP 429). Back off, cache results,
    and keep request volume low; do not hammer it.
  - **Relative, not absolute**: interest values are a 0-100 relative index, not query counts.
Migrate to the official Trends API once it reaches a stable GA tier.

Python package: ``pytrends`` (unofficial). Because it is untyped, ``pytrends.*`` must be added to
the mypy ``ignore_missing_imports`` / ``[[tool.mypy.overrides]]`` list (see the connector report).
SDK-derived values (the ``TrendReq`` session and the pandas frames it returns) stay implicitly
typed (``Any``).

Operation dispatch (first ReadFn argument):
  - ``interest_over_time``  -> ``TrendReq.interest_over_time`` (date-indexed relative interest)
  - ``related_queries``     -> ``TrendReq.related_queries`` (top + rising query tables)
  - ``trending_now``        -> ``TrendReq.trending_searches`` (daily trending, per country)
  - ``interest_by_region``  -> ``TrendReq.interest_by_region`` (geo breakdown for a keyword)
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

ReadFn = Callable[[str, dict[str, object]], list[dict[str, object]]]

# pytrends country codes are full lowercase names (e.g. "united_states"), not ISO-2 geo codes.
# Map the ISO-2 geo codes the tools speak to the trending_searches country-name space.
_TRENDING_COUNTRY: dict[str, str] = {
    "US": "united_states",
    "GB": "united_kingdom",
    "FR": "france",
    "DE": "germany",
    "ES": "spain",
    "IT": "italy",
    "CA": "canada",
    "AU": "australia",
    "JP": "japan",
    "IN": "india",
    "BR": "brazil",
}
_DEFAULT_TRENDING_COUNTRY = "united_states"


def read_factory(creds: dict[str, object], version: str) -> ReadFn:
    """Build the Google Trends ReadFn dispatching the four read operations over pytrends.

    ``creds`` / ``version`` are accepted for signature parity with the other connector factories;
    pytrends needs no Google credentials (it scrapes the public Trends endpoints). A single
    ``TrendReq`` session is reused across calls within the returned closure.
    """
    from pytrends.request import TrendReq

    session: Any = TrendReq(hl="en-US", tz=0)

    def _frame_rows(frame: Any) -> list[dict[str, object]]:
        """Normalize a pandas DataFrame (date/region index) into list-of-dict rows."""
        if frame is None or frame.empty:
            return []
        reset = frame.reset_index()
        return [dict(record) for record in reset.to_dict(orient="records")]

    def _interest_over_time(params: dict[str, object]) -> list[dict[str, object]]:
        keywords = [str(k) for k in params["keywords"]]  # type: ignore[union-attr]
        session.build_payload(keywords, timeframe=str(params["timeframe"]), geo=str(params["geo"]))
        return _frame_rows(session.interest_over_time())

    def _related_queries(params: dict[str, object]) -> list[dict[str, object]]:
        keyword = str(params["keyword"])
        session.build_payload([keyword], geo=str(params["geo"]))
        related = session.related_queries().get(keyword) or {}
        rows: list[dict[str, object]] = []
        for bucket in ("top", "rising"):
            frame = related.get(bucket)
            for record in _frame_rows(frame):
                rows.append({"bucket": bucket, **record})
        return rows

    def _trending_now(params: dict[str, object]) -> list[dict[str, object]]:
        geo = str(params["geo"]).upper()
        country = _TRENDING_COUNTRY.get(geo, _DEFAULT_TRENDING_COUNTRY)
        frame = session.trending_searches(pn=country)
        return [{"rank": i, "query": str(v)} for i, v in enumerate(frame[0].tolist())]

    def _interest_by_region(params: dict[str, object]) -> list[dict[str, object]]:
        keyword = str(params["keyword"])
        session.build_payload([keyword])
        frame = session.interest_by_region(resolution=str(params["resolution"]), inc_low_vol=True)
        return _frame_rows(frame)

    handlers: dict[str, Callable[[dict[str, object]], list[dict[str, object]]]] = {
        "interest_over_time": _interest_over_time,
        "related_queries": _related_queries,
        "trending_now": _trending_now,
        "interest_by_region": _interest_by_region,
    }

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        handler = handlers.get(operation)
        if handler is None:
            raise ValueError(f"unsupported trends read operation: {operation!r}")
        return handler(params)

    return read
