"""Live conformance for the GA4 connector (run with `pytest -m live`).

Needs a broad-scope OAuth token (analytics.readonly/edit) in GOOGLE_OAUTH_* — see
scripts/get_refresh_token.py. Reads + a validate_only mutate (the SDK short-circuits the
create to a preview, so nothing is created). Auto-discovers a property under the known accounts.
"""

import os

import pytest

pytestmark = pytest.mark.live

_REQ = ("GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_OAUTH_CLIENT_SECRET", "GOOGLE_OAUTH_REFRESH_TOKEN")
_KNOWN_ACCOUNTS = ["351346324", "351346325"]


def _creds() -> dict[str, object]:
    if any(not os.environ.get(k) for k in _REQ):
        pytest.skip("broad OAuth creds missing (run scripts/get_refresh_token.py)")
    return {
        "client_id": os.environ["GOOGLE_OAUTH_CLIENT_ID"],
        "client_secret": os.environ["GOOGLE_OAUTH_CLIENT_SECRET"],
        "refresh_token": os.environ["GOOGLE_OAUTH_REFRESH_TOKEN"],
        "quota_project_id": os.environ.get("GOOGLE_CLOUD_PROJECT", ""),
    }


def _accounts() -> list[str]:
    extra = [a.strip() for a in (os.environ.get("GA4_ACCOUNT_ID") or "").split(",") if a.strip()]
    return extra + _KNOWN_ACCOUNTS


def _find_property(creds: dict[str, object]) -> str | None:
    from quantum_ads.connectors.ga4.sdk import admin_read_factory

    admin = admin_read_factory(creds, "v1beta")
    for acc in _accounts():
        props = admin("listProperties", {"account_id": acc})
        if props:
            return str(props[0].get("name", "")).split("/")[-1]
    return None


def test_ga4_admin_list_properties_live():
    from quantum_ads.connectors.ga4.sdk import admin_read_factory

    admin = admin_read_factory(_creds(), "v1beta")
    found = any(admin("listProperties", {"account_id": a}) for a in _accounts())
    assert found, "no GA4 property under the known accounts"


def test_ga4_run_report_live():
    creds = _creds()
    pid = _find_property(creds)
    if not pid:
        pytest.skip("no GA4 property available")
    from quantum_ads.connectors.ga4.sdk import data_read_factory

    rows = data_read_factory(creds, "v1beta")(
        "runReport",
        {
            "property_id": pid,
            "dimensions": ["date"],
            "metrics": ["activeUsers"],
            "start_date": "7daysAgo",
            "end_date": "today",
        },
    )
    assert isinstance(rows, list)


def test_ga4_admin_streams_and_key_events_live():
    creds = _creds()
    pid = _find_property(creds)
    if not pid:
        pytest.skip("no GA4 property available")
    from quantum_ads.connectors.ga4.sdk import admin_read_factory

    admin = admin_read_factory(creds, "v1beta")
    assert isinstance(admin("listDataStreams", {"property_id": pid}), list)
    assert isinstance(admin("listKeyEvents", {"property_id": pid}), list)


def test_ga4_create_key_event_validate_only_live():
    creds = _creds()
    pid = _find_property(creds)
    if not pid:
        pytest.skip("no GA4 property available")
    from quantum_ads.connectors.ga4.sdk import admin_mutate_factory

    ops: list[dict[str, object]] = [
        {"entity": "key_event", "property_id": pid, "event_name": "qa_smoke_event"}
    ]
    out = admin_mutate_factory(creds, "v1beta")(pid, ops, True)  # preview only, never created
    assert out["validate_only"] is True
