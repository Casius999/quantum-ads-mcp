"""Display & Video 360 (Display Video API v4) connector: read + guarded write.

DV360 is the programmatic buying control plane for the sovereign agency: advertisers,
campaigns, insertion orders, and line items. ``register_dv360`` is the single entry point
mounting both planes; the sub-registrars are re-exported for callers that mount one plane in
isolation (tests).

API v4, June 2026: the 2026-06-10 Demand Gen launch can introduce new ``entityStatus`` /
``lineItemType`` enum values in list responses — the read row mapper routes those strings
through :func:`quantum_ads.core.versioning.enums.safe_enum_name` so unknown values degrade to
``"UNKNOWN"`` instead of breaking the pinned client.
"""

from __future__ import annotations

from .connector import register_dv360, register_dv360_read, register_dv360_write

__all__ = ["register_dv360", "register_dv360_read", "register_dv360_write"]
