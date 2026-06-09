"""Looker connector: the BI dashboards / reporting surface an ads agency runs on.

Public entry point: :func:`register_looker` mounts both the read and the guarded write tool planes
in one call (dashboards/looks listing, run a saved look, run an inline model/view query, and
guarded dashboard creation).

The read plane talks to a ``ReadFn`` backend keyed ``"looker.api"``; the guarded write plane to a
``MutateFn`` backend keyed ``"looker.mutate"`` (``account_id="looker"``). Both degrade gracefully:
when a backend is not wired the tools return a structured ``*_NOT_CONFIGURED`` error rather than
raising.
"""

from __future__ import annotations

from .connector import register_looker

__all__ = ["register_looker"]
