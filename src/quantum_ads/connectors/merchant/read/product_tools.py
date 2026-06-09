"""Raw Merchant API read execution + result wrapping for the read connector.

Each tool calls the injected ``ReadFn`` with an operation name (the resource being read) and a
params dict carrying the ids. Rows come back as plain dicts and are wrapped in a consistent
``{"rows": ..., "row_count": ...}`` envelope, matching the Google Ads read connector.
"""

from __future__ import annotations

from ..types import ReadFn

# Operation (resource) names passed as the first ReadFn argument.
OP_PRODUCTS_LIST = "products.list"
OP_PRODUCT_GET = "products.get"
OP_PRODUCT_STATUSES_LIST = "productStatuses.list"
OP_ACCOUNTS_GET = "accounts.get"


def _wrap(rows: list[dict[str, object]]) -> dict[str, object]:
    """Wrap rows in the shared read envelope."""
    return {"rows": rows, "row_count": len(rows)}


def list_products(*, merchant_id: str, read: ReadFn) -> dict[str, object]:
    """Tool: list products under a Merchant Center account."""
    params: dict[str, object] = {"merchant_id": merchant_id}
    return _wrap(read(OP_PRODUCTS_LIST, params))


def get_product(*, product_name: str, read: ReadFn) -> dict[str, object]:
    """Tool: get a single product by its resource name (``accounts/{a}/products/{p}``)."""
    params: dict[str, object] = {"product_name": product_name}
    return _wrap(read(OP_PRODUCT_GET, params))


def list_product_statuses(*, merchant_id: str, read: ReadFn) -> dict[str, object]:
    """Tool: list item-level status/issues for products under a Merchant Center account."""
    params: dict[str, object] = {"merchant_id": merchant_id}
    return _wrap(read(OP_PRODUCT_STATUSES_LIST, params))


def get_account(*, merchant_id: str, read: ReadFn) -> dict[str, object]:
    """Tool: get a Merchant Center account."""
    params: dict[str, object] = {"merchant_id": merchant_id}
    return _wrap(read(OP_ACCOUNTS_GET, params))
