"""Raw Looker read execution + result wrapping for the read connector.

Each tool calls the injected ``ReadFn`` with an operation name and a params dict, then wraps the
rows in the shared ``{"rows", "row_count"}`` envelope, matching the other read connectors.

The pure ``build_*`` param builders below assemble the params dicts (run a saved look, run an
inline model/view query) and are unit-tested directly with no SDK.
"""

from __future__ import annotations

from .types import ReadFn

# Operation names passed as the first ReadFn argument.
OP_DASHBOARDS_LIST = "dashboards.list"
OP_LOOKS_LIST = "looks.list"
OP_LOOK_RUN = "look.run"
OP_QUERY_RUN = "query.run"

# Default serialization format for ``look.run`` (Looker supports json/csv/txt/...).
DEFAULT_RESULT_FORMAT = "json"


def build_look_run_params(
    look_id: str, result_format: str = DEFAULT_RESULT_FORMAT
) -> dict[str, object]:
    """Build the params for running a saved look by id in a given result format."""
    params: dict[str, object] = {"look_id": look_id, "result_format": result_format}
    return params


def build_query_run_params(
    model: str, view: str, fields: list[str], filters: dict[str, object]
) -> dict[str, object]:
    """Build the params for running an inline model/view query.

    ``fields`` and ``filters`` are copied defensively so the caller's collections are never mutated.
    """
    params: dict[str, object] = {
        "model": model,
        "view": view,
        "fields": list(fields),
        "filters": dict(filters),
    }
    return params


def _wrap(rows: list[dict[str, object]]) -> dict[str, object]:
    """Wrap rows in the shared read envelope."""
    return {"rows": rows, "row_count": len(rows)}


def list_dashboards(*, read: ReadFn) -> dict[str, object]:
    """Tool: list dashboards on the Looker instance."""
    params: dict[str, object] = {}
    return _wrap(read(OP_DASHBOARDS_LIST, params))


def list_looks(*, read: ReadFn) -> dict[str, object]:
    """Tool: list saved looks on the Looker instance."""
    params: dict[str, object] = {}
    return _wrap(read(OP_LOOKS_LIST, params))


def run_look(
    *, look_id: str, read: ReadFn, result_format: str = DEFAULT_RESULT_FORMAT
) -> dict[str, object]:
    """Tool: run a saved look by id and wrap the resulting rows."""
    return _wrap(read(OP_LOOK_RUN, build_look_run_params(look_id, result_format)))


def run_query(
    *, model: str, view: str, fields: list[str], filters: dict[str, object], read: ReadFn
) -> dict[str, object]:
    """Tool: run an inline model/view query and wrap the resulting rows."""
    return _wrap(read(OP_QUERY_RUN, build_query_run_params(model, view, fields, filters)))
