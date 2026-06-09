"""Shared type alias for the Cloud Translation + Natural Language connector.

The connector talks to a single generic ``ReadFn`` backend (keyed ``"language.api"``): the first
argument names the operation (``"translate"`` / ``"detect"`` / ``"sentiment"`` / ``"entities"`` /
``"batch_translate"``) and the second carries the request params. This mirrors the Vertex /
Search Console / Merchant ``ReadFn`` boundary — resource/operation-oriented rather than
query-oriented — except here the returned items are language-API results (translations, a detected
language, a sentiment score, extracted entities) rather than fetched account records.
"""

from __future__ import annotations

from collections.abc import Callable

# (operation, params) -> result items. operation names the call; params carry text / target / etc.
ReadFn = Callable[[str, dict[str, object]], list[dict[str, object]]]
