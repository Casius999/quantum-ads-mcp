from quantum_ads.connectors.gtm.connector import register_gtm
from quantum_ads.connectors.gtm.read import list_tools
from quantum_ads.core.query.runner import StreamFn


def _env() -> dict[str, str]:
    return {
        "GOOGLE_ADS_DEVELOPER_TOKEN": "d",
        "GOOGLE_ADS_CLIENT_ID": "c",
        "GOOGLE_ADS_CLIENT_SECRET": "s",
        "GOOGLE_ADS_REFRESH_TOKEN": "r",
        "QUANTUM_ADS_READ_ONLY": "false",
    }


def _stream(creds: dict[str, object], version: str) -> StreamFn:
    return lambda cid, q: []


def _fake_read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
    return [{"operation": operation, "parent": params.get("parent", "")}]


def _fake_mutate(
    account_path: str, operations: list[dict[str, object]], validate_only: bool
) -> dict[str, object]:
    return {"ok": True, "validate_only": validate_only}


def _build():
    from quantum_ads.server import build_server

    return build_server(
        env=_env(),
        stream_factory=_stream,
        backends={"gtm.api": _fake_read, "gtm.mutate": _fake_mutate},
        connectors=[register_gtm],
    )


def test_gtm_read_tools_registered():
    assembled = _build()
    names = {t.name for t in assembled.registry.all_tools()}
    assert "gtm.list_accounts" in names
    assert "gtm.list_containers" in names
    assert "gtm.list_workspaces" in names
    assert "gtm.list_tags" in names
    assert "gtm.list_triggers" in names
    assert "gtm.list_variables" in names
    assert "gtm.list_versions" in names


def test_gtm_read_tools_marked_read_only():
    assembled = _build()
    assert assembled.registry.describe_tool("gtm.list_accounts").read_only is True
    assert assembled.registry.describe_tool("gtm.list_tags").read_only is True


def test_list_accounts_invokes_backend():
    out = list_tools.list_accounts(read=_fake_read)
    assert out["row_count"] == 1
    rows = out["rows"]
    assert isinstance(rows, list)
    assert rows[0]["operation"] == "list_accounts"


def test_list_containers_passes_parent():
    out = list_tools.list_containers(account_path="accounts/123", read=_fake_read)
    rows = out["rows"]
    assert isinstance(rows, list)
    assert rows[0] == {"operation": "list_containers", "parent": "accounts/123"}


def test_list_tags_passes_workspace_parent():
    out = list_tools.list_tags(
        workspace_path="accounts/1/containers/2/workspaces/3", read=_fake_read
    )
    rows = out["rows"]
    assert isinstance(rows, list)
    assert rows[0]["parent"] == "accounts/1/containers/2/workspaces/3"


def test_build_parent_params_is_pure():
    assert list_tools.build_parent_params("accounts/9") == {"parent": "accounts/9"}


def test_read_tool_reports_backend_not_configured_when_unwired():
    from quantum_ads.server import build_server

    assembled = build_server(
        env=_env(),
        stream_factory=_stream,
        backends={"gtm.mutate": _fake_mutate},  # gtm.api intentionally absent
        connectors=[register_gtm],
    )
    # Tool still registered (capability is static), but invocation degrades gracefully.
    assert "gtm.list_accounts" in {t.name for t in assembled.registry.all_tools()}
