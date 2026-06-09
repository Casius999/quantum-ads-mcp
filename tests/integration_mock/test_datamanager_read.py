"""Read-plane tests for the Data Manager connector: status tool + destinations + degradation.

Uses a fake ``ReadFn`` (no SDK). Verifies the dependency-free ``status`` tool, the
``{"rows", "row_count"}`` envelope for destinations.list, that the right operation name + params
reach the backend, and that a missing read backend yields a structured ``BACKEND_NOT_CONFIGURED``
error instead of raising.
"""

from quantum_ads.connectors.datamanager import register_datamanager
from quantum_ads.connectors.datamanager.read import status_tools
from quantum_ads.core.query.runner import StreamFn
from quantum_ads.server import build_server


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


# --- pure tool helpers (unit) -------------------------------------------------


def test_status_reports_data_manager_plane():
    out = status_tools.status()
    assert out["plane"] == "data-manager"
    assert isinstance(out["note"], str)
    assert "Data Manager" in out["note"]


def test_list_destinations_wraps_rows_and_passes_account_id():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["operation"] = operation
        seen["params"] = params
        return [{"name": "destinations/123"}]

    out = status_tools.list_destinations(account_id="acct-7", backend=read)
    assert out["rows"] == [{"name": "destinations/123"}]
    assert out["row_count"] == 1
    assert seen["operation"] == "destinations.list"
    assert seen["params"] == {"account_id": "acct-7"}


def test_list_destinations_degrades_when_backend_missing():
    out = status_tools.list_destinations(account_id="acct-7", backend=None)
    assert isinstance(out["error"], dict)
    assert out["error"]["code"] == "BACKEND_NOT_CONFIGURED"


# --- registration / degradation (integration) ---------------------------------


def test_read_tools_register_without_backend():
    # No backends wired -> destinations.list degrades, but both tools still register; status works.
    assembled = build_server(
        env=_env(),
        stream_factory=_stream,
        connectors=[register_datamanager],
    )
    names = {t.name for t in assembled.registry.all_tools()}
    assert "datamanager.status" in names
    assert "datamanager.destinations.list" in names
