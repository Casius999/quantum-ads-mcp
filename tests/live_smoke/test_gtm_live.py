"""Live conformance for the GTM connector (run with `pytest -m live`).

Read ops (list_accounts / list_containers) on the read-only scope + a validate_only mutate preview
(no tag/version is created — the preview short-circuits before any API call). Needs a broad-scope
OAuth token with tagmanager.readonly in GOOGLE_OAUTH_*.
"""

import os

import pytest

pytestmark = pytest.mark.live

_REQ = ("GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_OAUTH_CLIENT_SECRET", "GOOGLE_OAUTH_REFRESH_TOKEN")


def _creds() -> dict[str, object]:
    if any(not os.environ.get(k) for k in _REQ):
        pytest.skip("broad OAuth creds missing")
    return {
        "client_id": os.environ["GOOGLE_OAUTH_CLIENT_ID"],
        "client_secret": os.environ["GOOGLE_OAUTH_CLIENT_SECRET"],
        "refresh_token": os.environ["GOOGLE_OAUTH_REFRESH_TOKEN"],
        "quota_project_id": os.environ.get("GOOGLE_CLOUD_PROJECT", ""),
    }


def _read():
    from quantum_ads.connectors.gtm.sdk import default_read_factory

    return default_read_factory(_creds(), "v2")


def test_gtm_list_accounts_live():
    accounts = _read()("list_accounts", {})
    assert isinstance(accounts, list)


def test_gtm_list_containers_live():
    read = _read()
    accounts = read("list_accounts", {})
    if not accounts:
        pytest.skip("no GTM account on this token")
    path = str(accounts[0].get("path") or f"accounts/{accounts[0].get('accountId')}")
    containers = read("list_containers", {"parent": path})
    assert isinstance(containers, list)


def test_gtm_create_tag_validate_only_live():
    from quantum_ads.connectors.gtm.sdk import default_mutate_factory

    parent = "accounts/0/containers/0/workspaces/0"
    ops: list[dict[str, object]] = [
        {"action": "create_tag", "tag_name": "qa_smoke", "tag_type": "html"}
    ]
    out = default_mutate_factory(_creds(), "v2")(parent, ops, True)  # preview only
    assert out["validate_only"] is True
