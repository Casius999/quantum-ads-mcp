"""Which audited writes can still be rolled back.

A rollback is itself an audited write, recorded as ``<tool>.rollback:<index>`` where ``index`` is
the audit entry it undid. That makes rollbacks walk back through history: a rollback is never
the target of the next rollback, and an entry that was already undone is skipped.
"""

from __future__ import annotations

from collections.abc import Sequence

from .audit import AuditRecord

_ROLLBACK = ".rollback"


def rollback_op(tool: str, index: int) -> str:
    """The audit op of a rollback of entry ``index`` performed by ``tool`` (``ads.rollback``)."""
    return f"{tool}:{index}"


def _undone(op: str) -> int | None:
    name, _, index = op.partition(":")
    return int(index) if name.endswith(_ROLLBACK) and index.isdigit() else None


def reversible(
    records: Sequence[AuditRecord],
    *,
    prefix: str,
    tenant: str | None,
    audit_index: int | None = None,
) -> list[tuple[int, AuditRecord]]:
    """Entries under ``prefix`` that carry an inverse and were not rolled back yet, oldest first."""
    undone = {i for r in records if (i := _undone(r.op)) is not None}
    return [
        (index, record)
        for index, record in enumerate(records)
        if record.op.startswith(prefix)
        and not record.op.partition(":")[0].endswith(_ROLLBACK)
        and record.payload.get("inverse_operations")
        and index not in undone
        and (tenant is None or record.actor.split(":", 1)[0] == tenant)
        and (audit_index is None or index == audit_index)
    ]
