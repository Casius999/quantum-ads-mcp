"""Google Workspace read connector: registration, read_only flags, request builders, degradation.

All fakes — the real googleapiclient (Drive v3 / Sheets v4) SDK is never imported. Verifies the
``{"rows", "row_count"}`` envelope, the right operation name + params reach the backend, and a
missing backend yields a structured ``BACKEND_NOT_CONFIGURED`` error.
"""

from quantum_ads.connectors.workspace import register_workspace
from quantum_ads.connectors.workspace.read import list_tools as tools_mod
from quantum_ads.connectors.workspace.read.connector import register_workspace_read
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
    return [{"operation": operation, "params": params}]


def _fake_mutate(
    account_id: str, operations: list[dict[str, object]], validate_only: bool
) -> dict[str, object]:
    return {"validate_only": validate_only}


def _backends() -> dict[str, object]:
    return {"workspace.api": _fake_read, "workspace.mutate": _fake_mutate}


# --- registration via register_workspace (full connector) -----------------------------------


def test_workspace_read_tools_registered():
    from quantum_ads.server import build_server

    assembled = build_server(
        env=_env(),
        stream_factory=_stream,
        backends=_backends(),
        connectors=[register_workspace],
    )
    names = {t.name for t in assembled.registry.all_tools()}
    assert "workspace.drive.list_files" in names
    assert "workspace.sheets.read_range" in names
    assert "workspace.sheets.get_metadata" in names


def test_workspace_read_tools_are_read_only():
    from quantum_ads.server import build_server

    assembled = build_server(
        env=_env(),
        stream_factory=_stream,
        backends=_backends(),
        connectors=[register_workspace],
    )
    for name in (
        "workspace.drive.list_files",
        "workspace.sheets.read_range",
        "workspace.sheets.get_metadata",
    ):
        assert assembled.registry.describe_tool(name).read_only is True


def test_register_workspace_read_alone_registers_only_read_tools():
    from quantum_ads.server import build_server

    assembled = build_server(
        env=_env(),
        stream_factory=_stream,
        backends=_backends(),
        connectors=[register_workspace_read],
    )
    names = {t.name for t in assembled.registry.all_tools()}
    assert "workspace.drive.list_files" in names
    assert "workspace.sheets.write_range" not in names


# --- pure request builders (unit) -----------------------------------------------------------


def test_build_drive_list_params_shape():
    params = tools_mod.build_drive_list_params("mimeType='application/vnd.google-apps.spreadsheet'")
    assert params == {"query": "mimeType='application/vnd.google-apps.spreadsheet'"}


def test_build_drive_list_params_defaults_empty_query():
    assert tools_mod.build_drive_list_params() == {"query": ""}


def test_build_read_range_params_shape():
    params = tools_mod.build_read_range_params("sheet-123", "Sheet1!A1:D10")
    assert params == {"spreadsheet_id": "sheet-123", "range_a1": "Sheet1!A1:D10"}


def test_build_metadata_params_shape():
    assert tools_mod.build_metadata_params("sheet-123") == {"spreadsheet_id": "sheet-123"}


# --- tool helpers against the fake ReadFn ---------------------------------------------------


def test_list_files_wraps_rows_and_passes_query():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["operation"] = operation
        seen["params"] = params
        return [{"id": "f1", "name": "Q2 report"}]

    out = tools_mod.list_files(query="name contains 'report'", read=read)
    assert out["rows"] == [{"id": "f1", "name": "Q2 report"}]
    assert out["row_count"] == 1
    assert seen["operation"] == "drive.files.list"
    assert seen["params"] == {"query": "name contains 'report'"}


def test_list_files_defaults_empty_query():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["params"] = params
        return []

    out = tools_mod.list_files(read=read)
    assert out["row_count"] == 0
    assert seen["params"] == {"query": ""}


def test_read_range_passes_spreadsheet_and_range():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["operation"] = operation
        seen["params"] = params
        return [{"range": "Sheet1!A1:B2", "values": [["a", "b"]]}]

    out = tools_mod.read_range(spreadsheet_id="sheet-9", range_a1="Sheet1!A1:B2", read=read)
    assert out["row_count"] == 1
    assert seen["operation"] == "sheets.values.get"
    assert seen["params"] == {"spreadsheet_id": "sheet-9", "range_a1": "Sheet1!A1:B2"}


def test_get_metadata_passes_spreadsheet_id():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["operation"] = operation
        seen["params"] = params
        return [{"spreadsheetId": "sheet-9", "properties": {"title": "Budget"}}]

    out = tools_mod.get_metadata(spreadsheet_id="sheet-9", read=read)
    assert out["rows"][0]["spreadsheetId"] == "sheet-9"
    assert seen["operation"] == "sheets.spreadsheets.get"
    assert seen["params"] == {"spreadsheet_id": "sheet-9"}


# --- backend-not-configured degradation (integration) ---------------------------------------


def test_read_tools_degrade_when_backend_missing():
    from quantum_ads.server import build_server

    # No backends wired -> ctx.backend("workspace.api") is None.
    assembled = build_server(
        env=_env(),
        stream_factory=_stream,
        connectors=[register_workspace_read],
    )
    names = {t.name for t in assembled.registry.all_tools()}
    assert "workspace.drive.list_files" in names
