"""Live: the Performance Max builder is accepted by the real API (validate_only, nothing created)."""

from __future__ import annotations

import base64
import os
import struct
import zlib

import pytest

from quantum_ads.core.versioning.version_manager import DEFAULT_API_VERSION

pytestmark = pytest.mark.live


def _png(width: int, height: int, rgb: tuple[int, int, int]) -> str:
    raw = b"".join(b"\x00" + bytes(rgb) * width for _ in range(height))

    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        return struct.pack(">I", len(data)) + tag + data + crc

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    body = chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")
    return base64.b64encode(b"\x89PNG\r\n\x1a\n" + body).decode()


def test_pmax_builder_validates_live() -> None:
    required = ("GOOGLE_ADS_DEVELOPER_TOKEN", "GOOGLE_ADS_REFRESH_TOKEN")
    if any(not os.environ.get(k) for k in required):
        pytest.skip("Google Ads credentials not set")
    from google.ads.googleads.client import GoogleAdsClient

    from quantum_ads.connectors.google_ads.sdk import default_mutate_factory
    from quantum_ads.connectors.google_ads.write.pmax import build_pmax_campaign
    from quantum_ads.core.auth.secret_store import EnvSecretStore

    creds = EnvSecretStore(os.environ).get("default").to_google_ads_dict()
    client = GoogleAdsClient.load_from_dict(creds, version=DEFAULT_API_VERSION)
    names = client.get_service("CustomerService").list_accessible_customers().resource_names
    cid = os.environ.get("GOOGLE_ADS_TEST_CUSTOMER_ID") or names[0].split("/")[-1]
    ops = build_pmax_campaign(
        customer_id=cid,
        name="QA pmax validate-only (never created)",
        daily_budget_micros=5_000_000,
        final_url="https://www.example.com",
        business_name="Example Shop",
        headlines=["Chaussures Running", "Livraison Offerte", "Nouvelle Collection"],
        long_headlines=["Les meilleures chaussures de running pour tous les coureurs"],
        descriptions=["Retours gratuits sous 30 jours.", "Des modeles pour chaque foulee."],
        logo_base64=_png(1200, 1200, (20, 60, 200)),
        images=[
            {"field_type": "MARKETING_IMAGE", "data_base64": _png(1200, 628, (200, 40, 40))},
            {
                "field_type": "SQUARE_MARKETING_IMAGE",
                "data_base64": _png(1200, 1200, (40, 160, 60)),
            },
        ],
        geo_target_ids=["2250"],
        language_ids=["1002"],
    )
    batch: dict[str, object] = {"entity": "mutate", "operations": ops}
    assert default_mutate_factory(creds, DEFAULT_API_VERSION)(cid, [batch], True)["validate_only"]
