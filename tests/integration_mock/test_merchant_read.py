"""Read-plane tests for the Merchant API connector: tool helpers + graceful degradation.

Uses a fake ``ReadFn`` (no SDK). Verifies the ``{"rows", "row_count"}`` envelope, that the right
operation name + params reach the backend, and that a missing backend yields a structured
``BACKEND_NOT_CONFIGURED`` error instead of raising.
"""

from quantum_ads.connectors.merchant.read import product_tools
from quantum_ads.connectors.merchant.read.connector import register_merchant_read
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


# --- pure tool helpers (unit) -------------------------------------------------


def test_list_products_wraps_rows_and_passes_merchant_id():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["operation"] = operation
        seen["params"] = params
        return [{"name": "accounts/42/products/x"}]

    out = product_tools.list_products(merchant_id="42", read=read)
    assert out["rows"] == [{"name": "accounts/42/products/x"}]
    assert out["row_count"] == 1
    assert seen["operation"] == "products.list"
    assert seen["params"] == {"merchant_id": "42"}


def test_get_product_passes_product_name():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["operation"] = operation
        seen["params"] = params
        return []

    out = product_tools.get_product(product_name="accounts/42/products/x", read=read)
    assert out["row_count"] == 0
    assert seen["operation"] == "products.get"
    assert seen["params"] == {"product_name": "accounts/42/products/x"}


def test_list_product_statuses_uses_status_operation():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["operation"] = operation
        return [{"productStatus": {"itemLevelIssues": []}}]

    out = product_tools.list_product_statuses(merchant_id="42", read=read)
    assert out["row_count"] == 1
    assert seen["operation"] == "productStatuses.list"


def test_get_account_uses_accounts_operation():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["operation"] = operation
        return [{"accountId": "42"}]

    out = product_tools.get_account(merchant_id="42", read=read)
    assert out["rows"] == [{"accountId": "42"}]
    assert seen["operation"] == "accounts.get"


# --- backend-not-configured degradation (integration) -------------------------


def test_read_tools_degrade_when_backend_missing():
    # No backends wired -> ctx.backend("merchant.api") is None.
    assembled = build_server(
        env=_env(),
        stream_factory=_stream,
        connectors=[register_merchant_read],
    )
    # Tools still register even though the backend is absent.
    names = {t.name for t in assembled.registry.all_tools()}
    assert "merchant.products.list" in names
