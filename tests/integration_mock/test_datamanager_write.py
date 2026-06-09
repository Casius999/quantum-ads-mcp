"""Write-plane tests for the Data Manager connector: op builders + guarded execution.

Unit-tests the pure ``audience_ops`` builders and ``normalize_email``, then drives a guarded
upload end-to-end with a fake ``MutateFn`` (no SDK) through the shared ``WriteExecutor`` to confirm
the validate_only-preview -> confirm -> apply flow, the missing-backend degradation, and the
read-only block.
"""

from quantum_ads.connectors.datamanager.write import audience_ops
from quantum_ads.connectors.datamanager.write.connector import register_datamanager_write
from quantum_ads.core.context import ServerContext
from quantum_ads.core.registry.registry import ConnectorRegistry
from quantum_ads.core.safety.audit import AuditLedger
from quantum_ads.core.safety.mode import SafetyMode
from quantum_ads.core.versioning.version_manager import VersionManager

# --- pure helpers (unit) ------------------------------------------------------


def test_normalize_email_lowercases_and_strips():
    assert audience_ops.normalize_email("  Foo.Bar@Example.COM  ") == "foo.bar@example.com"


def test_normalize_email_is_idempotent():
    once = audience_ops.normalize_email("  Foo@Example.com ")
    assert audience_ops.normalize_email(once) == once


def test_build_upload_members_ops_shapes_entity_and_consent():
    members: list[dict[str, object]] = [{"emailAddress": "deadbeef"}]
    consent: dict[str, object] = {"ad_user_data": "GRANTED", "ad_personalization": "GRANTED"}
    ops = audience_ops.build_upload_members_ops("dest-1", "aud-9", members, consent)
    assert ops == [
        {
            "entity": "audience_member",
            "action": "upload",
            "destination_id": "dest-1",
            "audience_id": "aud-9",
            "members": [{"emailAddress": "deadbeef"}],
            "consent": {"ad_user_data": "GRANTED", "ad_personalization": "GRANTED"},
        }
    ]


def test_build_remove_members_ops_has_no_consent_key():
    ops = audience_ops.build_remove_members_ops("dest-1", "aud-9", [{"emailAddress": "deadbeef"}])
    assert ops[0]["entity"] == "audience_member"
    assert ops[0]["action"] == "remove"
    assert ops[0]["destination_id"] == "dest-1"
    assert ops[0]["audience_id"] == "aud-9"
    assert "consent" not in ops[0]


def test_build_upload_conversions_ops_shapes_entity_and_consent():
    conversions: list[dict[str, object]] = [{"conversionAction": "ca/1", "value": 9.99}]
    consent: dict[str, object] = {"ad_user_data": "GRANTED", "ad_personalization": "DENIED"}
    ops = audience_ops.build_upload_conversions_ops("dest-2", conversions, consent)
    assert ops == [
        {
            "entity": "conversion",
            "action": "upload",
            "destination_id": "dest-2",
            "conversions": [{"conversionAction": "ca/1", "value": 9.99}],
            "consent": {"ad_user_data": "GRANTED", "ad_personalization": "DENIED"},
        }
    ]


def test_builders_copy_inputs_no_mutation_leak():
    members: list[dict[str, object]] = [{"emailAddress": "deadbeef"}]
    ops = audience_ops.build_upload_members_ops("d", "a", members, {})
    members.append({"emailAddress": "extra"})
    # The op must hold a snapshot, not the caller's list.
    assert ops[0]["members"] == [{"emailAddress": "deadbeef"}]


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


def test_upload_members_previews_then_confirms_with_fake_mutate():
    calls: list[bool] = []
    seen_account: list[str] = []

    def fake_mutate(
        account_id: str, operations: list[dict[str, object]], validate_only: bool
    ) -> dict[str, object]:
        calls.append(validate_only)
        seen_account.append(account_id)
        return {"account_id": account_id, "validate_only": validate_only, "ops": len(operations)}

    app = _RecordingApp()
    ctx = _ctx({"datamanager.api": fake_mutate})
    register_datamanager_write(app, ctx)  # type: ignore[arg-type]
    upload = app.fns["datamanager.audience.upload_members"]

    consent: dict[str, object] = {"ad_user_data": "GRANTED", "ad_personalization": "GRANTED"}
    first = upload(  # type: ignore[operator]
        destination_id="dest-1",
        audience_id="aud-9",
        members=[{"emailAddress": "deadbeef"}],
        consent=consent,
    )
    assert first["applied"] is False
    assert calls == [True]  # validate_only preview only
    # customer_id is bound to the destination id (account_id == destination_id).
    assert seen_account == ["dest-1"]

    token = first["confirm_token"]
    second = upload(  # type: ignore[operator]
        destination_id="dest-1",
        audience_id="aud-9",
        members=[{"emailAddress": "deadbeef"}],
        consent=consent,
        confirm=token,
    )
    assert second["applied"] is True
    assert calls == [True, True, False]  # preview re-run, then real apply


def test_conversions_upload_degrades_when_mutate_backend_missing():
    app = _RecordingApp()
    ctx = _ctx({})  # no datamanager.api backend
    register_datamanager_write(app, ctx)  # type: ignore[arg-type]
    upload = app.fns["datamanager.conversions.upload"]

    out = upload(destination_id="dest-2", conversions=[{"x": 1}], consent={})  # type: ignore[operator]
    assert isinstance(out["error"], dict)
    assert out["error"]["code"] == "MUTATE_NOT_CONFIGURED"


def test_write_blocked_in_read_only_mode():
    def fake_mutate(
        account_id: str, operations: list[dict[str, object]], validate_only: bool
    ) -> dict[str, object]:
        return {"should": "not be reached for the real apply"}

    app = _RecordingApp()
    ctx = _ctx({"datamanager.api": fake_mutate}, read_only=True)
    register_datamanager_write(app, ctx)  # type: ignore[arg-type]
    remove = app.fns["datamanager.audience.remove_members"]

    out = remove(  # type: ignore[operator]
        destination_id="dest-1", audience_id="aud-9", members=[{"emailAddress": "deadbeef"}]
    )
    assert isinstance(out["error"], dict)
    assert out["error"]["code"] == "READ_ONLY"
