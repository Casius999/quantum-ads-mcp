"""Structured tool-call observability: one JSON line per tool invocation, plus counters.

Records carry the tool name, tenant, outcome, error code, duration and trace id — never the
arguments or results, which may hold customer data. Counters feed ``health``; only the most
recent records are kept in memory so a long-running server does not grow without bound.
"""

from __future__ import annotations

import json
import threading
from collections import deque
from collections.abc import Callable
from dataclasses import asdict, dataclass

RECENT_RECORDS = 1000


@dataclass(frozen=True)
class CallRecord:
    tool: str
    tenant: str
    ok: bool
    duration_ms: int
    error_code: str | None = None
    trace_id: str | None = None


class CallRecorder:
    """Count calls and emit each as a JSON line via an optional sink."""

    def __init__(self, sink: Callable[[str], None] | None = None):
        self._sink = sink
        self.records: deque[CallRecord] = deque(maxlen=RECENT_RECORDS)
        self._total = 0
        self._ok = 0
        self._lock = threading.Lock()

    def record(
        self,
        *,
        tool: str,
        tenant: str,
        ok: bool,
        duration_ms: int,
        error_code: str | None = None,
        trace_id: str | None = None,
    ) -> CallRecord:
        rec = CallRecord(tool, tenant, ok, duration_ms, error_code, trace_id)
        with self._lock:
            self.records.append(rec)
            self._total += 1
            self._ok += int(ok)
        if self._sink is not None:
            self._sink(json.dumps(asdict(rec), separators=(",", ":")))
        return rec

    def summary(self) -> dict[str, int]:
        with self._lock:
            return {"total": self._total, "ok": self._ok, "failed": self._total - self._ok}
