"""Merchant API connector (Google Merchant Center, successor to Content API for Shopping).

Public entry point: :func:`register_merchant` mounts both the read and write tool planes.

Content API for Shopping sunsets 2026-08-18; this connector targets the Merchant API (v1).
"""

from __future__ import annotations

from .connector import register_merchant

__all__ = ["register_merchant"]
