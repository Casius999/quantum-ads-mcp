"""Pure operation builders for Google Business Profile mutations.

Each builder returns a list with a single entity-tagged op dict. The ``entity``/``action`` keys
let the SDK mutate boundary dispatch to the right GBP call (review reply on the legacy v4 host /
location patch on the Business Information v1 host); the remaining keys carry the resource name and
payload. These are pure and unit-tested directly (no SDK needed).
"""

from __future__ import annotations


def build_review_reply_ops(review_name: str, comment: str) -> list[dict[str, object]]:
    """Build the op to reply to (upsert the owner reply on) a review by resource name."""
    op: dict[str, object] = {
        "entity": "review",
        "action": "reply",
        "review_name": review_name,
        "comment": comment,
    }
    return [op]


def build_location_update_ops(
    location_name: str, fields: dict[str, object]
) -> list[dict[str, object]]:
    """Build the op to patch a location's fields by resource name.

    ``fields`` is the partial set of location attributes to update; the SDK boundary derives the
    update mask from its keys (mirroring the DV360 line-item patch pattern).
    """
    op: dict[str, object] = {
        "entity": "location",
        "action": "update",
        "location_name": location_name,
        "fields": dict(fields),
    }
    return [op]
