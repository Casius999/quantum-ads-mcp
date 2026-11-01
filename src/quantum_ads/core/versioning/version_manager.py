"""Pinned Google Ads API version + sunset guard + injectable client factory.

The client factory is injected so tests never need the real SDK or network. Production
wires it to ``GoogleAdsClient.load_from_dict(creds, version=version)``.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable

# Official sunset months from developers.google.com/google-ads/api/docs/sunset-dates (read
# 2026-11-01). Google publishes month granularity only, so each date is the FIRST day of the
# sunset month: the guard warns early rather than late. Minor versions share their major's month.
SUNSET_SCHEDULE: dict[str, dt.date] = {
    "v23": dt.date(2027, 2, 1),  # released 2026-01-28
    "v24": dt.date(2027, 5, 1),  # released 2026-04-22
    "v25": dt.date(2027, 8, 1),  # released 2026-07-22
    "v26": dt.date(2027, 11, 1),  # released 2026-10-14 (latest)
}

ClientFactory = Callable[[dict[str, object], str], object]

# Single source of truth for the pinned Google Ads API version (overridable per deployment via
# GOOGLE_ADS_API_VERSION). Bump here; tests/integration_mock/test_gaql_field_conformance.py then
# proves every field the tools query still exists in it.
DEFAULT_API_VERSION = "v26"


class VersionManager:
    """Owns the pinned API version, builds clients, and reports time-to-sunset."""

    def __init__(self, version: str, client_factory: ClientFactory):
        self.version = version
        self._factory = client_factory

    def build_client(self, creds: dict[str, object]) -> object:
        return self._factory(creds, self.version)

    def days_until_sunset(self, today: dt.date | None = None) -> int | None:
        sunset = SUNSET_SCHEDULE.get(self.version)
        if sunset is None:
            return None
        return (sunset - (today or dt.date.today())).days
