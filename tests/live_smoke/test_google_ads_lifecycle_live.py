"""Live: Demand Gen + experiment builds (validate_only), a no-op batch job, Reach Planner."""

from __future__ import annotations

import base64
import os
import struct
import time
import zlib

import pytest

from quantum_ads.core.versioning.version_manager import DEFAULT_API_VERSION

pytestmark = pytest.mark.live
QA_NAME = "QA-SMOKE quantum-ads (PAUSED - ne pas activer)"


def _png(width: int, height: int, rgb: tuple[int, int, int]) -> str:
    raw = b"".join(b"\x00" + bytes(rgb) * width for _ in range(height))

    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        return struct.pack(">I", len(data)) + tag + data + crc

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    body = chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")
    return base64.b64encode(b"\x89PNG\r\n\x1a\n" + body).decode()


def _setup() -> tuple[dict[str, object], str]:
    if not os.environ.get("GOOGLE_ADS_DEVELOPER_TOKEN"):
        pytest.skip("Google Ads credentials not set")
    from google.ads.googleads.client import GoogleAdsClient

    from quantum_ads.core.auth.secret_store import EnvSecretStore

    creds = EnvSecretStore(os.environ).get("default").to_google_ads_dict()
    client = GoogleAdsClient.load_from_dict(creds, version=DEFAULT_API_VERSION)
    names = client.get_service("CustomerService").list_accessible_customers().resource_names
    return creds, os.environ.get("GOOGLE_ADS_TEST_CUSTOMER_ID") or names[0].split("/")[-1]


def _qa_campaign(creds: dict[str, object], cid: str) -> str:
    from quantum_ads.connectors.google_ads.sdk import default_stream_factory

    rows = default_stream_factory(creds, DEFAULT_API_VERSION)(
        cid, "SELECT campaign.id FROM campaign WHERE campaign.name LIKE 'QA-SMOKE%' LIMIT 1"
    )
    if not rows:
        pytest.skip("no QA-SMOKE campaign in this account")
    return str(rows[0]["campaign"]["id"])


def test_demand_gen_and_experiment_validate_live() -> None:
    from quantum_ads.connectors.google_ads.sdk import default_mutate_factory
    from quantum_ads.connectors.google_ads.write.lifecycle import (
        build_demand_gen_campaign,
        build_experiment,
    )

    creds, cid = _setup()
    mutate = default_mutate_factory(creds, DEFAULT_API_VERSION)
    demand_gen = build_demand_gen_campaign(
        customer_id=cid,
        name="QA demand gen validate-only",
        daily_budget_micros=5_000_000,
        final_url="https://www.example.com",
        business_name="Example Shop",
        headlines=["Chaussures Running"],
        descriptions=["Retours gratuits sous 30 jours."],
        logo_base64=_png(1200, 1200, (20, 60, 200)),
        marketing_images_base64=[_png(1200, 628, (200, 40, 40))],
        square_images_base64=[_png(1200, 1200, (40, 160, 60))],
        geo_target_ids=["2250"],
        language_ids=["1002"],
    )
    experiment = build_experiment(
        customer_id=cid,
        name="QA experiment validate-only",
        base_campaign_id=_qa_campaign(creds, cid),
    )
    for ops in (demand_gen, experiment):
        assert mutate(cid, [{"entity": "mutate", "operations": ops}], True)["validate_only"]


def test_noop_batch_job_runs_to_done_live() -> None:
    from quantum_ads.connectors.google_ads.sdk import (
        default_mutate_factory,
        default_services_factory,
    )

    creds, cid = _setup()
    campaign = f"customers/{cid}/campaigns/{_qa_campaign(creds, cid)}"
    same_name = {
        "campaign_operation": {
            "update": {"resource_name": campaign, "name": QA_NAME},
            "update_mask": "name",
        }
    }
    batch: dict[str, object] = {"entity": "batch_submit", "operations": [same_name]}
    submitted = default_mutate_factory(creds, DEFAULT_API_VERSION)(cid, [batch], False)
    job = submitted["results"][0]["batch_job"]  # type: ignore[index]
    status = default_services_factory(creds, DEFAULT_API_VERSION)
    for _ in range(36):
        row = status("batch_status", {"customer_id": cid, "batch_job": job})[0]
        if row.get("status") == "DONE":
            assert row["failed"] == 0
            return
        time.sleep(5)
    pytest.fail(f"batch job {job} not done after 3 minutes")


def test_reach_planner_live() -> None:
    from quantum_ads.connectors.google_ads.sdk import default_services_factory

    creds, _ = _setup()
    call = default_services_factory(creds, DEFAULT_API_VERSION)
    try:
        products = call("reach_products", {"location_id": "2250"})
    except Exception as exc:  # noqa: BLE001
        if "ACTION_NOT_PERMITTED" in str(exc) or "not enabled" in str(exc):
            pytest.skip("Reach Planner requires an allowlisted developer token")
        raise
    assert products
