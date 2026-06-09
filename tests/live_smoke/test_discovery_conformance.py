"""API-contract conformance for the discovery-based connectors (run with `pytest -m live`).

The account-free, credential-free proof that a connector's API surface is REAL: for every API a
connector targets, load Google's discovery document and assert that every method the connector's
sdk.py invokes actually exists in the contract. No OAuth token, no account, no cost.

Resolution order per API (most-accurate first):
  1. the discovery doc bundled inside google-api-python-client — this is the exact document the
     connector loads at runtime (offline, deterministic), so it is the truest conformance source;
  2. the public ``$discovery`` endpoint for APIs too new to be bundled.
Skips (never fails) only when neither source yields the document. A MISSING method id IS a failure —
it means the connector advertises an operation the API does not expose (this is how the non-existent
youtube ``videos.batchGetStats`` and the misrouted sa360 ``conversions.ingest`` were caught).
"""

import json
import os
import urllib.error
import urllib.request

import pytest

pytestmark = pytest.mark.live

# connector surface -> (api, version, method ids the connector's sdk.py actually calls)
_SURFACES: dict[str, tuple[str, str, list[str]]] = {
    "dv360": (
        "displayvideo",
        "v4",
        [
            "displayvideo.advertisers.list",
            "displayvideo.advertisers.campaigns.list",
            "displayvideo.advertisers.insertionOrders.list",
            "displayvideo.advertisers.lineItems.list",
            "displayvideo.advertisers.lineItems.patch",
        ],
    ),
    "cm360": (
        "dfareporting",
        "v4",
        [
            "dfareporting.userProfiles.list",
            "dfareporting.campaigns.list",
            "dfareporting.placements.list",
            "dfareporting.reports.list",
            "dfareporting.reports.run",
            "dfareporting.floodlightActivities.list",
            "dfareporting.placements.patch",
            "dfareporting.reports.insert",
        ],
    ),
    "sa360_reporting": (
        "searchads360",
        "v0",
        [
            "searchads360.customers.searchAds360.search",
            "searchads360.customers.listAccessibleCustomers",
        ],
    ),
    "sa360_conversions": (
        "doubleclicksearch",
        "v2",
        ["doubleclicksearch.conversion.insert"],
    ),
    "adh": (
        "adsdatahub",
        "v1",
        [
            "adsdatahub.customers.list",
            "adsdatahub.customers.analysisQueries.list",
            "adsdatahub.customers.analysisQueries.start",
            "adsdatahub.customers.analysisQueries.create",
            "adsdatahub.operations.get",
        ],
    ),
    "gtm": (
        "tagmanager",
        "v2",
        [
            "tagmanager.accounts.list",
            "tagmanager.accounts.containers.list",
            "tagmanager.accounts.containers.workspaces.list",
            "tagmanager.accounts.containers.workspaces.tags.list",
            "tagmanager.accounts.containers.workspaces.tags.create",
            "tagmanager.accounts.containers.versions.publish",
        ],
    ),
    "searchconsole_webmasters": (
        "webmasters",
        "v3",
        [
            "webmasters.searchanalytics.query",
            "webmasters.sites.list",
            "webmasters.sitemaps.list",
            "webmasters.sitemaps.submit",
        ],
    ),
    "searchconsole_inspection": (
        "searchconsole",
        "v1",
        ["searchconsole.urlInspection.index.inspect"],
    ),
    "youtube_data": (
        "youtube",
        "v3",
        [
            "youtube.channels.list",
            "youtube.videos.list",
            "youtube.playlistItems.list",
            "youtube.videos.update",
            "youtube.playlistItems.insert",
        ],
    ),
    "gbp_accounts": (
        "mybusinessaccountmanagement",
        "v1",
        ["mybusinessaccountmanagement.accounts.list"],
    ),
    "gbp_info": (
        "mybusinessbusinessinformation",
        "v1",
        [
            "mybusinessbusinessinformation.accounts.locations.list",
            "mybusinessbusinessinformation.locations.get",
            "mybusinessbusinessinformation.locations.patch",
        ],
    ),
    "gbp_performance": (
        "businessprofileperformance",
        "v1",
        ["businessprofileperformance.locations.fetchMultiDailyMetricsTimeSeries"],
    ),
}


def _bundled_doc(api: str, version: str) -> dict | None:
    try:
        import googleapiclient.discovery_cache as dc

        path = os.path.join(os.path.dirname(dc.__file__), "documents", f"{api}.{version}.json")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                return json.load(fh)
    except (OSError, ValueError, ImportError):
        return None
    return None


def _public_doc(api: str, version: str) -> dict | None:
    url = f"https://{api}.googleapis.com/$discovery/rest?version={version}"
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:  # noqa: S310 — fixed Google URLs
            return json.loads(resp.read())
    except (urllib.error.URLError, TimeoutError, ValueError):
        return None


def _collect_method_ids(node: dict, acc: set[str]) -> None:
    for method in (node.get("methods") or {}).values():
        if isinstance(method, dict) and "id" in method:
            acc.add(str(method["id"]))
    for resource in (node.get("resources") or {}).values():
        if isinstance(resource, dict):
            _collect_method_ids(resource, acc)


@pytest.mark.parametrize("name", list(_SURFACES))
def test_connector_methods_exist_in_discovery(name: str) -> None:
    api, version, expected = _SURFACES[name]
    doc = _bundled_doc(api, version) or _public_doc(api, version)
    if doc is None:
        pytest.skip(f"discovery doc for {api} {version} unavailable (not bundled + endpoint 404)")
    ids: set[str] = set()
    _collect_method_ids(doc, ids)
    assert ids, f"{name}: discovery doc had no methods (unexpected shape)"
    missing = [m for m in expected if m not in ids]
    assert not missing, f"{name}: methods absent from the live API contract: {missing}"
