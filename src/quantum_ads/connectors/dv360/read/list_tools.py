"""DV360 read tools: pure param builders + a backend-invoking, enum-tolerant runner.

Each resource is listed by naming it in ``operation`` and carrying the parent id in ``params``
(the ``ReadFn`` contract). Builders are pure and unit-tested directly. ``run_read`` invokes the
injected backend and projects every row through ``catalogs.map_rows`` so unknown ``entityStatus``
/ ``lineItemType`` enum values (e.g. Demand Gen, launched 2026-06-10) degrade to ``"UNKNOWN"``
instead of breaking, then wraps as ``{"rows", "row_count"}``.
"""

from __future__ import annotations

from ..catalogs import map_rows
from ..types import ReadFn

# Operation (resource) names passed as the first ReadFn argument.
OP_ADVERTISERS_LIST = "advertisers.list"
OP_CAMPAIGNS_LIST = "campaigns.list"
OP_INSERTION_ORDERS_LIST = "insertionOrders.list"
OP_LINE_ITEMS_LIST = "lineItems.list"


def build_advertisers_params(partner_id: str) -> dict[str, object]:
    """Pure: wrap a partner id as backend params for ``advertisers.list``."""
    params: dict[str, object] = {"partner_id": partner_id}
    return params


def build_advertiser_child_params(advertiser_id: str) -> dict[str, object]:
    """Pure: wrap an advertiser id as backend params (campaigns / IOs / line items list)."""
    params: dict[str, object] = {"advertiser_id": advertiser_id}
    return params


def run_read(*, operation: str, params: dict[str, object], read: ReadFn) -> dict[str, object]:
    """Invoke the DV360 read backend for ``operation`` and wrap enum-tolerant rows."""
    rows = map_rows(read(operation, params))
    return {"rows": rows, "row_count": len(rows)}


def list_advertisers(*, partner_id: str, read: ReadFn) -> dict[str, object]:
    """Tool: list advertisers under a partner."""
    return run_read(
        operation=OP_ADVERTISERS_LIST,
        params=build_advertisers_params(partner_id),
        read=read,
    )


def list_campaigns(*, advertiser_id: str, read: ReadFn) -> dict[str, object]:
    """Tool: list campaigns under an advertiser."""
    return run_read(
        operation=OP_CAMPAIGNS_LIST,
        params=build_advertiser_child_params(advertiser_id),
        read=read,
    )


def list_insertion_orders(*, advertiser_id: str, read: ReadFn) -> dict[str, object]:
    """Tool: list insertion orders under an advertiser."""
    return run_read(
        operation=OP_INSERTION_ORDERS_LIST,
        params=build_advertiser_child_params(advertiser_id),
        read=read,
    )


def list_line_items(*, advertiser_id: str, read: ReadFn) -> dict[str, object]:
    """Tool: list line items under an advertiser."""
    return run_read(
        operation=OP_LINE_ITEMS_LIST,
        params=build_advertiser_child_params(advertiser_id),
        read=read,
    )
