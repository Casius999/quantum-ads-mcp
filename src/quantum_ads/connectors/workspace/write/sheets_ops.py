"""Pure operation builders for Google Workspace mutations (Sheets writes + Slides deck create).

Each builder returns a list with a single entity-tagged op dict. The ``entity``/``action`` keys
let the SDK mutate boundary dispatch to the right Workspace call (sheets.values.update /
sheets.spreadsheets.create / slides.presentations.create); the remaining keys carry the target id
+ body fields. These are pure and unit-tested directly (no SDK needed).
"""

from __future__ import annotations


def build_write_range_ops(
    spreadsheet_id: str, range_a1: str, values: list[object]
) -> list[dict[str, object]]:
    """Build the op to write ``values`` into an A1 range of a spreadsheet (values.update)."""
    op: dict[str, object] = {
        "entity": "sheet_range",
        "action": "write_range",
        "spreadsheet_id": spreadsheet_id,
        "range_a1": range_a1,
        "values": list(values),
    }
    return [op]


def build_create_spreadsheet_ops(title: str) -> list[dict[str, object]]:
    """Build the op to create a new spreadsheet with the given title (spreadsheets.create)."""
    op: dict[str, object] = {
        "entity": "spreadsheet",
        "action": "create",
        "title": title,
    }
    return [op]


def build_create_deck_ops(title: str) -> list[dict[str, object]]:
    """Build the op to create a new Slides deck with the given title (presentations.create)."""
    op: dict[str, object] = {
        "entity": "presentation",
        "action": "create",
        "title": title,
    }
    return [op]
