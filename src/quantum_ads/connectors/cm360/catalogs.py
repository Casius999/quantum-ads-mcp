"""CM360 (dfareporting v4) enum catalogs + version-tolerant row mapping.

The dfareporting API stamps list rows with enum strings (placement ``status``/``compatibility``,
campaign/placement ``paymentSource``). Monthly API releases add new members the pinned client does
not know yet; rather than let an unknown value leak through (or crash a downstream consumer that
pattern-matches on the closed set), the row mapper routes those fields through
:func:`quantum_ads.core.versioning.enums.safe_enum_name`, collapsing unknown values to
``"UNKNOWN"``.

``map_row`` is pure and unit-tested directly (including with a fabricated unknown enum). Keep the
KNOWN_SETs deliberately small — they are the *recognised* members, not an exhaustive mirror of the
API; anything outside them is intentionally treated as unknown.
"""

from __future__ import annotations

from ...core.versioning.enums import safe_enum_name

# Recognised ``status`` members. The dfareporting API reuses the field name ``status`` across
# resources: placements carry Placement.status, while the report-run file response carries
# File.status. ``map_row`` is field-name keyed and applied uniformly across every read response
# (including ``reports.run``), so both member families are recognised here — otherwise a legitimate
# report-file status (e.g. ``PROCESSING``) would collapse to ``"UNKNOWN"``.
KNOWN_PLACEMENT_STATUS: set[str] = {
    # Placement.status
    "PLACEMENT_STATUS_UNKNOWN",
    "ACKNOWLEDGE_ACCEPTANCE",
    "ACKNOWLEDGE_REJECTION",
    "DRAFT",
    "PAYMENT_ACCEPTED",
    "PAYMENT_REJECTED",
    "PENDING_REVIEW",
    # File.status (reports.run queued-file lifecycle)
    "PROCESSING",
    "REPORT_AVAILABLE",
    "FAILED",
    "CANCELLED",
}

# Recognised placement ``compatibility`` members (display / app / in-stream surfaces).
KNOWN_COMPATIBILITY: set[str] = {
    "DISPLAY",
    "DISPLAY_INTERSTITIAL",
    "APP",
    "APP_INTERSTITIAL",
    "IN_STREAM_VIDEO",
    "IN_STREAM_AUDIO",
}

# Recognised ``paymentSource`` members (shared across campaigns / placements).
KNOWN_PAYMENT_SOURCE: set[str] = {
    "PLACEMENT_AGENCY_PAID",
    "PLACEMENT_PUBLISHER_PAID",
}

# Field name -> the KNOWN set it is validated against, applied by ``map_row``.
_ENUM_FIELDS: dict[str, set[str]] = {
    "status": KNOWN_PLACEMENT_STATUS,
    "compatibility": KNOWN_COMPATIBILITY,
    "paymentSource": KNOWN_PAYMENT_SOURCE,
}


def map_row(row: dict[str, object]) -> dict[str, object]:
    """Return a shallow copy of ``row`` with known enum fields passed through ``safe_enum_name``.

    Unknown ``status`` / ``compatibility`` / ``paymentSource`` values become ``"UNKNOWN"``
    (tolerating enum members added by monthly dfareporting releases). Non-enum fields and missing
    keys are left untouched; non-string enum values are left as-is (the API always sends strings).
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
