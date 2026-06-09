"""Write-plane tests for the reCAPTCHA Enterprise connector: op builders + guarded execution.

Unit-tests the pure ``build_annotate_ops`` builder, then drives a guarded mutation end-to-end with
a fake ``MutateFn`` (no SDK) through the shared ``WriteExecutor`` to confirm the
validate_only-preview -> confirm -> apply flow, the read_only flags, and the missing-backend /
read-only degradations. ``account_id`` (the MutateFn's first arg) carries the GCP project id.
"""

from quantum_ads.connectors.recaptcha import builders
from quantum_ads.connectors.recaptcha.connector import register_recaptcha
from quantum_ads.core.context import ServerContext
from quantum_ads.core.query.runner import StreamFn
from quantum_ads.core.registry.registry import ConnectorRegistry
from quantum_ads.core.safety.audit import AuditLedger
from quantum_ads.core.safety.mode import SafetyMode
from quantum_ads.core.versioning.version_manager import VersionManager
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


# --- pure op builder (unit) ---------------------------------------------------


def test_build_annotate_ops_shape():
    ops = builders.build_annotate_ops("proj-1", "assess-123", "LEGITIMATE")
    assert ops == [
        {
            "entity": "annotation",
            "action": "annotate",
            "project_id": "proj-1",
            "assessment_id": "assess-123",
            "annotation": "LEGITIMATE",
        }
    ]


def test_build_annotate_ops_upper_cases_annotation():
    ops = builders.build_annotate_ops("proj-1", "assess-123", "fraudulent")
    assert ops[0]["annotation"] == "FRAUDULENT"


# --- guarded write flow (integration, fake MutateFn) --------------------------


def _ctx(backends: dict[str, object], read_only: bool = False) -> ServerContext:
    return ServerContext(
        creds={},
        version="v1",
        stream_factory=lambda c, v: lambda cid, q: [],
        version_manager=VersionManager("v1", client_factory=lambda c, v: None),
        safety=SafetyMode(read_only=read_only),
        registry=ConnectorRegistry(),
        audit=AuditLedger.ephemeral(),
        backends=backends,
    )


class _RecordingApp:
    """Captures the functions registered via FastMCP's ``add_tool`` so we can call them."""

    def __init__(self) -> None:
        self.fns: dict[str, object] = {}

    def tool(self, name: str, description: str):
        def decorator(fn):
            self.fns[name] = fn
            return fn

        return decorator


def test_assessment_annotate_previews_then_confirms_with_fake_mutate():
    calls: list[bool] = []

    def fake_mutate(
        account_id: str, operations: list[dict[str, object]], validate_only: bool
    ) -> dict[str, object]:
        calls.append(validate_only)
        return {"account_id": account_id, "validate_only": validate_only, "ops": len(operations)}

    app = _RecordingApp()
    ctx = _ctx({"recaptcha.mutate": fake_mutate})
    register_recaptcha(app, ctx)  # type: ignore[arg-type]
    annotate = app.fns["recaptcha.assessment.annotate"]

    first = annotate(  # type: ignore[operator]
        project_id="proj-1",
        assessment_id="assess-123",
        annotation="LEGITIMATE",
    )
    assert first["applied"] is False
    assert calls == [True]  # validate_only preview only

    token = first["confirm_token"]
    second = annotate(  # type: ignore[operator]
        project_id="proj-1",
        assessment_id="assess-123",
        annotation="LEGITIMATE",
        confirm=token,
    )
    assert second["applied"] is True
    assert calls == [True, True, False]  # preview re-run, then real apply


def test_write_tools_registered_and_marked_not_read_only():
    def fake_mutate(
        account_id: str, operations: list[dict[str, object]], validate_only: bool
    ) -> dict[str, object]:
        return {"validate_only": validate_only}

    assembled = build_server(
        env=_env(),
        stream_factory=_stream,
        backends={"recaptcha.mutate": fake_mutate},
        connectors=[register_recaptcha],
    )
    names = {t.name for t in assembled.registry.all_tools()}
    assert "recaptcha.assessment.annotate" in names
    assert assembled.registry.describe_tool("recaptcha.assessment.annotate").read_only is False


def test_write_tool_degrades_when_mutate_backend_missing():
    app = _RecordingApp()
    ctx = _ctx({})  # no recaptcha.mutate backend
    register_recaptcha(app, ctx)  # type: ignore[arg-type]
    annotate = app.fns["recaptcha.assessment.annotate"]

    out = annotate(  # type: ignore[operator]
        project_id="proj-1", assessment_id="assess-123", annotation="LEGITIMATE"
    )
    assert isinstance(out["error"], dict)
    assert out["error"]["code"] == "MUTATE_NOT_CONFIGURED"


def test_write_blocked_in_read_only_mode():
    def fake_mutate(
        account_id: str, operations: list[dict[str, object]], validate_only: bool
    ) -> dict[str, object]:
        return {"should": "not be reached for the real apply"}

    app = _RecordingApp()
    ctx = _ctx({"recaptcha.mutate": fake_mutate}, read_only=True)
    register_recaptcha(app, ctx)  # type: ignore[arg-type]
    annotate = app.fns["recaptcha.assessment.annotate"]

    out = annotate(  # type: ignore[operator]
        project_id="proj-1", assessment_id="assess-123", annotation="LEGITIMATE"
    )
    assert isinstance(out["error"], dict)
    assert out["error"]["code"] == "READ_ONLY"
