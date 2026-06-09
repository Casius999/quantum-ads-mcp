"""Google Business Profile guarded write connector: op builders + guarded execution + degradation.

Unit-tests the pure ``mutate_tools`` builders, then drives a guarded mutation end-to-end with a
fake ``MutateFn`` (no SDK) through the shared ``WriteExecutor`` to confirm the
validate_only-preview -> confirm -> apply flow, the missing-backend degradation, and the read-only
block. The real googleapiclient SDK is never imported.
"""

from quantum_ads.connectors.gbp import register_gbp
from quantum_ads.connectors.gbp.write import mutate_tools
from quantum_ads.connectors.gbp.write.connector import register_gbp_write
from quantum_ads.core.context import ServerContext
from quantum_ads.core.query.runner import StreamFn
from quantum_ads.core.registry.registry import ConnectorRegistry
from quantum_ads.core.safety.audit import AuditLedger
from quantum_ads.core.safety.confirm import confirm_token
from quantum_ads.core.safety.mode import SafetyMode
from quantum_ads.core.safety.write_executor import WriteExecutor
from quantum_ads.core.versioning.version_manager import VersionManager


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
    return [{"operation": operation}]


def _fake_mutate(
    resource: str, operations: list[dict[str, object]], validate_only: bool
) -> dict[str, object]:
    return {"validate_only": validate_only}


def _backends() -> dict[str, object]:
    return {"gbp.api": _fake_read, "gbp.reviews": _fake_read, "gbp.mutate": _fake_mutate}


# --- registration -----------------------------------------------------------------------------


def test_gbp_write_tools_registered():
    from quantum_ads.server import build_server

    assembled = build_server(
        env=_env(),
        stream_factory=_stream,
        backends=_backends(),
        connectors=[register_gbp],
    )
    names = {t.name for t in assembled.registry.all_tools()}
    assert "gbp.review.reply" in names
    assert "gbp.location.update" in names


def test_gbp_write_tools_marked_not_read_only():
    from quantum_ads.server import build_server

    assembled = build_server(
        env=_env(),
        stream_factory=_stream,
        backends=_backends(),
        connectors=[register_gbp_write],
    )
    assert assembled.registry.describe_tool("gbp.review.reply").read_only is False
    assert assembled.registry.describe_tool("gbp.location.update").read_only is False


# --- pure op builders (unit) ------------------------------------------------------------------


def test_build_review_reply_ops():
    ops = mutate_tools.build_review_reply_ops(
        "accounts/1/locations/123/reviews/abc", "Thanks for visiting!"
    )
    assert ops == [
        {
            "entity": "review",
            "action": "reply",
            "review_name": "accounts/1/locations/123/reviews/abc",
            "comment": "Thanks for visiting!",
        }
    ]


def test_build_location_update_ops():
    ops = mutate_tools.build_location_update_ops(
        "locations/123", {"title": "Cafe Souverain", "websiteUri": "https://example.com"}
    )
    assert ops == [
        {
            "entity": "location",
            "action": "update",
            "location_name": "locations/123",
            "fields": {"title": "Cafe Souverain", "websiteUri": "https://example.com"},
        }
    ]


def test_build_location_update_ops_copies_fields():
    fields: dict[str, object] = {"title": "Original"}
    ops = mutate_tools.build_location_update_ops("locations/123", fields)
    fields["title"] = "Mutated"
    # The builder snapshots fields so later caller mutation does not leak into the op.
    assert ops[0]["fields"] == {"title": "Original"}


# --- guarded flow through WriteExecutor (preview -> confirm -> applied) ------------------------


def _executor() -> WriteExecutor:
    return WriteExecutor(_fake_mutate, SafetyMode(read_only=False), AuditLedger.ephemeral())


def test_review_reply_preview_then_confirm():
    ex = _executor()
    ops = mutate_tools.build_review_reply_ops(
        "accounts/1/locations/123/reviews/abc", "Thanks for visiting!"
    )

    preview = ex.execute(
        op="gbp.review.reply",
        customer_id="accounts/1/locations/123/reviews/abc",
        operations=ops,
    )
    assert preview["applied"] is False
    assert preview["preview"] == {"validate_only": True}
    token = preview["confirm_token"]

    # token binds to the exact (op, payload) the executor builds.
    expected = confirm_token(
        "gbp.review.reply",
        {"customer_id": "accounts/1/locations/123/reviews/abc", "operations": ops},
    )
    assert token == expected

    applied = ex.execute(
        op="gbp.review.reply",
        customer_id="accounts/1/locations/123/reviews/abc",
        operations=ops,
        confirm=str(token),
    )
    assert applied["applied"] is True
    assert applied["result"] == {"validate_only": False}
    assert isinstance(applied["audit_signature"], str)


def test_review_reply_blocked_in_read_only_mode():
    ex = WriteExecutor(_fake_mutate, SafetyMode(read_only=True), AuditLedger.ephemeral())
    ops = mutate_tools.build_review_reply_ops("accounts/1/locations/123/reviews/abc", "Thanks!")
    out = ex.execute(
        op="gbp.review.reply",
        customer_id="accounts/1/locations/123/reviews/abc",
        operations=ops,
    )
    assert isinstance(out["error"], dict)
    assert out["error"]["code"] == "READ_ONLY"


# --- guarded flow through the registered FastMCP callable (fake MutateFn) ----------------------


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


def test_location_update_previews_then_confirms_via_registered_tool():
    calls: list[bool] = []

    def fake_mutate(
        resource: str, operations: list[dict[str, object]], validate_only: bool
    ) -> dict[str, object]:
        calls.append(validate_only)
        return {"resource": resource, "validate_only": validate_only, "ops": len(operations)}

    app = _RecordingApp()
    ctx = _ctx({"gbp.mutate": fake_mutate})
    register_gbp_write(app, ctx)  # type: ignore[arg-type]
    update = app.fns["gbp.location.update"]

    first = update(  # type: ignore[operator]
        location_name="locations/123", fields={"title": "Cafe Souverain"}
    )
    assert first["applied"] is False
    assert calls == [True]  # validate_only preview only

    token = first["confirm_token"]
    second = update(  # type: ignore[operator]
        location_name="locations/123",
        fields={"title": "Cafe Souverain"},
        confirm=token,
    )
    assert second["applied"] is True
    assert calls == [True, True, False]  # preview re-run, then real apply


def test_write_tool_degrades_when_mutate_backend_missing():
    app = _RecordingApp()
    ctx = _ctx({})  # no gbp.mutate backend
    register_gbp_write(app, ctx)  # type: ignore[arg-type]
    reply = app.fns["gbp.review.reply"]

    out = reply(  # type: ignore[operator]
        review_name="accounts/1/locations/123/reviews/abc", comment="Thanks!"
    )
    assert isinstance(out["error"], dict)
    assert out["error"]["code"] == "MUTATE_NOT_CONFIGURED"
