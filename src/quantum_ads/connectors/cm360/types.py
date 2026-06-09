"""Shared type aliases for the Campaign Manager 360 connector.

The read plane talks to a generic ``ReadFn`` backend (keyed ``"cm360.api"``): the first argument
names the resource/operation (``userProfiles.list`` / ``campaigns.list`` / ``placements.list`` /
``reports.list`` / ``reports.run`` / ``floodlightActivities.list``) and the second carries the
profile id plus any per-operation params. This mirrors the DV360 / Merchant ``ReadFn`` boundary —
resource-oriented rather than query-oriented, because the dfareporting API is a set of REST
resources rather than a single query language.

The write plane talks to a ``MutateFn`` (keyed ``"cm360.mutate"``) where ``account_id`` carries
the CM360 user profile id (every placement patch and report insert is scoped to that profile).
"""

from __future__ import annotations

from collections.abc import Callable

# (operation, params) -> rows. operation names the resource; params carry the profile id + args.
ReadFn = Callable[[str, dict[str, object]], list[dict[str, object]]]
