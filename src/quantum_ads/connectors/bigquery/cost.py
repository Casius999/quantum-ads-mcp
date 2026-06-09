"""Pure BigQuery cost helpers — unit-tested directly, no SDK.

BigQuery on-demand analysis pricing (June 2026) is ``$6.25 per TiB`` scanned, where a TiB is
``2**40`` bytes. ``estimate_cost_usd`` converts a byte count (as returned by a dry-run's
``total_bytes_processed``) into an estimated USD cost so callers can decide before running.

Sanity check: ``estimate_cost_usd(2**40) == 6.25`` (exactly one TiB).
"""

from __future__ import annotations

# On-demand analysis price per TiB scanned (USD), June 2026.
USD_PER_TIB: float = 6.25
# Bytes in one TiB.
BYTES_PER_TIB: int = 2**40


def estimate_cost_usd(bytes_processed: int) -> float:
    """Estimate the on-demand query cost in USD for ``bytes_processed`` bytes scanned."""
    return bytes_processed / BYTES_PER_TIB * USD_PER_TIB
