"""Live: every field the server's generated GAQL selects is *selectable* per GoogleAdsFieldService.

The offline conformance test proves the fields exist in the protos; it cannot tell that a nested
message's sub-fields are not selectable (recommendation.impact.* is a real example). This asks the
API itself, for the pinned version.
"""

from __future__ import annotations

import os
import re

import pytest

from quantum_ads.core.versioning.version_manager import DEFAULT_API_VERSION

pytestmark = pytest.mark.live
_SELECT = re.compile(r"SELECT\s+(.*?)\s+FROM\s", re.IGNORECASE | re.DOTALL)


def test_generated_gaql_fields_are_selectable_live() -> None:
    if not os.environ.get("GOOGLE_ADS_DEVELOPER_TOKEN"):
        pytest.skip("no Google Ads developer token")
    import importlib.util
    from pathlib import Path

    from google.ads.googleads.client import GoogleAdsClient

    from quantum_ads.core.auth.secret_store import EnvSecretStore

    source = Path(__file__).parents[1] / "integration_mock" / "test_gaql_field_conformance.py"
    spec = importlib.util.spec_from_file_location("_gaql_conformance", source)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _generated_queries = module._generated_queries

    selected: set[str] = set()
    for query in _generated_queries():
        match = _SELECT.search(query)
        assert match, query
        selected |= {field.strip() for field in match.group(1).split(",")}
    client = GoogleAdsClient.load_from_dict(
        EnvSecretStore(os.environ).get("default").to_google_ads_dict(), version=DEFAULT_API_VERSION
    )
    names = ", ".join(f"'{name}'" for name in sorted(selected))
    rows = client.get_service("GoogleAdsFieldService").search_google_ads_fields(
        query=f"SELECT name, selectable WHERE name IN ({names})"
    )
    selectable = {row.name for row in rows if row.selectable}
    assert selected - selectable == set()
