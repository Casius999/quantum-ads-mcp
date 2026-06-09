"""Real Google Business Profile SDK glue: read + reviews + mutate factories.

Live boundary — smoke-gated, not unit-tested.

Isolated at the untyped third-party boundary (``googleapiclient.*`` / ``google.oauth2.*`` are in
the mypy ``ignore_missing_imports`` list, so ``build(...)`` yields ``Any`` and the dynamic resource
objects are threaded as ``Any`` here). Imports are local so importing this module stays cheap and
credential-free; OAuth credentials are derived from the shared Google creds dict. SDK-derived
values stay implicitly typed (``Any``).

Four discovery surfaces, all via ``googleapiclient.discovery.build``:
  - ``mybusinessaccountmanagement`` v1 — accounts.list
  - ``mybusinessbusinessinformation`` v1 — accounts.locations.list / locations.get / locations.patch
  - ``businessprofileperformance`` v1 — locations.fetchMultiDailyMetricsTimeSeries
  - ``mybusiness`` v4 — reviews.list / reviews.updateReply (legacy host, allowlist-gated)

The v1 family covers Account Management / Business Information / Business Profile Performance; the
legacy v4 host carries Reviews/Media/LocalPosts, which require separate Google allowlist approval
(weeks-to-months). Reviews are split onto their own ``ReadFn`` so they bind to the ``gbp.reviews``
backend independently of the v1 ``gbp.api`` backend.

Python package: ``google-api-python-client`` (plus ``google-auth``).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

ReadFn = Callable[[str, dict[str, object]], list[dict[str, object]]]
MutateFn = Callable[[str, list[dict[str, object]], bool], dict[str, object]]

# Single scope covers the whole Business Profile surface (read + manage + reply to reviews).
BUSINESS_MANAGE_SCOPE = "https://www.googleapis.com/auth/business.manage"

# Discovery documents for the v4 reviews host are not served from the default endpoint; the
# legacy ``mybusiness`` API is reached via an explicit discovery URL.
_MYBUSINESS_V4_DISCOVERY = "https://mybusiness.googleapis.com/$discovery/rest?version=v4"


def _oauth_credentials(creds: dict[str, object]) -> Any:
    from google.oauth2.credentials import Credentials

    return Credentials(
        token=None,
        refresh_token=str(creds["refresh_token"]),
        client_id=str(creds["client_id"]),
        client_secret=str(creds["client_secret"]),
        token_uri="https://oauth2.googleapis.com/token",
        scopes=[BUSINESS_MANAGE_SCOPE],
    )


def read_factory(creds: dict[str, object], version: str) -> ReadFn:
    """Build the GBP v1-family ReadFn (accounts / locations / location.get / performance)."""
    from googleapiclient.discovery import build

    credentials = _oauth_credentials(creds)
    account_mgmt = build(
        "mybusinessaccountmanagement", "v1", credentials=credentials, cache_discovery=False
    )
    business_info = build(
        "mybusinessbusinessinformation", "v1", credentials=credentials, cache_discovery=False
    )
    performance = build(
        "businessprofileperformance", "v1", credentials=credentials, cache_discovery=False
    )

    # Business Information locations.list requires an explicit read mask of the fields to return.
    location_read_mask = "name,title,storefrontAddress,phoneNumbers,websiteUri,metadata"

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        if operation == "accounts.list":
            response = account_mgmt.accounts().list().execute()
            return [dict(entry) for entry in response.get("accounts", [])]
        if operation == "locations.list":
            response = (
                business_info.accounts()
                .locations()
                .list(parent=str(params["account_id"]), readMask=location_read_mask)
                .execute()
            )
            return [dict(entry) for entry in response.get("locations", [])]
        if operation == "location.get":
            response = (
                business_info.locations()
                .get(name=str(params["location_name"]), readMask=location_read_mask)
                .execute()
            )
            return [dict(response)]
        if operation == "performance.fetchMultiDailyMetricsTimeSeries":
            start = _date_parts(str(params["start_date"]))
            end = _date_parts(str(params["end_date"]))
            request = performance.locations().fetchMultiDailyMetricsTimeSeries(
                location=str(params["location_name"]),
                dailyMetrics=_DAILY_METRICS,
                **{
                    "dailyRange_startDate_year": start[0],
                    "dailyRange_startDate_month": start[1],
                    "dailyRange_startDate_day": start[2],
                    "dailyRange_endDate_year": end[0],
                    "dailyRange_endDate_month": end[1],
                    "dailyRange_endDate_day": end[2],
                },
            )
            response = request.execute()
            return [dict(series) for series in response.get("multiDailyMetricTimeSeries", [])]
        raise ValueError(f"unsupported gbp read operation: {operation!r}")

    return read


def reviews_read_factory(creds: dict[str, object], version: str) -> ReadFn:
    """Build the legacy v4 reviews ReadFn (allowlist-gated ``mybusiness`` host)."""
    from googleapiclient.discovery import build

    credentials = _oauth_credentials(creds)
    mybusiness = build(
        "mybusiness",
        "v4",
        credentials=credentials,
        discoveryServiceUrl=_MYBUSINESS_V4_DISCOVERY,
        cache_discovery=False,
    )

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        if operation == "reviews.list":
            response = (
                mybusiness.accounts()
                .locations()
                .reviews()
                .list(parent=str(params["location_name"]))
                .execute()
            )
            return [dict(entry) for entry in response.get("reviews", [])]
        raise ValueError(f"unsupported gbp reviews operation: {operation!r}")

    return read


def mutate_factory(creds: dict[str, object], version: str) -> MutateFn:
    """Build the GBP MutateFn dispatching review replies (v4) and location updates (v1).

    Neither endpoint exposes a server-side validate-only flag, so the ``validate_only`` pass
    returns a synthetic preview of the exact op dicts that would be applied before the confirm
    step. Review replies go through the legacy v4 ``mybusiness`` host; location updates go through
    the Business Information v1 host with an update mask derived from the patched field keys.
    """
    from googleapiclient.discovery import build

    credentials = _oauth_credentials(creds)
    business_info = build(
        "mybusinessbusinessinformation", "v1", credentials=credentials, cache_discovery=False
    )
    mybusiness = build(
        "mybusiness",
        "v4",
        credentials=credentials,
        discoveryServiceUrl=_MYBUSINESS_V4_DISCOVERY,
        cache_discovery=False,
    )

    def _reply(op: dict[str, object]) -> dict[str, object]:
        body: dict[str, object] = {"comment": str(op["comment"])}
        request = (
            mybusiness.accounts()
            .locations()
            .reviews()
            .updateReply(name=str(op["review_name"]), body=body)
        )
        return dict(request.execute())

    def _update_location(op: dict[str, object]) -> dict[str, object]:
        fields = dict(op.get("fields", {}))
        update_mask = ",".join(sorted(fields.keys()))
        request = business_info.locations().patch(
            name=str(op["location_name"]), updateMask=update_mask, body=fields
        )
        return dict(request.execute())

    handlers: dict[str, Callable[[dict[str, object]], dict[str, object]]] = {
        "reply": _reply,
        "update": _update_location,
    }

    def mutate(
        customer_id: str, operations: list[dict[str, object]], validate_only: bool
    ) -> dict[str, object]:
        if validate_only:
            # No native validate_only on either endpoint; preview without applying.
            return {"validate_only": True, "operations": operations, "resource": customer_id}
        results: list[dict[str, object]] = []
        for op in operations:
            handler = handlers.get(str(op.get("action")))
            if handler is None:
                raise ValueError(f"unsupported gbp mutate action: {op.get('action')!r}")
            results.append(handler(op))
        return {"validate_only": False, "results": results}

    return mutate


# Daily metrics requested from fetchMultiDailyMetricsTimeSeries (calls/directions/clicks/views).
_DAILY_METRICS: list[str] = [
    "CALL_CLICKS",
    "BUSINESS_DIRECTION_REQUESTS",
    "WEBSITE_CLICKS",
    "BUSINESS_IMPRESSIONS_DESKTOP_MAPS",
    "BUSINESS_IMPRESSIONS_DESKTOP_SEARCH",
    "BUSINESS_IMPRESSIONS_MOBILE_MAPS",
    "BUSINESS_IMPRESSIONS_MOBILE_SEARCH",
]


def _date_parts(iso_date: str) -> tuple[int, int, int]:
    """Split an ISO ``YYYY-MM-DD`` date into (year, month, day) ints for the structured query."""
    year, month, day = iso_date.split("-")
    return int(year), int(month), int(day)
