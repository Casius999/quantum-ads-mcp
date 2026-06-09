"""Exhaustive live conformance for every Google Ads connector tool (run with `pytest -m live`).

Reads + a `validate_only` mutate (dry run, never applied). Standard reports must succeed; feature-
dependent views (PMax, AI Max) and change history must at least return a structured dict (no crash).
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
    if any(not os.environ.get(k) for k in _REQUIRED):
        pytest.skip("live Google Ads creds missing")
    from quantum_ads.core.auth.secret_store import EnvSecretStore

    return EnvSecretStore(os.environ).get("default").to_google_ads_dict()


def _customer_id(creds: dict[str, object]) -> str:
    explicit = os.environ.get("GOOGLE_ADS_TEST_CUSTOMER_ID")
    if explicit:
        return "".join(c for c in explicit if c.isdigit())
    from google.ads.googleads.client import GoogleAdsClient

    client = GoogleAdsClient.load_from_dict(creds, version="v24")
    names = client.get_service("CustomerService").list_accessible_customers().resource_names
    return names[0].split("/")[-1]


def _stream(creds: dict[str, object]):
    from quantum_ads.connectors.google_ads.sdk import default_stream_factory

    return default_stream_factory(creds, "v24")


def test_standard_reports_succeed_live():
    from quantum_ads.connectors.google_ads.read.report_tools import (
        report_campaign,
        report_conversions,
        report_search_terms,
    )

    creds = _creds()
    cid, stream = _customer_id(creds), _stream(_creds())
    for report in (report_campaign, report_search_terms, report_conversions):
        out = report(customer_id=cid, stream=stream)
        assert "error" not in out, (report.__name__, out.get("error"))
        assert "rows" in out


def test_feature_dependent_reports_return_dict_live():
    from quantum_ads.connectors.google_ads.read.report_tools import (
        report_ai_max,
        report_pmax_asset_groups,
    )

    creds = _creds()
    cid, stream = _customer_id(creds), _stream(_creds())
    for report in (report_pmax_asset_groups, report_ai_max):
        out = report(customer_id=cid, stream=stream)
        assert isinstance(out, dict)  # rows OR a structured error (account may lack the feature)
        assert "rows" in out or "error" in out


def test_change_history_audit_and_delta_live():
    from quantum_ads.connectors.google_ads.read.change_history import change_history

    creds = _creds()
    cid, stream = _customer_id(creds), _stream(_creds())
    for mode in ("audit", "delta"):
        out = change_history(customer_id=cid, mode=mode, stream=stream)
        assert isinstance(out, dict)
        assert "rows" in out or "error" in out


def test_campaign_set_status_validate_only_live():
    # SAFE: validate_only=True is a dry run — never applied.
    from quantum_ads.connectors.google_ads.sdk import default_mutate_factory
    from quantum_ads.core.query.runner import run_report

    creds = _creds()
    cid, stream = _customer_id(creds), _stream(_creds())
    rows = run_report(
        cid,
        "SELECT campaign.id FROM campaign WHERE campaign.status != 'REMOVED' LIMIT 1",
        stream=stream,
    )
    if not rows:
        pytest.skip("no campaign available to validate against")
    ops: list[dict[str, object]] = [
        {
            "entity": "campaign",
            "action": "update",
            "campaign_id": str(rows[0]["campaign.id"]),
            "status": "PAUSED",
        }
    ]
    result = default_mutate_factory(creds, "v24")(cid, ops, True)  # validate_only -> never applied
    assert result is not None
