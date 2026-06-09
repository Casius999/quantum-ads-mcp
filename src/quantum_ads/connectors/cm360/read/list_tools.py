"""CM360 read tools: pure param builders + a backend-invoking, enum-tolerant runner.

Each resource is listed by naming it in ``operation`` and carrying the profile id (and any extra
ids) in ``params`` (the ``ReadFn`` contract). Builders are pure and unit-tested directly.
``run_read`` invokes the injected backend and projects every row through ``catalogs.map_rows`` so
unknown ``status`` / ``compatibility`` / ``paymentSource`` enum values degrade to ``"UNKNOWN"``
instead of breaking, then wraps as ``{"rows", "row_count"}``.

Every dfareporting call is scoped to a user profile, so ``profile_id`` is the leading param on all
operations except ``userProfiles.list`` (which enumerates the profiles themselves and takes no id).
``reports.run`` additionally carries the ``report_id`` of the report definition to execute.
"""

from __future__ import annotations

from ..catalogs import map_rows
from ..types import ReadFn

# Operation (resource) names passed as the first ReadFn argument.
OP_USER_PROFILES_LIST = "userProfiles.list"
OP_CAMPAIGNS_LIST = "campaigns.list"
OP_PLACEMENTS_LIST = "placements.list"
OP_REPORTS_LIST = "reports.list"
OP_REPORT_RUN = "reports.run"
OP_FLOODLIGHT_ACTIVITIES_LIST = "floodlightActivities.list"


def build_profile_params(profile_id: str) -> dict[str, object]:
    """Pure: wrap a profile id as backend params (campaigns / placements / reports / Floodlight)."""
    params: dict[str, object] = {"profile_id": profile_id}
    return params


def build_report_run_params(profile_id: str, report_id: str) -> dict[str, object]:
    """Pure: wrap a profile id + report id as backend params for ``reports.run``."""
    params: dict[str, object] = {"profile_id": profile_id, "report_id": report_id}
    return params


def run_read(*, operation: str, params: dict[str, object], read: ReadFn) -> dict[str, object]:
    """Invoke the CM360 read backend for ``operation`` and wrap enum-tolerant rows."""
    rows = map_rows(read(operation, params))
    return {"rows": rows, "row_count": len(rows)}


def list_user_profiles(*, read: ReadFn) -> dict[str, object]:
    """Tool: list the CM360 user profiles the authenticated user can access (no profile id)."""
    params: dict[str, object] = {}
    return run_read(operation=OP_USER_PROFILES_LIST, params=params, read=read)


def list_campaigns(*, profile_id: str, read: ReadFn) -> dict[str, object]:
    """Tool: list campaigns visible to a user profile."""
    return run_read(
        operation=OP_CAMPAIGNS_LIST,
        params=build_profile_params(profile_id),
        read=read,
    )


def list_placements(*, profile_id: str, read: ReadFn) -> dict[str, object]:
    """Tool: list placements (ad-serving slots) visible to a user profile."""
    return run_read(
        operation=OP_PLACEMENTS_LIST,
        params=build_profile_params(profile_id),
        read=read,
    )


def list_reports(*, profile_id: str, read: ReadFn) -> dict[str, object]:
    """Tool: list report definitions owned by / visible to a user profile."""
    return run_read(
        operation=OP_REPORTS_LIST,
        params=build_profile_params(profile_id),
        read=read,
    )


def run_report(*, profile_id: str, report_id: str, read: ReadFn) -> dict[str, object]:
    """Tool: run a report definition by id under a user profile (returns the queued report file)."""
    return run_read(
        operation=OP_REPORT_RUN,
        params=build_report_run_params(profile_id, report_id),
        read=read,
    )


def list_floodlight_activities(*, profile_id: str, read: ReadFn) -> dict[str, object]:
    """Tool: list Floodlight activities (conversion tags) visible to a user profile."""
    return run_read(
        operation=OP_FLOODLIGHT_ACTIVITIES_LIST,
        params=build_profile_params(profile_id),
        read=read,
    )
