"""Write-plane tests for the Merchant API connector: op builders + guarded execution.

Unit-tests the pure ``product_ops`` builders, then drives a guarded mutation end-to-end with a
fake ``MutateFn`` (no SDK) through the shared ``WriteExecutor`` to confirm the
validate_only-preview -> confirm -> apply flow and the missing-backend degradation.
"""

from quantum_ads.connectors.merchant.write import product_ops
from quantum_ads.connectors.merchant.write.connector import (
    _merchant_id_from_product_name,
    register_merchant_write,
)
from quantum_ads.core.context import ServerContext
from quantum_ads.core.registry.registry import ConnectorRegistry
from quantum_ads.core.safety.audit import AuditLedger
from quantum_ads.core.safety.mode import SafetyMode
from quantum_ads.core.versioning.version_manager import VersionManager

# --- pure op builders (unit) --------------------------------------------------


def test_build_insert_product_ops():
    ops = product_ops.build_insert_product_ops({"offerId": "sku-1", "title": "Widget"})
    assert ops == [
        {
            "entity": "product",
            "action": "insert",
            "product_input": {"offerId": "sku-1", "title": "Widget"},
        }
    ]


def test_build_update_product_ops():
    ops = product_ops.build_update_product_ops("accounts/42/products/x", {"title": "New"})
    assert ops[0]["entity"] == "product"
    assert ops[0]["action"] == "update"
    assert ops[0]["product_name"] == "accounts/42/products/x"
    assert ops[0]["fields"] == {"title": "New"}


def test_build_delete_product_ops():
    ops = product_ops.build_delete_product_ops("accounts/42/products/x")
    assert ops == [
        {"entity": "product", "action": "delete", "product_name": "accounts/42/products/x"}
    ]


def test_merchant_id_extracted_from_product_name():
    assert _merchant_id_from_product_name("accounts/42/products/online~en~US~sku") == "42"


def test_merchant_id_falls_back_to_raw_on_unexpected_shape():
    assert _merchant_id_from_product_name("not-a-resource-name") == "not-a-resource-name"


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


def test_insert_previews_then_confirms_with_fake_mutate():
    calls: list[bool] = []

    def fake_mutate(
        account_id: str, operations: list[dict[str, object]], validate_only: bool
    ) -> dict[str, object]:
        calls.append(validate_only)
        return {"account_id": account_id, "validate_only": validate_only, "ops": len(operations)}

    app = _RecordingApp()
    ctx = _ctx({"merchant.mutate": fake_mutate})
    register_merchant_write(app, ctx)  # type: ignore[arg-type]
    insert = app.fns["merchant.product.insert"]

    first = insert(merchant_id="42", product_input={"offerId": "sku-1"})  # type: ignore[operator]
    assert first["applied"] is False
    assert calls == [True]  # validate_only preview only

    token = first["confirm_token"]
    second = insert(  # type: ignore[operator]
        merchant_id="42", product_input={"offerId": "sku-1"}, confirm=token
    )
    assert second["applied"] is True
    assert calls == [True, True, False]  # preview re-run, then real apply


def test_write_tool_degrades_when_mutate_backend_missing():
    app = _RecordingApp()
    ctx = _ctx({})  # no merchant.mutate backend
    register_merchant_write(app, ctx)  # type: ignore[arg-type]
    delete = app.fns["merchant.product.delete"]

    out = delete(product_name="accounts/42/products/x")  # type: ignore[operator]
    assert isinstance(out["error"], dict)
    assert out["error"]["code"] == "MUTATE_NOT_CONFIGURED"


def test_write_blocked_in_read_only_mode():
    def fake_mutate(
        account_id: str, operations: list[dict[str, object]], validate_only: bool
    ) -> dict[str, object]:
        return {"should": "not be reached for the real apply"}

    app = _RecordingApp()
    ctx = _ctx({"merchant.mutate": fake_mutate}, read_only=True)
    register_merchant_write(app, ctx)  # type: ignore[arg-type]
    delete = app.fns["merchant.product.delete"]

    out = delete(product_name="accounts/42/products/x")  # type: ignore[operator]
    assert isinstance(out["error"], dict)
    assert out["error"]["code"] == "READ_ONLY"
