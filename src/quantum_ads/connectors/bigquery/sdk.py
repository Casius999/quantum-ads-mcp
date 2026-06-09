"""Real BigQuery SDK glue: read (ReadFn) + write (MutateFn) factories.

Live boundary — smoke-gated, not unit-tested. Isolated at the untyped third-party boundary
(``google.cloud.*`` is already in the mypy ignore list + this module is coverage-omitted via the
live gate). Imports are local so importing this module stays cheap and credential-free; the OAuth
credentials are derived from the shared Google creds dict. SDK-derived values stay implicitly
typed (``Any``) — they are never annotated, mirroring the Google Ads SDK boundary.

Targets **google-cloud-bigquery** (imports ``google.cloud.bigquery``). On-demand analysis pricing
is ``$6.25 / TiB`` (June 2026); the run path enforces a ``maximum_bytes_billed`` ceiling so a
mis-sized scan aborts server-side and is billed nothing.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

ReadFn = Callable[[str, dict[str, object]], list[dict[str, object]]]
MutateFn = Callable[[str, list[dict[str, object]], bool], dict[str, object]]

# OAuth scope for the BigQuery surface (read + DDL both ride the same scope; the read-only guard
# lives in the SafetyMode spine, not in the token).
_SCOPES = ["https://www.googleapis.com/auth/bigquery"]


def _oauth_credentials(creds: dict[str, object]) -> Any:
    from google.oauth2.credentials import Credentials

    return Credentials(
        token=None,
        refresh_token=str(creds["refresh_token"]),
        client_id=str(creds["client_id"]),
        client_secret=str(creds["client_secret"]),
        token_uri="https://oauth2.googleapis.com/token",
        scopes=_SCOPES,
    )


def default_read_factory(creds: dict[str, object], version: str) -> ReadFn:
    """Build an operation-dispatching ReadFn over the BigQuery client."""
    from google.cloud import bigquery

    client = bigquery.Client(
        project=str(creds.get("project_id")) or None,
        credentials=_oauth_credentials(creds),
    )

    def _datasets_list(params: dict[str, object]) -> list[dict[str, object]]:
        project = str(params["project_id"])
        return [
            {
                "dataset_id": ds.dataset_id,
                "project": ds.project,
                "full_dataset_id": ds.full_dataset_id,
            }
            for ds in client.list_datasets(project=project)
        ]

    def _tables_list(params: dict[str, object]) -> list[dict[str, object]]:
        project = str(params["project_id"])
        dataset = str(params["dataset_id"])
        ref = bigquery.DatasetReference(project, dataset)
        return [
            {"table_id": t.table_id, "dataset_id": t.dataset_id, "table_type": t.table_type}
            for t in client.list_tables(ref)
        ]

    def _query_dry_run(params: dict[str, object]) -> list[dict[str, object]]:
        config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
        job = client.query(str(params["sql"]), job_config=config)
        return [{"total_bytes_processed": int(job.total_bytes_processed or 0)}]

    def _query_run(params: dict[str, object]) -> list[dict[str, object]]:
        config = bigquery.QueryJobConfig(
            maximum_bytes_billed=int(params["max_bytes_billed"]),
        )
        job = client.query(str(params["sql"]), job_config=config)
        return [dict(row.items()) for row in job.result()]

    handlers: dict[str, Callable[[dict[str, object]], list[dict[str, object]]]] = {
        "datasets.list": _datasets_list,
        "tables.list": _tables_list,
        "query.dry_run": _query_dry_run,
        "query.run": _query_run,
    }

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        handler = handlers.get(operation)
        if handler is None:
            raise ValueError(f"unsupported bigquery read operation: {operation!r}")
        return handler(params)

    return read


def default_mutate_factory(creds: dict[str, object], version: str) -> MutateFn:
    """Build an op-dispatching MutateFn over the BigQuery client (dataset / table DDL).

    ``validate_only`` short-circuits to a synthetic preview because BigQuery's create calls do not
    expose a server-side validate-only flag; the guarded preview still surfaces the exact op dicts
    that would be applied before the confirm step. ``account_id`` carries the GCP project id.
    """
    from google.cloud import bigquery

    client = bigquery.Client(
        project=str(creds.get("project_id")) or None,
        credentials=_oauth_credentials(creds),
    )

    def _create_dataset(account_id: str, op: dict[str, object]) -> dict[str, object]:
        project = str(op["project_id"])
        dataset = bigquery.Dataset(f"{project}.{op['dataset_id']}")
        created = client.create_dataset(dataset)
        return {"dataset_id": created.dataset_id, "project": created.project}

    def _create_table(account_id: str, op: dict[str, object]) -> dict[str, object]:
        project = str(op["project_id"])
        ref = bigquery.DatasetReference(project, str(op["dataset_id"])).table(str(op["table_id"]))
        raw_schema = op["schema"] if isinstance(op["schema"], list) else []
        schema = [
            bigquery.SchemaField(
                str(field["name"]),
                str(field.get("type", "STRING")),
                mode=str(field.get("mode", "NULLABLE")),
            )
            for field in raw_schema
        ]
        table = bigquery.Table(ref, schema=schema)
        created = client.create_table(table)
        return {"table_id": created.table_id, "dataset_id": created.dataset_id}

    handlers: dict[str, Callable[[str, dict[str, object]], dict[str, object]]] = {
        "dataset": _create_dataset,
        "table": _create_table,
    }

    def mutate(
        account_id: str, operations: list[dict[str, object]], validate_only: bool
    ) -> dict[str, object]:
        if validate_only:
            return {"validate_only": True, "preview": operations}
        results: list[dict[str, object]] = []
        for op in operations:
            handler = handlers.get(str(op["entity"]))
            if handler is None:
                raise ValueError(f"unsupported bigquery mutate entity: {op.get('entity')!r}")
            results.append(handler(account_id, op))
        return {"validate_only": False, "results": results}

    return mutate
