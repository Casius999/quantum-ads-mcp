"""Ads Data Hub (ADH) connector: privacy-safe aggregated measurement over Google ad-event data.

Public entry point: :func:`register_adh` mounts both the read and write tool planes. The read plane
wraps the Ads Data Hub API (``adsdatahub`` v1): ``customers.list`` + ``analysisQueries.list``
listing, ``analysisQueries.start`` (run a stored analysis query -> operation/job ref), and
``operations.get`` (poll a job). The guarded write plane covers stored analysis-query creation
(``analysisQueries.create``).

ADH enforces privacy checks (aggregation thresholds + difference checks) on the server: results are
aggregated, privacy-filtered, and never row-level. This connector submits, lists, and polls — it
does not and cannot bypass ADH's privacy layer.

``register_adh`` is the single entrypoint; the sub-registrars are re-exported for callers that want
to mount one plane in isolation (tests).
"""

from __future__ import annotations

from .connector import register_adh
from .read.connector import register_adh_read
from .write.connector import register_adh_write

__all__ = ["register_adh", "register_adh_read", "register_adh_write"]
