"""Shared type alias for the reCAPTCHA Enterprise connector read plane.

The read plane talks to a generic ``ReadFn`` backend (keyed ``"recaptcha.api"``): the first
argument names the operation and the second carries the project id / site key / token / params.
This mirrors the BigQuery resource-oriented boundary rather than the Google Ads query-oriented one,
because the reCAPTCHA surface here is a small set of named operations (list keys, create an
assessment) rather than a single query language.
"""

from __future__ import annotations

from collections.abc import Callable

# (operation, params) -> rows. operation names the API call; params carry project_id / token / etc.
ReadFn = Callable[[str, dict[str, object]], list[dict[str, object]]]
