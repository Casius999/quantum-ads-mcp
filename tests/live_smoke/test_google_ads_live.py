"""Live conformance smoke for the Google Ads connector (run with `pytest -m live`).

Requires real Google Ads OAuth creds in the environment (or a gitignored `.env`; see
docs/LIVE_VALIDATION.md). SAFE BY DESIGN: reads only, plus one mutation run with
`validate_only=True` (a dry run that is never applied). No budgets/statuses are changed.
"""

import os

import pytest

pytestmark = pytest.mark.live

_REQUIRED = (
    "GOOGLE_ADS_DEVELOPER_TOKEN",
    "GOOGLE_ADS_CLIENT_ID",
    "GOOGLE_ADS_CLIENT_SECRET",
    "GOOGLE_ADS_REFRESH_TOKEN",
)


def _creds() -> dict[str, object]:
    missing = [k for k in _REQUIRED if not os.environ.get(k)]
    if missing:
        pytest.skip(f"live Google Ads creds missing: {missing}")
    from quantum_ads.core.auth.secret_store import EnvSecretStore

    return EnvSecretStore(os.environ).get("default").to_google_ads_dict()


def _client(creds: dict[str, object]):
    from google.ads.googleads.client import GoogleAdsClient

    return GoogleAdsClient.load_from_dict(creds, version="v24")


def _first_customer_id(client) -> str:
    explicit = os.environ.get("GOOGLE_ADS_TEST_CUSTOMER_ID")
    if explicit:
        return "".join(ch for ch in explicit if ch.isdigit())
    names = client.get_service("CustomerService").list_accessible_customers().resource_names
    assert names, "no accessible customers"
    return names[0].split("/")[-1]


def test_list_accessible_customers_live():
    client = _client(_creds())
    names = client.get_service("CustomerService").list_accessible_customers().resource_names
    assert names  # at least one accessible account


def test_gaql_customer_read_live():
    creds = _creds()
    from quantum_ads.connectors.google_ads.read.gaql_tools import run_gaql
    from quantum_ads.connectors.google_ads.sdk import default_stream_factory

    cid = _first_customer_id(_client(creds))
    out = run_gaql(
        customer_id=cid,
        query="SELECT customer.id FROM customer",
        stream=default_stream_factory(creds, "v24"),
    )
    assert "error" not in out, out.get("error")
    assert out["row_count"] >= 1


def test_gaql_campaign_read_live():
    creds = _creds()
    from quantum_ads.connectors.google_ads.read.gaql_tools import run_gaql
    from quantum_ads.connectors.google_ads.sdk import default_stream_factory

    cid = _first_customer_id(_client(creds))
    out = run_gaql(
        customer_id=cid,
        query=(
            "SELECT campaign.id, campaign.name, metrics.clicks "
            "FROM campaign WHERE segments.date DURING LAST_7_DAYS"
        ),
        stream=default_stream_factory(creds, "v24"),
    )
    assert "error" not in out, out.get("error")
    assert "rows" in out  # may be empty if the account has no campaigns


def test_budget_update_validate_only_live():
    # SAFE: validate_only=True is a dry run — never applied. Re-sets a budget to its CURRENT amount.
    creds = _creds()
    from quantum_ads.connectors.google_ads.sdk import (
        default_mutate_factory,
        default_stream_factory,
    )
    from quantum_ads.core.query.runner import run_report

    cid = _first_customer_id(_client(creds))
    rows = run_report(
        cid,
        "SELECT campaign_budget.id, campaign_budget.amount_micros FROM campaign_budget LIMIT 1",
        stream=default_stream_factory(creds, "v24"),
    )
    if not rows:
        pytest.skip("no campaign budget available to validate against")
    ops: list[dict[str, object]] = [
        {
            "entity": "campaign_budget",
            "action": "update",
            "budget_id": str(rows[0]["campaign_budget.id"]),
            "amount_micros": int(rows[0]["campaign_budget.amount_micros"]),
        }
    ]
    result = default_mutate_factory(creds, "v24")(cid, ops, True)  # validate_only -> never applied
    assert result is not None
