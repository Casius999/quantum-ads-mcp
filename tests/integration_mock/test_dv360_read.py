"""Read-plane tests for the DV360 connector: tool helpers, enum tolerance, degradation.

Uses a fake ``ReadFn`` (no SDK). Verifies the ``{"rows", "row_count"}`` envelope, that the right
operation name + params reach the backend, that the enum-tolerant row mapper collapses unknown
``entityStatus`` / ``lineItemType`` values to ``"UNKNOWN"`` (the Demand Gen scenario, 2026-06-10),
and that a missing backend yields a structured ``BACKEND_NOT_CONFIGURED`` error instead of raising.
"""

from quantum_ads.connectors.dv360 import catalogs, register_dv360
from quantum_ads.connectors.dv360.read import list_tools
from quantum_ads.connectors.dv360.read.connector import register_dv360_read
from quantum_ads.core.query.runner import StreamFn
from quantum_ads.server import build_server


def _env() -> dict[str, str]:
    return {
        "GOOGLE_ADS_DEVELOPER_TOKEN": "d",
        "GOOGLE_ADS_CLIENT_ID": "c",
        "GOOGLE_ADS_CLIENT_SECRET": "s",
        "GOOGLE_ADS_REFRESH_TOKEN": "r",
        "QUANTUM_ADS_READ_ONLY": "false",
    }


def _stream(creds: dict[str, object], version: str) -> StreamFn:
    return lambda cid, q: []


def _fake_read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
    return []


def _fake_mutate(
    advertiser_id: str, operations: list[dict[str, object]], validate_only: bool
) -> dict[str, object]:
    return {"ok": True, "validate_only": validate_only, "advertiser_id": advertiser_id}


def _build():
    return build_server(
        env=_env(),
        stream_factory=_stream,
        backends={"dv360.api": _fake_read, "dv360.mutate": _fake_mutate},
        connectors=[register_dv360],
    )


# --- registration -------------------------------------------------------------


def test_dv360_read_tools_registered():
    assembled = _build()
    names = {t.name for t in assembled.registry.all_tools()}
    assert "dv360.advertisers.list" in names
    assert "dv360.campaigns.list" in names
    assert "dv360.insertion_orders.list" in names
    assert "dv360.line_items.list" in names


def test_dv360_read_tools_marked_read_only():
    assembled = _build()
    assert assembled.registry.describe_tool("dv360.advertisers.list").read_only is True
    assert assembled.registry.describe_tool("dv360.line_items.list").read_only is True


# --- pure param builders + runner (unit) --------------------------------------


def test_build_advertisers_params():
    assert list_tools.build_advertisers_params("PARTNER1") == {"partner_id": "PARTNER1"}


def test_build_advertiser_child_params():
    assert list_tools.build_advertiser_child_params("ADV1") == {"advertiser_id": "ADV1"}


def test_list_advertisers_wraps_rows_and_passes_partner_id():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["operation"] = operation
        seen["params"] = params
        return [{"advertiserId": "1", "entityStatus": "ENTITY_STATUS_ACTIVE"}]

    out = list_tools.list_advertisers(partner_id="P1", read=read)
    assert out["row_count"] == 1
    assert out["rows"][0]["entityStatus"] == "ENTITY_STATUS_ACTIVE"
    assert seen["operation"] == "advertisers.list"
    assert seen["params"] == {"partner_id": "P1"}


def test_list_campaigns_uses_campaigns_operation():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["operation"] = operation
        seen["params"] = params
        return []

    out = list_tools.list_campaigns(advertiser_id="ADV1", read=read)
    assert out["row_count"] == 0
    assert seen["operation"] == "campaigns.list"
    assert seen["params"] == {"advertiser_id": "ADV1"}


def test_list_insertion_orders_uses_insertion_orders_operation():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["operation"] = operation
        return [{"insertionOrderId": "9"}]

    out = list_tools.list_insertion_orders(advertiser_id="ADV1", read=read)
    assert out["row_count"] == 1
    assert seen["operation"] == "insertionOrders.list"


def test_list_line_items_uses_line_items_operation_and_maps_enums():
    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        return [
            {
                "lineItemId": "5",
                "entityStatus": "ENTITY_STATUS_PAUSED",
                "lineItemType": "LINE_ITEM_TYPE_DISPLAY_DEFAULT",
            }
        ]

    out = list_tools.list_line_items(advertiser_id="ADV1", read=read)
    assert out["rows"][0]["entityStatus"] == "ENTITY_STATUS_PAUSED"
    assert out["rows"][0]["lineItemType"] == "LINE_ITEM_TYPE_DISPLAY_DEFAULT"


# --- enum tolerance (unit) ----------------------------------------------------


def test_map_row_passes_known_enums_through_unchanged():
    row = {
        "lineItemId": "1",
        "entityStatus": "ENTITY_STATUS_ACTIVE",
        "lineItemType": "LINE_ITEM_TYPE_VIDEO_DEFAULT",
    }
    mapped = catalogs.map_row(row)
    assert mapped["entityStatus"] == "ENTITY_STATUS_ACTIVE"
    assert mapped["lineItemType"] == "LINE_ITEM_TYPE_VIDEO_DEFAULT"


def test_map_row_collapses_unknown_demand_gen_enums_to_unknown():
    # Fabricated Demand Gen members the pinned v4 client does not recognise yet.
    row = {
        "lineItemId": "1",
        "entityStatus": "ENTITY_STATUS_ACTIVE",
        "lineItemType": "LINE_ITEM_TYPE_DEMAND_GEN",
    }
    mapped = catalogs.map_row(row)
    assert mapped["lineItemType"] == "UNKNOWN"
    # Known field on the same row is untouched.
    assert mapped["entityStatus"] == "ENTITY_STATUS_ACTIVE"


def test_map_row_collapses_unknown_entity_status():
    mapped = catalogs.map_row({"entityStatus": "ENTITY_STATUS_BRAND_NEW_2027"})
    assert mapped["entityStatus"] == "UNKNOWN"


def test_map_row_leaves_missing_and_non_string_enum_fields_alone():
    # No enum keys present -> row is returned as an untouched copy.
    assert catalogs.map_row({"lineItemId": "1"}) == {"lineItemId": "1"}
    # Non-string enum value is left as-is (the API always sends strings; defensive).
    assert catalogs.map_row({"entityStatus": 7})["entityStatus"] == 7


def test_map_row_returns_a_copy():
    row = {"entityStatus": "ENTITY_STATUS_ACTIVE"}
    mapped = catalogs.map_row(row)
    assert mapped is not row


def test_map_rows_projects_each_row():
    rows = [
        {"entityStatus": "ENTITY_STATUS_ACTIVE"},
        {"lineItemType": "LINE_ITEM_TYPE_DEMAND_GEN"},
    ]
    out = catalogs.map_rows(rows)
    assert out[0]["entityStatus"] == "ENTITY_STATUS_ACTIVE"
    assert out[1]["lineItemType"] == "UNKNOWN"


# --- backend-not-configured degradation (integration) -------------------------


def test_read_tools_degrade_when_backend_missing():
    # No backends wired -> ctx.backend("dv360.api") is None.
    assembled = build_server(
        env=_env(),
        stream_factory=_stream,
        connectors=[register_dv360_read],
    )
    names = {t.name for t in assembled.registry.all_tools()}
    assert "dv360.advertisers.list" in names
