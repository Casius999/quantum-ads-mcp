"""BigQuery connector registrar: mounts the read + guarded write planes in one call.

Read backend is keyed ``"bigquery.api"`` (a ``ReadFn``); write backend ``"bigquery.mutate"`` (a
``MutateFn`` whose ``account_id`` carries the GCP project id). Both degrade gracefully: when a
backend is not wired the tools return a structured ``*_NOT_CONFIGURED`` error rather than raising.

Cost safety: ``bigquery.query.dry_run`` is always available and returns estimated scanned bytes +
USD cost; ``bigquery.query.run`` only runs under an explicit ``max_bytes_billed`` ceiling. Dataset
and table creation are guarded mutations (validate_only preview -> confirm token -> signed audit).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from fastmcp import FastMCP

from ...core.context import ServerContext
from ...core.mcp.register import add_tool
from ...core.registry.registry import Capability, ToolSpec
from ...core.safety.write_executor import MutateFn, WriteExecutor
from . import read_tools
from .read_tools import DEFAULT_MAX_BYTES_BILLED
from .types import ReadFn
from .write_ops import build_create_dataset_ops, build_create_table_ops

READ_BACKEND_KEY = "bigquery.api"
WRITE_BACKEND_KEY = "bigquery.mutate"

_READ_NOT_CONFIGURED: dict[str, object] = {
    "error": {"code": "BACKEND_NOT_CONFIGURED", "message": f"{READ_BACKEND_KEY} not wired"}
}
_WRITE_NOT_CONFIGURED: dict[str, object] = {
    "error": {"code": "MUTATE_NOT_CONFIGURED", "message": f"{WRITE_BACKEND_KEY} not wired"}
}


def register_bigquery(app: FastMCP, ctx: ServerContext) -> None:
    """Mount the full BigQuery connector (read + guarded write) onto the FastMCP app."""
    _register_read(app, ctx)
    _register_write(app, ctx)


def _register_read(app: FastMCP, ctx: ServerContext) -> None:
    def read_backend() -> ReadFn | None:
        backend = ctx.backend(READ_BACKEND_KEY)
        if backend is None:
            return None
        return cast(ReadFn, backend)

    def bigquery_datasets_list(project_id: str) -> dict[str, object]:
        read = read_backend()
        if read is None:
            return dict(_READ_NOT_CONFIGURED)
        return read_tools.list_datasets(project_id=project_id, read=read)

    def bigquery_tables_list(project_id: str, dataset_id: str) -> dict[str, object]:
        read = read_backend()
        if read is None:
            return dict(_READ_NOT_CONFIGURED)
        return read_tools.list_tables(project_id=project_id, dataset_id=dataset_id, read=read)

    def bigquery_query_dry_run(project_id: str, sql: str) -> dict[str, object]:
        read = read_backend()
        if read is None:
            return dict(_READ_NOT_CONFIGURED)
        return read_tools.dry_run_query(project_id=project_id, sql=sql, read=read)

    def bigquery_query_run(
        project_id: str, sql: str, max_bytes_billed: int = DEFAULT_MAX_BYTES_BILLED
    ) -> dict[str, object]:
        read = read_backend()
        if read is None:
            return dict(_READ_NOT_CONFIGURED)
        return read_tools.run_query(
            project_id=project_id, sql=sql, read=read, max_bytes_billed=max_bytes_billed
        )

    tools: list[tuple[str, str, Callable[..., Any]]] = [
        (
            "bigquery.datasets.list",
            "List datasets in a BigQuery project.",
            bigquery_datasets_list,
        ),
        (
            "bigquery.tables.list",
            "List tables in a BigQuery dataset.",
            bigquery_tables_list,
        ),
        (
            "bigquery.query.dry_run",
            "Dry-run a query: estimate scanned bytes + USD cost ($6.25/TiB), billing nothing.",
            bigquery_query_dry_run,
        ),
        (
            "bigquery.query.run",
            "Run a query only if it scans under max_bytes_billed (default 1e9 bytes).",
            bigquery_query_run,
        ),
    ]
    for name, description, fn in tools:
        add_tool(app, name, description, fn)

    ctx.registry.register(
        Capability(
            connector="bigquery",
            domain="read",
            tools=[ToolSpec(name=name, summary=description) for name, description, _ in tools],
        )
    )


def _register_write(app: FastMCP, ctx: ServerContext) -> None:
    holder: dict[str, WriteExecutor] = {}

    def executor() -> WriteExecutor | None:
        backend = ctx.backend(WRITE_BACKEND_KEY)
        if backend is None:
            return None
        if "ex" not in holder:
            holder["ex"] = WriteExecutor(cast(MutateFn, backend), ctx.safety, ctx.audit)
        return holder["ex"]

    def bigquery_dataset_create(
        project_id: str, dataset_id: str, confirm: str | None = None
    ) -> dict[str, object]:
        ex = executor()
        if ex is None:
            return dict(_WRITE_NOT_CONFIGURED)
        return ex.execute(
            op="bigquery.dataset.create",
            customer_id=project_id,
            operations=build_create_dataset_ops(project_id, dataset_id),
            confirm=confirm,
        )

    def bigquery_table_create(
        project_id: str,
        dataset_id: str,
        table_id: str,
        schema: list[dict[str, object]],
        confirm: str | None = None,
    ) -> dict[str, object]:
        ex = executor()
        if ex is None:
            return dict(_WRITE_NOT_CONFIGURED)
        return ex.execute(
            op="bigquery.table.create",
            customer_id=project_id,
            operations=build_create_table_ops(project_id, dataset_id, table_id, schema),
            confirm=confirm,
        )

    tools: list[tuple[str, str, Callable[..., Any]]] = [
        (
            "bigquery.dataset.create",
            "Create a dataset under a project (guarded: validate_only preview + confirm token).",
            bigquery_dataset_create,
        ),
        (
            "bigquery.table.create",
            "Create a table with a schema under a dataset (guarded).",
            bigquery_table_create,
        ),
    ]
    for name, description, fn in tools:
        add_tool(app, name, description, fn)

    ctx.registry.register(
        Capability(
            connector="bigquery",
            domain="write",
            tools=[
                ToolSpec(name=name, summary=description, read_only=False)
                for name, description, _ in tools
            ],
        )
    )
