"""Quota governance: token bucket + exponential backoff policy.

Per-API governors (Ads QPS, GTM 0.25 QPS, YouTube search 100/day, Search Console
2000/site/day) are configured by connectors using these primitives.
"""

from __future__ import annotations

from collections.abc import Callable


def backoff_seconds(attempt: int, base: int = 1, cap: int = 60) -> int:
    """Exponential backoff in seconds, capped (for RESOURCE_EXHAUSTED retries)."""
    return min(cap, base * (1 << attempt))


class TokenBucket:
    """Classic token bucket. ``now`` is injected for deterministic tests."""

    def __init__(self, capacity: int, refill_per_sec: float, now: Callable[[], float]):
        self.capacity = capacity
        self.refill = refill_per_sec
        self._tokens = float(capacity)
        self._now = now
        self._last = now()

    def try_acquire(self, n: int = 1) -> bool:
        current = self._now()
        self._tokens = min(self.capacity, self._tokens + (current - self._last) * self.refill)
        self._last = current
        if self._tokens >= n:
            self._tokens -= n
            return True
        return False
