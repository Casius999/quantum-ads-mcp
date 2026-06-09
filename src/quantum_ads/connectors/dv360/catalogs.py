"""DV360 v4 enum catalogs + version-tolerant row mapping.

The Display Video API stamps list rows with enum strings (``entityStatus``, ``lineItemType``).
The 2026-06-10 Demand Gen launch adds new members the pinned client does not know yet; rather
than let an unknown value leak through (or crash a downstream consumer that pattern-matches on
the closed set), the row mapper routes those fields through
:func:`quantum_ads.core.versioning.enums.safe_enum_name`, collapsing unknown values to
``"UNKNOWN"``.

``map_row`` is pure and unit-tested directly (including with a fabricated unknown enum). Keep the
KNOWN_SETs deliberately small — they are the *recognised* members, not an exhaustive mirror of
the API; anything outside them is intentionally treated as unknown.
"""

from __future__ import annotations

from ...core.versioning.enums import safe_enum_name

# Recognised EntityStatus members (shared across advertisers / IOs / line items in DV360 v4).
KNOWN_ENTITY_STATUS: set[str] = {
    "ENTITY_STATUS_ACTIVE",
    "ENTITY_STATUS_ARCHIVED",
    "ENTITY_STATUS_DRAFT",
    "ENTITY_STATUS_PAUSED",
    "ENTITY_STATUS_SCHEDULED_FOR_DELETION",
    "ENTITY_STATUS_UNSPECIFIED",
}

# Recognised LineItemType members (DV360 v4, pre Demand Gen additions).
KNOWN_LINE_ITEM_TYPE: set[str] = {
    "LINE_ITEM_TYPE_UNSPECIFIED",
    "LINE_ITEM_TYPE_DISPLAY_DEFAULT",
    "LINE_ITEM_TYPE_DISPLAY_MOBILE_APP_INSTALL",
    "LINE_ITEM_TYPE_VIDEO_DEFAULT",
    "LINE_ITEM_TYPE_VIDEO_MOBILE_APP_INSTALL",
    "LINE_ITEM_TYPE_DISPLAY_MOBILE_APP_INVENTORY",
    "LINE_ITEM_TYPE_VIDEO_MOBILE_APP_INVENTORY",
    "LINE_ITEM_TYPE_AUDIO_DEFAULT",
}

# Field name -> the KNOWN set it is validated against, applied by ``map_row``.
_ENUM_FIELDS: dict[str, set[str]] = {
    "entityStatus": KNOWN_ENTITY_STATUS,
    "lineItemType": KNOWN_LINE_ITEM_TYPE,
}


def map_row(row: dict[str, object]) -> dict[str, object]:
    """Return a shallow copy of ``row`` with known enum fields passed through ``safe_enum_name``.

    Unknown ``entityStatus`` / ``lineItemType`` values become ``"UNKNOWN"`` (tolerating enum
    members added by monthly API releases such as Demand Gen). Non-enum fields and missing keys
    are left untouched; non-string enum values are left as-is (the API always sends strings).
    """
    mapped: dict[str, object] = dict(row)
    for field, known in _ENUM_FIELDS.items():
        value = mapped.get(field)
        if isinstance(value, str):
            mapped[field] = safe_enum_name(value, known)
    return mapped


def map_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Apply :func:`map_row` across a list of rows (enum-tolerant projection of a list response)."""
    return [map_row(row) for row in rows]
