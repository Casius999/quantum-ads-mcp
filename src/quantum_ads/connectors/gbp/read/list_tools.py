"""Google Business Profile read tools (v1 family + legacy v4 reviews).

Pure request builders (``build_*``) construct the params dict handed to the injected backend
``ReadFn``; the thin tool wrappers (``list_accounts`` / ``list_locations`` / ``get_location`` /
``fetch_performance`` / ``list_reviews``) do the result wrapping. The backend ReadFn signature is
``(operation, params) -> rows`` where operation is one of the ``OP_*`` constants below.

Two backends are involved (the connector picks which ``read`` to pass):
  - the v1 family (``gbp.api``): accounts.list / locations.list / location.get / performance fetch
  - the legacy v4 reviews host (``gbp.reviews``): reviews.list — allowlist-gated by Google

The ``{"rows", "row_count"}`` envelope matches the Google Ads / Merchant / Search Console read
connectors.
"""

from __future__ import annotations

from ..types import ReadFn

# Operation names passed as the first ReadFn argument.
# v1 family (Account Management / Business Information / Business Profile Performance).
OP_ACCOUNTS_LIST = "accounts.list"
OP_LOCATIONS_LIST = "locations.list"
OP_LOCATION_GET = "location.get"
OP_PERFORMANCE_FETCH = "performance.fetchMultiDailyMetricsTimeSeries"
# Legacy v4 ``mybusiness`` host (allowlist-gated).
OP_REVIEWS_LIST = "reviews.list"


def build_locations_request(*, account_id: str) -> dict[str, object]:
    """Build the locations.list request (the parent account whose locations to enumerate)."""
    request: dict[str, object] = {"account_id": account_id}
    return request


def build_location_get_request(*, location_name: str) -> dict[str, object]:
    """Build the location.get request (the ``locations/{id}`` resource name to fetch)."""
    request: dict[str, object] = {"location_name": location_name}
    return request


def build_performance_request(
    *, location_name: str, start_date: str, end_date: str
) -> dict[str, object]:
    """Build the fetchMultiDailyMetricsTimeSeries request (location + inclusive date range).

    The daily metrics time series covers calls, direction requests, website clicks, and the
    various search/maps impression breakdowns for the location over the requested window.
    """
    request: dict[str, object] = {
        "location_name": location_name,
        "start_date": start_date,
        "end_date": end_date,
    }
    return request


def build_reviews_request(*, location_name: str) -> dict[str, object]:
    """Build the reviews.list request (the location whose reviews to enumerate).

    Reviews live on the legacy v4 ``mybusiness`` host and require separate Google allowlist
    approval; the connector routes this through the dedicated ``gbp.reviews`` backend.
    """
    request: dict[str, object] = {"location_name": location_name}
    return request


def _wrap(rows: list[dict[str, object]]) -> dict[str, object]:
    """Wrap rows in the shared read envelope."""
    return {"rows": rows, "row_count": len(rows)}


def list_accounts(*, read: ReadFn) -> dict[str, object]:
    """Tool: list the GBP accounts the authenticated user can access (Account Management API)."""
    params: dict[str, object] = {}
    return _wrap(read(OP_ACCOUNTS_LIST, params))


def list_locations(*, account_id: str, read: ReadFn) -> dict[str, object]:
    """Tool: list the locations under a GBP account (Business Information API)."""
    request = build_locations_request(account_id=account_id)
    return _wrap(read(OP_LOCATIONS_LIST, request))


def get_location(*, location_name: str, read: ReadFn) -> dict[str, object]:
    """Tool: fetch a single location's details by resource name (Business Information API)."""
    request = build_location_get_request(location_name=location_name)
    return _wrap(read(OP_LOCATION_GET, request))


def fetch_performance(
    *, location_name: str, start_date: str, end_date: str, read: ReadFn
) -> dict[str, object]:
    """Tool: fetch daily performance metrics for a location (Business Profile Performance API)."""
    request = build_performance_request(
        location_name=location_name, start_date=start_date, end_date=end_date
    )
    return _wrap(read(OP_PERFORMANCE_FETCH, request))


def list_reviews(*, location_name: str, read: ReadFn) -> dict[str, object]:
    """Tool: list reviews for a location (legacy v4 host — allowlist-gated)."""
    request = build_reviews_request(location_name=location_name)
    return _wrap(read(OP_REVIEWS_LIST, request))
