"""Pure operation builder for Search Ads 360 conversion uploads (unit-tested directly).

Returns a list with a single ``action``-tagged op dict; the ``MutateFn`` backend dispatches on
``action`` and the concrete Search Ads 360 ``conversions:ingest`` translation lives in
``sa360.sdk`` (live boundary). ``account_id`` (the SA360 ``customer_id``) is threaded by the
WriteExecutor, so the op carries only the conversion payloads. The builder snapshots the input
list so later caller mutations cannot leak into the queued op.

These are pure and unit-tested directly (no SDK needed).
"""

from __future__ import annotations


def build_upload_conversions_ops(
    conversions: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Build the op to upload SA360 conversions.

    ``conversions`` carry the conversion payloads (e.g. ``conversionId`` / ``conversionQuantity`` /
    ``floodlightActivityId`` / ``conversionTimestamp``). This builder only shapes the dict; it does
    not validate the payload fields.
    """
    op: dict[str, object] = {
        "action": "upload_conversions",
        "conversions": [dict(c) for c in conversions],
    }
    return [op]
