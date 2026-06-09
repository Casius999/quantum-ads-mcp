"""Pure operation builders for Merchant API product mutations.

Each builder returns a list with a single entity-tagged op dict. The ``entity``/``action`` keys
let the SDK mutate boundary dispatch to the right Merchant API call; the remaining keys carry the
resource ids and payload. These are pure and unit-tested directly (no SDK needed).
"""

from __future__ import annotations


def build_insert_product_ops(product_input: dict[str, object]) -> list[dict[str, object]]:
    """Build the op for inserting a product (productInput payload)."""
    op: dict[str, object] = {
        "entity": "product",
        "action": "insert",
        "product_input": dict(product_input),
    }
    return [op]


def build_update_product_ops(
    product_name: str, fields: dict[str, object]
) -> list[dict[str, object]]:
    """Build the op for updating a product by resource name with a partial field set."""
    op: dict[str, object] = {
        "entity": "product",
        "action": "update",
        "product_name": product_name,
        "fields": dict(fields),
    }
    return [op]


def build_delete_product_ops(product_name: str) -> list[dict[str, object]]:
    """Build the op for deleting a product by resource name."""
    op: dict[str, object] = {
        "entity": "product",
        "action": "delete",
        "product_name": product_name,
    }
    return [op]
