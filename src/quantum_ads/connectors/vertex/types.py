"""Shared type aliases for the Vertex AI generative connector.

The connector talks to a single generic ``ReadFn`` backend (keyed ``"vertex.api"``): the first
argument names the operation (``"gemini"`` / ``"imagen"`` / ``"veo"``) and the second carries the
request params. This mirrors the Search Console / Merchant ``ReadFn`` boundary —
resource/operation-oriented rather than query-oriented — except here the returned items are
generated artifacts (text rows, image refs, a video operation ref) rather than fetched records.
"""

from __future__ import annotations

from collections.abc import Callable

# (operation, params) -> generated items. operation names the modality; params carry the request.
ReadFn = Callable[[str, dict[str, object]], list[dict[str, object]]]
