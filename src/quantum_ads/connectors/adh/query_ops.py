"""Pure operation builder for Ads Data Hub (ADH) stored-query creation (unit-tested directly).

Returns a list with a single ``entity``-tagged op dict; the ``MutateFn`` backend dispatches on
``entity`` and the concrete ADH ``customers.analysisQueries.create`` translation lives in
``adh.sdk`` (live boundary). ``account_id`` (the ADH ``customer_id``) is threaded by the
WriteExecutor, so the op carries only the query definition (``title`` + ``query_text``).

Creating a stored analysis query does not run it (no data is read at create time) and does not
affect ADH's privacy enforcement: any later run of the query is still subject to ADH's aggregation
thresholds + difference checks server-side.

These are pure and unit-tested directly (no SDK needed).
"""

from __future__ import annotations

# Entity name passed inside each op dict (the MutateFn dispatches on it).
ENTITY_ANALYSIS_QUERY = "analysis_query"


def build_create_query_ops(title: str, query_text: str) -> list[dict[str, object]]:
    """Build the op to create a stored ADH analysis query.

    ``title`` is the human-readable query name; ``query_text`` is the SQL body of the analysis
    query. This builder only shapes the dict; it does not validate or parse the SQL. The op is a
    create only — it does not start a run.
    """
    op: dict[str, object] = {
        "entity": ENTITY_ANALYSIS_QUERY,
        "action": "create",
        "title": title,
        "query_text": query_text,
    }
    return [op]
