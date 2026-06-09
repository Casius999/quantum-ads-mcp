"""Google Data Manager API connector (first-party data ingestion plane).

Public entry point: :func:`register_datamanager` mounts both the read and write tool planes.

This is the SOTA upload plane for first-party data: Customer Match audience members and
offline/enhanced conversions. The legacy **Google Ads API upload path is blocked since
2026-06-15**; uploads now go through the Data Manager API (``datamanager`` v1) instead.

Hard requirements callers must honor (enforced operationally, not by this connector):
  - Member identifiers (email, phone, address) MUST be SHA-256 hashed and normalized by the
    operator before being passed in. This connector shapes the op dicts but never hashes.
  - Consent (``ad_user_data`` / ``ad_personalization``) is required for EEA traffic under
    Consent Mode v2 and is carried on every write op.
"""

from __future__ import annotations

from .connector import register_datamanager

__all__ = ["register_datamanager"]
