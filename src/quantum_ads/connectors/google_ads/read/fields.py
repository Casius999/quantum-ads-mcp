"""Field catalogs: curated 2026 deltas + a version-cached GoogleAdsFieldService facade."""

from __future__ import annotations

from collections.abc import Callable

from ..catalogs.v24_deltas import (
    NEW_METRIC_FAMILIES_2026,
    NEW_SEGMENT_FAMILIES_2026,
    NEW_VIEWS_2026,
    REMOVED_FIELDS_2026,
)

FieldFetcher = Callable[[str], dict[str, object]]


def list_v24_new_views() -> list[str]:
    return list(NEW_VIEWS_2026)


def field_deltas_2026() -> dict[str, object]:
    return {
        "new_views": list(NEW_VIEWS_2026),
        "new_metric_families": list(NEW_METRIC_FAMILIES_2026),
        "new_segment_families": list(NEW_SEGMENT_FAMILIES_2026),
        "removed_fields": list(REMOVED_FIELDS_2026),
    }


class FieldCatalog:
    """Caches GoogleAdsFieldService lookups per (version, field). Fetcher is injected/testable."""

    def __init__(self, fetcher: FieldFetcher):
        self._fetcher = fetcher
        self._cache: dict[tuple[str, str], dict[str, object]] = {}

    def describe_field(self, version: str, name: str) -> dict[str, object]:
        key = (version, name)
        if key not in self._cache:
            self._cache[key] = self._fetcher(name)
        return self._cache[key]
