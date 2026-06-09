"""Google Business Profile connector: local listings, reviews, and performance.

Public entry point: :func:`register_gbp` mounts both the read and write tool planes.
The read plane wraps the v1 API family (Account Management / Business Information /
Business Profile Performance) plus the allowlist-gated legacy v4 reviews host; the guarded
write plane covers review replies and location updates.
"""

from __future__ import annotations

from .connector import register_gbp
from .read.connector import register_gbp_read
from .write.connector import register_gbp_write

__all__ = [
    "register_gbp",
    "register_gbp_read",
    "register_gbp_write",
]
