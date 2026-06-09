"""BigQuery connector: the measurement / data-warehouse surface agencies run on.

Public entry point: :func:`register_bigquery` mounts both the read and the guarded write tool
planes in one call (datasets/tables listing, dry-run + run query with cost safety, and guarded
dataset/table creation).

Cost safety is central: every byte-scanning read goes through a dry-run estimate first, and
``bigquery.query.run`` refuses to execute unless the scan is under an explicit ``max_bytes_billed``
ceiling. On-demand pricing is ``$6.25 / TiB`` (June 2026).
"""

from __future__ import annotations

from .connector import register_bigquery

__all__ = ["register_bigquery"]
