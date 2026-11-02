"""Optional write policy: guardrails an operator can put around an autonomous agent.

The agent decides and applies; the policy only bounds what it may do. With no policy file there
are no limits. ``QUANTUM_ADS_POLICY_FILE`` holds JSON with a ``default`` section and optional
per-tenant overrides (a tenant section is merged over ``default``)::

    {"default": {"forbidden_ops": ["*.delete"], "max_amount_micros": 500000000,
                 "allowed_hours_utc": [7, 22], "max_operations_per_call": 200,
                 "max_writes_per_day": 500},
     "tenants": {"acme": {"max_amount_micros": 2000000000}}}

Checks run before any API call: operation allow/deny lists (glob patterns), any ``*amount_micros``
value anywhere in the operations, operations per call, UTC hours, and writes per tenant per day.
"""

from __future__ import annotations

import datetime as dt
import fnmatch
import json
import threading
from collections.abc import Mapping
from dataclasses import dataclass, field, fields, replace
from pathlib import Path


def _amounts(value: object) -> list[int]:
    found: list[int] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key).endswith("amount_micros") and isinstance(item, int | float):
                found.append(int(item))
            else:
                found.extend(_amounts(item))
    elif isinstance(value, list | tuple):
        for item in value:
            found.extend(_amounts(item))
    return found


@dataclass(frozen=True)
class WritePolicy:
    forbidden_ops: tuple[str, ...] = ()
    allowed_ops: tuple[str, ...] = ()
    max_amount_micros: int | None = None
    max_operations_per_call: int | None = None
    allowed_hours_utc: tuple[int, int] | None = None
    max_writes_per_day: int | None = None
    _counts: dict[tuple[str, str], int] = field(default_factory=dict, compare=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, compare=False, repr=False)

    def check(
        self,
        *,
        op: str,
        operations: list[dict[str, object]],
        tenant: str,
        now: dt.datetime | None = None,
    ) -> str | None:
        """The reason this write is refused, or None if the policy allows it."""
        if any(fnmatch.fnmatchcase(op, pattern) for pattern in self.forbidden_ops):
            return f"operation {op!r} is forbidden by policy"
        if self.allowed_ops and not any(fnmatch.fnmatchcase(op, p) for p in self.allowed_ops):
            return f"operation {op!r} is not in the policy allowlist"
        if (
            self.max_operations_per_call is not None
            and len(operations) > self.max_operations_per_call
        ):
            return (
                f"{len(operations)} operations exceed the limit of {self.max_operations_per_call}"
            )
        if self.max_amount_micros is not None:
            over = [a for a in _amounts(operations) if a > self.max_amount_micros]
            if over:
                return f"amount {max(over)} micros exceeds the cap of {self.max_amount_micros}"
        moment = now or dt.datetime.now(dt.UTC)
        if self.allowed_hours_utc is not None:
            start, end = self.allowed_hours_utc
            if not start <= moment.hour < end:
                return f"writes are allowed {start:02d}:00-{end:02d}:00 UTC only"
        if self.max_writes_per_day is not None:
            key = (tenant, moment.date().isoformat())
            with self._lock:
                if self._counts.get(key, 0) >= self.max_writes_per_day:
                    return f"daily write quota of {self.max_writes_per_day} reached"
        return None

    def record_write(self, tenant: str, now: dt.datetime | None = None) -> None:
        if self.max_writes_per_day is None:
            return
        key = (tenant, (now or dt.datetime.now(dt.UTC)).date().isoformat())
        with self._lock:
            self._counts[key] = self._counts.get(key, 0) + 1


_KEYS = {f.name for f in fields(WritePolicy) if not f.name.startswith("_")}


def _section(raw: object, where: str) -> dict[str, object]:
    if not isinstance(raw, dict):
        raise ValueError(f"{where}: expected an object")
    unknown = set(raw) - _KEYS
    if unknown:
        raise ValueError(f"{where}: unknown policy keys {sorted(unknown)}; allowed {sorted(_KEYS)}")
    out: dict[str, object] = {}
    for key, value in raw.items():
        out[key] = tuple(value) if isinstance(value, list) else value
    return out


@dataclass(frozen=True)
class PolicySet:
    default: WritePolicy
    tenants: dict[str, WritePolicy]

    def for_tenant(self, tenant: str) -> WritePolicy:
        return self.tenants.get(tenant, self.default)


def load_policy(env: Mapping[str, str]) -> PolicySet | None:
    path = env.get("QUANTUM_ADS_POLICY_FILE")
    if not path:
        return None
    raw = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: expected an object with 'default' and/or 'tenants'")
    base = _section(raw.get("default", {}), f"{path}: default")
    default = WritePolicy(**base)  # type: ignore[arg-type]
    tenants = {
        tenant: replace(default, **_section(section, f"{path}: tenant {tenant!r}"))  # type: ignore[arg-type]
        for tenant, section in (raw.get("tenants") or {}).items()
    }
    # replace() shares the counter dict with the default; give each tenant its own state.
    tenants = {t: replace(p, _counts={}, _lock=threading.Lock()) for t, p in tenants.items()}
    return PolicySet(default=default, tenants=tenants)
