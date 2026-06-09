"""Google Workspace connector: agency ops surface (Sheets + Drive + Slides).

Public entry point: :func:`register_workspace` mounts both the read and write tool planes.
The read plane wraps Drive v3 (file listing) and Sheets v4 (range + spreadsheet metadata);
the guarded write plane covers Sheets range writes / spreadsheet creation and Slides deck
creation — the building blocks for reporting exports, shared files, and decks.
"""

from __future__ import annotations

from .connector import register_workspace
from .read.connector import register_workspace_read
from .write.connector import register_workspace_write

__all__ = [
    "register_workspace",
    "register_workspace_read",
    "register_workspace_write",
]
