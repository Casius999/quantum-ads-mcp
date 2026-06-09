"""Structured tool-call observability (SP8): record every tool invocation as a JSON line."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class CallRecord:
    tool: str
    tenant: str
    ok: bool
    duration_ms: int


class CallRecorder:
    """Collect structured call records and emit them as JSON lines via an optional sink."""

    def __init__(self, sink: Callable[[str], None] | None = None):
        self._sink = sink
        self.records: list[CallRecord] = []

    def record(self, *, tool: str, tenant: str, ok: bool, duration_ms: int) -> CallRecord:
        rec = CallRecord(tool=tool, tenant=tenant, ok=ok, duration_ms=duration_ms)
        self.records.append(rec)
        if self._sink is not None:
            self._sink(json.dumps(asdict(rec), separators=(",", ":")))
        return rec

    def summary(self) -> dict[str, int]:
        total = len(self.records)
        ok = sum(1 for r in self.records if r.ok)
        return {"total": total, "ok": ok, "failed": total - ok}
