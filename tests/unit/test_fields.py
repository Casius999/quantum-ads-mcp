from quantum_ads.connectors.google_ads.read.fields import (
    FieldCatalog,
    field_deltas_2026,
    list_v24_new_views,
)


def test_new_views_include_2026_additions():
    views = list_v24_new_views()
    assert "per_store_view" in views
    assert "matched_location_interest_view" in views


def test_field_deltas_has_all_sections():
    deltas = field_deltas_2026()
    assert set(deltas) == {
        "new_views",
        "new_metric_families",
        "new_segment_families",
        "removed_fields",
    }


def test_field_catalog_caches_per_version_field():
    calls = {"n": 0}

    def fetcher(name: str) -> dict[str, object]:
        calls["n"] += 1
        return {"name": name, "selectable": True}

    catalog = FieldCatalog(fetcher)
    catalog.describe_field("v24", "campaign.id")
    catalog.describe_field("v24", "campaign.id")
    assert calls["n"] == 1  # second call served from cache
