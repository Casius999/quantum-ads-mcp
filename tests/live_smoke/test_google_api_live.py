"""Live: the generic Google API plane on real APIs with the broad OAuth token.

- reads on several APIs through google.api.read;
- a reversible write cycle on a permanent QA draft GTM workspace (never published):
  rename -> rollback (name restored from the signed audit);
- the preview refusing a delete the token holds no scope for, before anything is written;
- a GA4 Admin create in confirm mode: previewed against the contract, never applied.
"""

from __future__ import annotations

import asyncio
import os

import pytest
from fastmcp import Client

from quantum_ads.backends import build_backends
from quantum_ads.connectors.googleapi import register_google_api
from quantum_ads.server import build_server

pytestmark = pytest.mark.live
QA_WORKSPACE = "QA-SMOKE quantum-ads google.api"


def _no_stream(creds: dict[str, object], version: str):  # type: ignore[no-untyped-def]
    raise AssertionError("google.api never streams GAQL")


def _app(write_mode: str):  # type: ignore[no-untyped-def]
    if not os.environ.get("GOOGLE_ADS_REFRESH_TOKEN"):
        pytest.skip("Google OAuth credentials not set")
    env = {
        **os.environ,
        "QUANTUM_ADS_READ_ONLY": "false",
        "QUANTUM_ADS_WRITE_MODE": write_mode,
        "QUANTUM_ADS_AUDIT_DIR": "",
    }
    return build_server(
        env=env,
        stream_factory=_no_stream,
        connectors=[register_google_api],
        backends=build_backends(env),
    ).app


def _run(app, *calls: tuple[str, dict[str, object]]) -> list[dict[str, object]]:  # type: ignore[no-untyped-def]
    async def scenario() -> list[dict[str, object]]:
        out = []
        async with Client(app, timeout=300) as client:
            for name, args in calls:
                result = await client.call_tool(name, args, raise_on_error=False)
                assert isinstance(result.structured_content, dict), result
                out.append(result.structured_content)
        return out

    return asyncio.run(scenario())


def test_reads_across_apis_live() -> None:
    results = _run(
        _app("auto"),
        ("google.api.read", {"api": "tagmanager", "method": "accounts.list"}),
        (
            "google.api.read",
            {"api": "analyticsadmin", "method": "accountSummaries.list", "params": {"pageSize": 5}},
        ),
        ("google.api.read", {"api": "searchconsole", "method": "sites.list"}),
        (
            "google.api.read",
            {"api": "youtube", "method": "channels.list", "params": {"part": ["id"], "mine": True}},
        ),
    )
    assert all("response" in r for r in results), results


def _gtm_container(app) -> str:  # type: ignore[no-untyped-def]
    (accounts,) = _run(app, ("google.api.read", {"api": "tagmanager", "method": "accounts.list"}))
    for account in accounts.get("response", {}).get("account", []):  # type: ignore[union-attr]
        (containers,) = _run(
            app,
            (
                "google.api.read",
                {
                    "api": "tagmanager",
                    "method": "accounts.containers.list",
                    "params": {"parent": account["path"]},
                },
            ),
        )
        for container in containers.get("response", {}).get("container", []):  # type: ignore[union-attr]
            return str(container["path"])
    pytest.skip("no GTM container visible to this token")


def _qa_workspace(app, container: str) -> str:  # type: ignore[no-untyped-def]
    """The permanent QA draft workspace (like the paused QA campaign): found, or created once."""
    (listed,) = _run(
        app,
        (
            "google.api.read",
            {
                "api": "tagmanager",
                "method": "accounts.containers.workspaces.list",
                "params": {"parent": container},
            },
        ),
    )
    for workspace in listed["response"].get("workspace", []):  # type: ignore[union-attr]
        if str(workspace["name"]).startswith(QA_WORKSPACE):
            return str(workspace["path"])
    (created,) = _run(
        app,
        (
            "google.api.call",
            {
                "api": "tagmanager",
                "method": "accounts.containers.workspaces.create",
                "params": {"parent": container},
                "body": {"name": QA_WORKSPACE, "description": "QA draft, never published"},
            },
        ),
    )
    assert created["applied"] is True, created
    return str(created["result"]["results"][0]["path"])  # type: ignore[index]


def test_gtm_workspace_write_rollback_cycle_live() -> None:
    """A draft workspace is never published, so nothing reaches the live site."""
    app = _app("auto")
    path = _qa_workspace(app, _gtm_container(app))
    (start,) = _run(
        app,
        (
            "google.api.read",
            {
                "api": "tagmanager",
                "method": "accounts.containers.workspaces.get",
                "params": {"path": path},
            },
        ),
    )
    original = start["response"]["name"]  # type: ignore[index]
    renamed, rolled, after = _run(
        app,
        (
            "google.api.call",
            {
                "api": "tagmanager",
                "method": "accounts.containers.workspaces.update",
                "params": {"path": path},
                "body": {"name": QA_WORKSPACE + " (renamed by test)"},
            },
        ),
        ("google.api.rollback", {}),
        (
            "google.api.read",
            {
                "api": "tagmanager",
                "method": "accounts.containers.workspaces.get",
                "params": {"path": path},
            },
        ),
    )
    assert renamed["applied"] is True, renamed
    assert renamed["result"]["results"][0]["name"] == QA_WORKSPACE + " (renamed by test)"  # type: ignore[index]
    assert (
        rolled["rolled_back"]["op"]
        == "google.api.call:tagmanager.accounts.containers.workspaces.update"
    )  # type: ignore[index]
    assert after["response"]["name"] == original  # type: ignore[index]


def test_preview_refuses_a_call_the_token_has_no_scope_for_live() -> None:
    """tagmanager.delete.containers is not granted: the preview stops the delete before any write."""
    app = _app("confirm")
    path = _qa_workspace(app, _gtm_container(app))
    (refused,) = _run(
        app,
        (
            "google.api.call",
            {
                "api": "tagmanager",
                "method": "accounts.containers.workspaces.delete",
                "params": {"path": path},
                "allow_delete": True,
            },
        ),
    )
    assert refused["error"]["code"] == "VALIDATION_FAILED", refused  # type: ignore[index]
    assert "tagmanager.delete.containers" in refused["error"]["message"]  # type: ignore[index]


def test_ga4_admin_create_is_previewed_not_applied_live() -> None:
    app = _app("confirm")
    (summaries,) = _run(
        app,
        (
            "google.api.read",
            {"api": "analyticsadmin", "method": "accountSummaries.list", "params": {"pageSize": 5}},
        ),
    )
    properties = [
        p["property"]
        for account in summaries.get("response", {}).get("accountSummaries", [])  # type: ignore[union-attr]
        for p in account.get("propertySummaries", [])
    ]
    if not properties:
        pytest.skip("no GA4 property visible to this token")
    (preview,) = _run(
        app,
        (
            "google.api.call",
            {
                "api": "analyticsadmin",
                "method": "properties.customDimensions.create",
                "params": {"parent": properties[0]},
                "body": {"parameterName": "qa_smoke", "displayName": "QA smoke", "scope": "EVENT"},
            },
        ),
    )
    assert preview["applied"] is False and preview["confirm_token"], preview
    assert preview["preview"]["results"] == [  # type: ignore[index]
        {
            "method": "analyticsadmin.properties.customDimensions.create",
            "validated": "discovery contract",
        }
    ]
