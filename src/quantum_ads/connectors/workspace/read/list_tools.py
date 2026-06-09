"""Google Workspace read tools: Drive file listing + Sheets range read + spreadsheet metadata.

Pure request builders (``build_*``) construct the params dict handed to the injected backend
``ReadFn``; the thin tool wrappers do the result wrapping. The backend ReadFn signature is
``(operation, params) -> rows`` where operation is one of ``"drive.files.list"`` /
``"sheets.values.get"`` / ``"sheets.spreadsheets.get"``.

The ``{"rows", "row_count"}`` envelope matches the Search Console / Merchant read connectors.
"""

from __future__ import annotations

from ..types import ReadFn

# Operation names passed as the first ReadFn argument.
OP_DRIVE_LIST = "drive.files.list"
OP_SHEETS_READ_RANGE = "sheets.values.get"
OP_SHEETS_METADATA = "sheets.spreadsheets.get"


def build_drive_list_params(query: str = "") -> dict[str, object]:
    """Pure: wrap a Drive search query (``files.list`` ``q`` syntax) as backend params.

    An empty query lists all accessible files; a query such as
    ``"mimeType='application/vnd.google-apps.spreadsheet'"`` narrows to reporting sheets.
    """
    params: dict[str, object] = {"query": query}
    return params


def build_read_range_params(spreadsheet_id: str, range_a1: str) -> dict[str, object]:
    """Pure: wrap a spreadsheet id + A1 range (e.g. ``"Sheet1!A1:D10"``) as backend params."""
    params: dict[str, object] = {"spreadsheet_id": spreadsheet_id, "range_a1": range_a1}
    return params


def build_metadata_params(spreadsheet_id: str) -> dict[str, object]:
    """Pure: wrap a spreadsheet id as backend params for a spreadsheet-metadata fetch."""
    params: dict[str, object] = {"spreadsheet_id": spreadsheet_id}
    return params


def _wrap(rows: list[dict[str, object]]) -> dict[str, object]:
    """Wrap rows in the shared read envelope."""
    return {"rows": rows, "row_count": len(rows)}


def list_files(*, query: str = "", read: ReadFn) -> dict[str, object]:
    """Tool: list Drive files the authenticated user can access (optional ``q`` filter)."""
    return _wrap(read(OP_DRIVE_LIST, build_drive_list_params(query)))


def read_range(*, spreadsheet_id: str, range_a1: str, read: ReadFn) -> dict[str, object]:
    """Tool: read a cell range (A1 notation) from a spreadsheet."""
    return _wrap(read(OP_SHEETS_READ_RANGE, build_read_range_params(spreadsheet_id, range_a1)))


def get_metadata(*, spreadsheet_id: str, read: ReadFn) -> dict[str, object]:
    """Tool: fetch spreadsheet metadata (title, sheet tabs, grid sizes) for a spreadsheet."""
    return _wrap(read(OP_SHEETS_METADATA, build_metadata_params(spreadsheet_id)))
