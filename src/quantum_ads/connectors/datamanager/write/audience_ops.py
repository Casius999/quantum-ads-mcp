"""Pure operation builders for Data Manager first-party uploads.

Each builder returns a list with a single entity-tagged op dict. The ``entity``/``action`` keys
let the SDK mutate boundary dispatch to the right Data Manager call; the remaining keys carry the
destination/audience ids, the member or conversion payload, and the required consent block.

HASHING IS THE OPERATOR'S RESPONSIBILITY. These builders only *shape* the dict — they never hash.
Member identifiers (email, phone, address fields) MUST already be SHA-256 hashed and normalized
by the caller before reaching here. The one normalization helper exposed (``normalize_email``)
lowercases + strips whitespace; it does NOT hash. Apply it (and your own phone/address
normalization) before SHA-256, then pass the resulting hex digests in as ``members``.

These are pure and unit-tested directly (no SDK needed).
"""

from __future__ import annotations

# entity tags carried on each op so the SDK mutate boundary can dispatch.
ENTITY_AUDIENCE_MEMBER = "audience_member"
ENTITY_CONVERSION = "conversion"


def normalize_email(email: str) -> str:
    """Normalize an email for Customer Match: lowercase + strip surrounding whitespace.

    This is the pre-hash normalization step only. It does NOT hash. The caller must SHA-256 the
    returned value (hex digest) before handing it to :func:`build_upload_members_ops`.
    """
    return email.strip().lower()


def build_upload_members_ops(
    destination_id: str,
    audience_id: str,
    members: list[dict[str, object]],
    consent: dict[str, object],
) -> list[dict[str, object]]:
    """Build the op to upload (add) Customer Match audience members.

    ``members`` must already carry SHA-256-hashed, normalized identifiers (this builder does not
    hash). ``consent`` carries the Consent Mode v2 signals (``ad_user_data`` / ``ad_personalization``)
    required for EEA traffic.
    """
    op: dict[str, object] = {
        "entity": ENTITY_AUDIENCE_MEMBER,
        "action": "upload",
        "destination_id": destination_id,
        "audience_id": audience_id,
        "members": [dict(m) for m in members],
        "consent": dict(consent),
    }
    return [op]


def build_remove_members_ops(
    destination_id: str,
    audience_id: str,
    members: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Build the op to remove Customer Match audience members.

    ``members`` must already carry SHA-256-hashed, normalized identifiers (this builder does not
    hash). Removal does not require consent signals — only the (hashed) identifiers to match.
    """
    op: dict[str, object] = {
        "entity": ENTITY_AUDIENCE_MEMBER,
        "action": "remove",
        "destination_id": destination_id,
        "audience_id": audience_id,
        "members": [dict(m) for m in members],
    }
    return [op]


def build_upload_conversions_ops(
    destination_id: str,
    conversions: list[dict[str, object]],
    consent: dict[str, object],
) -> list[dict[str, object]]:
    """Build the op to upload offline + enhanced conversions.

    ``conversions`` carry the conversion payloads; any user identifiers used for enhanced
    conversions must already be SHA-256-hashed and normalized (this builder does not hash).
    ``consent`` carries the Consent Mode v2 signals required for EEA traffic.
    """
    op: dict[str, object] = {
        "entity": ENTITY_CONVERSION,
        "action": "upload",
        "destination_id": destination_id,
        "conversions": [dict(c) for c in conversions],
        "consent": dict(consent),
    }
    return [op]
