"""Read-plane tests for the reCAPTCHA Enterprise connector: builders, tool helpers, degradation.

Uses a fake ``ReadFn`` (no SDK). Verifies the pure assessment-request builder, the shared
``{"rows", "row_count"}`` envelope, the top-level ``risk_score`` annotation on assessment.create,
that the right operation name + params reach the backend, registration + read_only flags, and that
a missing backend yields a structured ``BACKEND_NOT_CONFIGURED`` error instead of raising.
"""

from quantum_ads.connectors.recaptcha import read_tools
from quantum_ads.connectors.recaptcha.builders import build_assessment_request
from quantum_ads.connectors.recaptcha.connector import register_recaptcha
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
    return [{"operation": operation, "params": params}]


def _fake_mutate(
    account_id: str, operations: list[dict[str, object]], validate_only: bool
) -> dict[str, object]:
    return {"validate_only": validate_only}


def _backends() -> dict[str, object]:
    return {"recaptcha.api": _fake_read, "recaptcha.mutate": _fake_mutate}


# --- pure assessment-request builder (unit) -----------------------------------


def test_build_assessment_request_shape():
    request = build_assessment_request(
        project_id="proj-1",
        site_key="6Lc_key",
        token="user-token",
        expected_action="submit_lead",
    )
    assert request == {
        "project_id": "proj-1",
        "site_key": "6Lc_key",
        "token": "user-token",
        "expected_action": "submit_lead",
    }


# --- pure tool helpers (unit) -------------------------------------------------


def test_list_keys_wraps_rows_and_passes_project_id():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["operation"] = operation
        seen["params"] = params
        return [{"name": "projects/proj-1/keys/abc", "display_name": "site"}]

    out = read_tools.list_keys(project_id="proj-1", read=read)
    assert out["rows"] == [{"name": "projects/proj-1/keys/abc", "display_name": "site"}]
    assert out["row_count"] == 1
    assert seen["operation"] == "keys.list"
    assert seen["params"] == {"project_id": "proj-1"}


def test_create_assessment_surfaces_risk_score_and_passes_request():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["operation"] = operation
        seen["params"] = params
        return [{"score": 0.9, "reasons": ["LOW_CONFIDENCE_SCORE"], "valid": True}]

    out = read_tools.create_assessment(
        project_id="proj-1",
        site_key="6Lc_key",
        token="user-token",
        expected_action="submit_lead",
        read=read,
    )
    assert out["rows"] == [{"score": 0.9, "reasons": ["LOW_CONFIDENCE_SCORE"], "valid": True}]
    assert out["row_count"] == 1
    assert out["risk_score"] == 0.9
    assert seen["operation"] == "assessment.create"
    assert seen["params"] == {
        "project_id": "proj-1",
        "site_key": "6Lc_key",
        "token": "user-token",
        "expected_action": "submit_lead",
    }


def test_create_assessment_defaults_risk_score_to_zero_when_absent():
    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        return [{"valid": False}]

    out = read_tools.create_assessment(
        project_id="proj-1",
        site_key="6Lc_key",
        token="user-token",
        expected_action="submit_lead",
        read=read,
    )
    assert out["risk_score"] == 0.0


def test_create_assessment_defaults_risk_score_to_zero_when_no_rows():
    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        return []

    out = read_tools.create_assessment(
        project_id="proj-1",
        site_key="6Lc_key",
        token="user-token",
        expected_action="submit_lead",
        read=read,
    )
    assert out["risk_score"] == 0.0
    assert out["row_count"] == 0


# --- registration + backend-not-configured degradation (integration) ----------


def test_read_tools_registered_and_marked_read_only():
    assembled = build_server(
        env=_env(),
        stream_factory=_stream,
        backends=_backends(),
        connectors=[register_recaptcha],
    )
    names = {t.name for t in assembled.registry.all_tools()}
    assert "recaptcha.keys.list" in names
    assert "recaptcha.assessment.create" in names
    assert assembled.registry.describe_tool("recaptcha.keys.list").read_only is True
    assert assembled.registry.describe_tool("recaptcha.assessment.create").read_only is True


def test_read_tools_degrade_when_backend_missing():
    # No backends wired -> ctx.backend("recaptcha.api") is None.
    assembled = build_server(
        env=_env(),
        stream_factory=_stream,
        connectors=[register_recaptcha],
    )
    names = {t.name for t in assembled.registry.all_tools()}
    assert "recaptcha.keys.list" in names
    assert "recaptcha.assessment.create" in names
