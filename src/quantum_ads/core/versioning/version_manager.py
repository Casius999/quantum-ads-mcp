"""Pinned Google Ads API version + sunset guard + injectable client factory.

The client factory is injected so tests never need the real SDK or network. Production
wires it to ``GoogleAdsClient.load_from_dict(creds, version=version)``.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable

# Verified / approximate sunset dates (June 2026). Refine from the official sunset-dates page.
# Google Ads API releases monthly in 2026; each major is supported ~12 months.
SUNSET_SCHEDULE: dict[str, dt.date] = {
    "v20": dt.date(2026, 6, 10),  # verified
    "v21": dt.date(2026, 9, 1),  # approximate
    "v22": dt.date(2027, 2, 1),  # approximate
    "v23": dt.date(2027, 4, 1),  # approximate
    "v24": dt.date(2027, 5, 1),  # approximate (~12 months from GA 2026-04-22)
}

ClientFactory = Callable[[dict[str, object], str], object]


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
