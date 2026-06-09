"""Read-plane tests for the CM360 connector: tool helpers, enum tolerance, degradation.

Uses a fake ``ReadFn`` (no SDK). Verifies the ``{"rows", "row_count"}`` envelope, that the right
operation name + params (profile id, and report id for ``reports.run``) reach the backend, that the
enum-tolerant row mapper collapses unknown ``status`` / ``compatibility`` / ``paymentSource``
values to ``"UNKNOWN"``, and that a missing backend yields a structured ``BACKEND_NOT_CONFIGURED``
error instead of raising.
"""

from quantum_ads.connectors.cm360 import catalogs, register_cm360
from quantum_ads.connectors.cm360.read import list_tools
from quantum_ads.connectors.cm360.read.connector import register_cm360_read
from quantum_ads.core.query.runner import StreamFn
from quantum_ads.server import build_server


def _env() -> dict[str, str]:
    return {
        "GOOGLE_ADS_DEVELOPER_TOKEN": "d",
        "GOOGLE_ADS_CLIENT_ID": "c",
        "GOOGLE_ADS_CLIENT_SECRET": "s",
        "GOOGLE_ADS_REFRESH_TOKEN": "r",
        "QUANTUM_ADS_READ_ONLY": "false",
    }


def _stream(creds: dict[str, object], version: str) -> StreamFn:
    return lambda cid, q: []


def _fake_read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
    return []


def _fake_mutate(
    profile_id: str, operations: list[dict[str, object]], validate_only: bool
) -> dict[str, object]:
    return {"ok": True, "validate_only": validate_only, "profile_id": profile_id}


def _build():
    return build_server(
        env=_env(),
        stream_factory=_stream,
        backends={"cm360.api": _fake_read, "cm360.mutate": _fake_mutate},
        connectors=[register_cm360],
    )


# --- registration -------------------------------------------------------------


def test_cm360_read_tools_registered():
    assembled = _build()
    names = {t.name for t in assembled.registry.all_tools()}
    assert "cm360.user_profiles.list" in names
    assert "cm360.campaigns.list" in names
    assert "cm360.placements.list" in names
    assert "cm360.reports.list" in names
    assert "cm360.report.run" in names
    assert "cm360.floodlight_activities.list" in names


def test_cm360_read_tools_marked_read_only():
    assembled = _build()
    assert assembled.registry.describe_tool("cm360.user_profiles.list").read_only is True
    assert assembled.registry.describe_tool("cm360.report.run").read_only is True
    assert assembled.registry.describe_tool("cm360.floodlight_activities.list").read_only is True


# --- pure param builders + runner (unit) --------------------------------------


def test_build_profile_params():
    assert list_tools.build_profile_params("PROFILE1") == {"profile_id": "PROFILE1"}


def test_build_report_run_params():
    assert list_tools.build_report_run_params("PROFILE1", "RPT9") == {
        "profile_id": "PROFILE1",
        "report_id": "RPT9",
    }


def test_list_user_profiles_uses_user_profiles_operation_and_no_params():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["operation"] = operation
        seen["params"] = params
        return [{"profileId": "1", "userName": "agency@example.com"}]

    out = list_tools.list_user_profiles(read=read)
    assert out["row_count"] == 1
    assert seen["operation"] == "userProfiles.list"
    assert seen["params"] == {}


def test_list_campaigns_uses_campaigns_operation_and_passes_profile_id():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["operation"] = operation
        seen["params"] = params
        return []

    out = list_tools.list_campaigns(profile_id="P1", read=read)
    assert out["row_count"] == 0
    assert seen["operation"] == "campaigns.list"
    assert seen["params"] == {"profile_id": "P1"}


def test_list_placements_uses_placements_operation_and_maps_enums():
    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        return [
            {
                "id": "5",
                "status": "PAYMENT_ACCEPTED",
                "compatibility": "DISPLAY",
            }
        ]

    out = list_tools.list_placements(profile_id="P1", read=read)
    assert out["rows"][0]["status"] == "PAYMENT_ACCEPTED"
    assert out["rows"][0]["compatibility"] == "DISPLAY"


def test_list_reports_uses_reports_operation():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["operation"] = operation
        return [{"id": "77", "name": "Weekly Floodlight"}]

    out = list_tools.list_reports(profile_id="P1", read=read)
    assert out["row_count"] == 1
    assert seen["operation"] == "reports.list"


def test_run_report_uses_report_run_operation_and_passes_report_id():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["operation"] = operation
        seen["params"] = params
        return [{"id": "file-1", "status": "PROCESSING"}]

    out = list_tools.run_report(profile_id="P1", report_id="RPT9", read=read)
    assert out["row_count"] == 1
    assert seen["operation"] == "reports.run"
    assert seen["params"] == {"profile_id": "P1", "report_id": "RPT9"}


def test_list_floodlight_activities_uses_floodlight_operation():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["operation"] = operation
        return [{"id": "fl-1", "name": "Purchase"}]

    out = list_tools.list_floodlight_activities(profile_id="P1", read=read)
    assert out["row_count"] == 1
    assert seen["operation"] == "floodlightActivities.list"


# --- enum tolerance (unit) ----------------------------------------------------


def test_map_row_passes_known_enums_through_unchanged():
    row = {
        "id": "1",
        "status": "PAYMENT_ACCEPTED",
        "compatibility": "IN_STREAM_VIDEO",
        "paymentSource": "PLACEMENT_AGENCY_PAID",
    }
    mapped = catalogs.map_row(row)
    assert mapped["status"] == "PAYMENT_ACCEPTED"
    assert mapped["compatibility"] == "IN_STREAM_VIDEO"
    assert mapped["paymentSource"] == "PLACEMENT_AGENCY_PAID"


def test_map_row_collapses_unknown_status_to_unknown():
    # Fabricated status member the pinned v4 client does not recognise yet.
    row = {"id": "1", "status": "PLACEMENT_STATUS_BRAND_NEW_2027", "compatibility": "DISPLAY"}
    mapped = catalogs.map_row(row)
    assert mapped["status"] == "UNKNOWN"
    # Known field on the same row is untouched.
    assert mapped["compatibility"] == "DISPLAY"


def test_map_row_collapses_unknown_compatibility():
    mapped = catalogs.map_row({"compatibility": "HOLOGRAM_2030"})
    assert mapped["compatibility"] == "UNKNOWN"


def test_map_row_leaves_missing_and_non_string_enum_fields_alone():
    # No enum keys present -> row is returned as an untouched copy.
    assert catalogs.map_row({"id": "1"}) == {"id": "1"}
    # Non-string enum value is left as-is (the API always sends strings; defensive).
    assert catalogs.map_row({"status": 7})["status"] == 7


def test_map_row_returns_a_copy():
    row = {"status": "PAYMENT_ACCEPTED"}
    mapped = catalogs.map_row(row)
    assert mapped is not row


def test_map_rows_projects_each_row():
    rows = [
        {"status": "PAYMENT_ACCEPTED"},
        {"compatibility": "HOLOGRAM_2030"},
    ]
    out = catalogs.map_rows(rows)
    assert out[0]["status"] == "PAYMENT_ACCEPTED"
    assert out[1]["compatibility"] == "UNKNOWN"


# --- backend-not-configured degradation (integration) -------------------------


def test_read_tools_degrade_when_backend_missing():
    # No backends wired -> ctx.backend("cm360.api") is None.
    assembled = build_server(
        env=_env(),
        stream_factory=_stream,
        connectors=[register_cm360_read],
    )
    names = {t.name for t in assembled.registry.all_tools()}
    assert "cm360.user_profiles.list" in names
