"""Live conformance for the Merchant API connector (run with `pytest -m live`).

accounts.get + products.list (reads) and an insert `validate_only` preview (no product is created).
Needs a broad-scope OAuth token with the `content` scope in GOOGLE_OAUTH_*, GOOGLE_CLOUD_PROJECT
(quota project where merchantapi.googleapis.com is enabled), and a Merchant Center account id in
GOOGLE_MERCHANT_ID (defaults to the project owner's account).
"""

import os

import pytest

pytestmark = pytest.mark.live

_REQ = ("GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_OAUTH_CLIENT_SECRET", "GOOGLE_OAUTH_REFRESH_TOKEN")
_DEFAULT_MERCHANT_ID = "5616979184"


def _creds() -> dict[str, object]:
    proj = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if any(not os.environ.get(k) for k in _REQ) or not proj:
        pytest.skip("broad OAuth creds or GOOGLE_CLOUD_PROJECT missing")
    return {
        "client_id": os.environ["GOOGLE_OAUTH_CLIENT_ID"],
        "client_secret": os.environ["GOOGLE_OAUTH_CLIENT_SECRET"],
        "refresh_token": os.environ["GOOGLE_OAUTH_REFRESH_TOKEN"],
        "quota_project_id": proj,
    }


def _merchant_id() -> str:
    return os.environ.get("GOOGLE_MERCHANT_ID", _DEFAULT_MERCHANT_ID)


def _read():
    from quantum_ads.connectors.merchant.sdk import default_read_factory

    return default_read_factory(_creds(), "v1")


def test_merchant_accounts_get_live():
    rows = _read()("accounts.get", {"merchant_id": _merchant_id()})
    assert rows and "name" in rows[0]


def test_merchant_products_list_live():
    rows = _read()("products.list", {"merchant_id": _merchant_id()})
    assert isinstance(rows, list)


def test_merchant_product_insert_validate_only_live():
    from quantum_ads.connectors.merchant.sdk import default_mutate_factory

    ops: list[dict[str, object]] = [
        {"action": "insert", "product_input": {"offerId": "qa_smoke", "contentLanguage": "fr"}}
    ]
    out = default_mutate_factory(_creds(), "v1")(_merchant_id(), ops, True)  # preview only
    assert out["validate_only"] is True
