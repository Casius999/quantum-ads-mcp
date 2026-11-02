"""Live: generic mutate, Search campaign builder, Keyword Planner, recommendations (v26).

Writes here are validate_only only — an automated run never creates or changes anything. The
account keeps a paused QA campaign ("QA-SMOKE quantum-ads ...") so update operations have a
real target; it never serves.
"""

from __future__ import annotations

import os

import pytest

from quantum_ads.core.versioning.version_manager import DEFAULT_API_VERSION

pytestmark = pytest.mark.live
_REQUIRED = (
    "GOOGLE_ADS_DEVELOPER_TOKEN",
    "GOOGLE_ADS_CLIENT_ID",
    "GOOGLE_ADS_CLIENT_SECRET",
    "GOOGLE_ADS_REFRESH_TOKEN",
)


def _creds() -> dict[str, object]:
    if any(not os.environ.get(k) for k in _REQUIRED):
        pytest.skip("Google Ads credentials not set")
    from quantum_ads.core.auth.secret_store import EnvSecretStore

    return EnvSecretStore(os.environ).get("default").to_google_ads_dict()


def _customer(creds: dict[str, object]) -> str:
    explicit = os.environ.get("GOOGLE_ADS_TEST_CUSTOMER_ID")
    if explicit:
        return "".join(c for c in explicit if c.isdigit())
    from google.ads.googleads.client import GoogleAdsClient

    client = GoogleAdsClient.load_from_dict(creds, version=DEFAULT_API_VERSION)
    names = client.get_service("CustomerService").list_accessible_customers().resource_names
    return names[0].split("/")[-1]


def test_search_campaign_builder_validates_live() -> None:
    from quantum_ads.connectors.google_ads.sdk import default_mutate_factory
    from quantum_ads.connectors.google_ads.write.operations import build_search_campaign

    creds = _creds()
    cid = _customer(creds)
    ops = build_search_campaign(
        customer_id=cid,
        name="QA validate-only (never created)",
        daily_budget_micros=1_000_000,
        final_url="https://www.example.com",
        keywords=["chaussures running"],
        headlines=["Chaussures Running", "Livraison Offerte", "Nouvelle Collection"],
        descriptions=["Les meilleures chaussures.", "Retours gratuits sous 30 jours."],
        geo_target_ids=["2250"],
        language_ids=["1002"],
    )
    batch: dict[str, object] = {"entity": "mutate", "operations": ops}
    out = default_mutate_factory(creds, DEFAULT_API_VERSION)(cid, [batch], True)
    assert out["validate_only"] is True


def test_generic_mutate_validates_on_the_qa_campaign_live() -> None:
    from quantum_ads.connectors.google_ads.sdk import (
        default_mutate_factory,
        default_stream_factory,
    )

    creds = _creds()
    cid = _customer(creds)
    rows = default_stream_factory(creds, DEFAULT_API_VERSION)(
        cid, "SELECT campaign.id FROM campaign WHERE campaign.name LIKE 'QA-SMOKE%' LIMIT 1"
    )
    if not rows:
        pytest.skip("no QA-SMOKE campaign in this account")
    campaign = f"customers/{cid}/campaigns/{rows[0]['campaign']['id']}"
    operation = {
        "campaign_criterion_operation": {
            "create": {
                "campaign": campaign,
                "negative": True,
                "keyword": {"text": "qa validate only", "match_type": "PHRASE"},
            }
        }
    }
    batch: dict[str, object] = {"entity": "mutate", "operations": [operation]}
    out = default_mutate_factory(creds, DEFAULT_API_VERSION)(cid, [batch], True)
    assert out["validate_only"] is True


def test_keyword_ideas_live() -> None:
    from quantum_ads.connectors.google_ads.sdk import default_services_factory

    creds = _creds()
    rows = default_services_factory(creds, DEFAULT_API_VERSION)(
        "keyword_ideas",
        {
            "customer_id": _customer(creds),
            "keywords": ["chaussures running"],
            "language_id": "1002",
            "geo_target_ids": ["2250"],
            "limit": 5,
        },
    )
    assert rows and rows[0]["avg_monthly_searches"] >= 0


def test_recommendations_query_runs_live() -> None:
    from quantum_ads.connectors.google_ads.read.planning import build_recommendations_query
    from quantum_ads.connectors.google_ads.sdk import default_stream_factory

    creds = _creds()
    rows = default_stream_factory(creds, DEFAULT_API_VERSION)(
        _customer(creds), build_recommendations_query(limit=5)
    )
    assert isinstance(rows, list)
