"""Campaign Manager 360 (dfareporting API v4) connector: read + guarded write.

CM360 is the ad-serving / trafficking / measurement control plane for the sovereign agency:
user profiles, campaigns, placements, Floodlight activities (conversion tags), and the reporting
subsystem (report definitions + report runs). ``register_cm360`` is the single entry point
mounting both planes; the sub-registrars are re-exported for callers that mount one plane in
isolation (tests).

Every CM360 API call is scoped to a **user profile** (``profileId``): the dfareporting API keys
access off the profile rather than a raw account id, so it is threaded as the leading argument on
every tool (and bound as the ``customer_id`` / ``account_id`` on the write plane).
"""

from __future__ import annotations

from .connector import register_cm360, register_cm360_read, register_cm360_write

__all__ = ["register_cm360", "register_cm360_read", "register_cm360_write"]
