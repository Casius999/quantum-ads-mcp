"""Shared type aliases for the Google Workspace connector.

The read plane talks to a generic ``ReadFn`` backend (keyed ``"workspace.api"``): the first
argument names the operation and the second carries the params. This mirrors the Search Console
/ Merchant ``ReadFn`` boundary — resource/operation-oriented rather than query-oriented, because
Workspace spans three small REST surfaces (Drive files.list, Sheets values.get,
Sheets spreadsheets.get) rather than a single query language.
"""

from __future__ import annotations

from collections.abc import Callable

# (operation, params) -> rows. operation names the call; params carry the args.
ReadFn = Callable[[str, dict[str, object]], list[dict[str, object]]]
