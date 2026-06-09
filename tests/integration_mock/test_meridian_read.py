"""Meridian MMM connector: registration, read_only flags, pure builders, degradation.

All fakes — the real google-meridian SDK is never imported. Verifies the ``{"rows", "row_count"}``
envelope, the right operation name + params reach the backend, the param builders, and a missing
backend yields a structured ``BACKEND_NOT_CONFIGURED`` error.
"""

from quantum_ads.connectors.meridian import mmm_tools, register_meridian
from quantum_ads.core.query.runner import StreamFn


def _env() -> dict[str, str]:
    return {
        "GOOGLE_ADS_DEVELOPER_TOKEN": "d",
        "GOOGLE_ADS_CLIENT_ID": "c",
        "GOOGLE_ADS_CLIENT_SECRET": "s",
        "GOOGLE_ADS_REFRESH_TOKEN": "r",
        "QUANTUM_ADS_READ_ONLY": "true",
    }


def _stream(creds: dict[str, object], version: str) -> StreamFn:
    return lambda cid, q: []


def _fake_read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
    return [{"operation": operation, "params": params}]


def _backends() -> dict[str, object]:
    return {"meridian.api": _fake_read}


# --- registration via register_meridian -----------------------------------------------------


def test_meridian_tools_registered():
    from quantum_ads.server import build_server

    assembled = build_server(
        env=_env(),
        stream_factory=_stream,
        backends=_backends(),
        connectors=[register_meridian],
    )
    names = {t.name for t in assembled.registry.all_tools()}
    assert "meridian.model.summary" in names
    assert "meridian.roi.by_channel" in names
    assert "meridian.budget.optimize" in names
    assert "meridian.fit" in names


def test_meridian_tools_are_read_only():
    from quantum_ads.server import build_server

    assembled = build_server(
        env=_env(),
        stream_factory=_stream,
        backends=_backends(),
        connectors=[register_meridian],
    )
    for name in (
        "meridian.model.summary",
        "meridian.roi.by_channel",
        "meridian.budget.optimize",
        "meridian.fit",
    ):
        assert assembled.registry.describe_tool(name).read_only is True


# --- pure param builders (unit) -------------------------------------------------------------


def test_build_summary_params_shape():
    params = mmm_tools.build_summary_params("m1")
    assert params == {"model_id": "m1"}


def test_build_roi_params_shape():
    params = mmm_tools.build_roi_params("m1")
    assert params == {"model_id": "m1"}


def test_build_optimize_params_shape():
    params = mmm_tools.build_optimize_params("m1", 50_000)
    assert params == {"model_id": "m1", "total_budget": 50_000}


def test_build_fit_params_shape_passes_config_through():
    config: dict[str, object] = {"kpi_column": "sales", "media_columns": ["search", "social"]}
    params = mmm_tools.build_fit_params("bq://proj.ds.input", config)
    assert params == {"dataset_ref": "bq://proj.ds.input", "config": config}


# --- tool wrappers against the fake ReadFn --------------------------------------------------


def test_model_summary_wraps_rows_and_passes_params():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["operation"] = operation
        seen["params"] = params
        return [{"metric": "r_hat", "value": 1.01}]

    out = mmm_tools.model_summary(model_id="m1", read=read)
    assert out["rows"] == [{"metric": "r_hat", "value": 1.01}]
    assert out["row_count"] == 1
    assert seen["operation"] == mmm_tools.OP_SUMMARY
    assert isinstance(seen["params"], dict)
    assert seen["params"]["model_id"] == "m1"


def test_roi_by_channel_uses_roi_operation():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["operation"] = operation
        seen["params"] = params
        return [{"channel": "search", "roi": 3.2}, {"channel": "social", "roi": 1.8}]

    out = mmm_tools.roi_by_channel(model_id="m1", read=read)
    assert out["row_count"] == 2
    assert seen["operation"] == mmm_tools.OP_ROI
    assert isinstance(seen["params"], dict)
    assert seen["params"]["model_id"] == "m1"


def test_optimize_budget_uses_optimize_operation_and_passes_budget():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["operation"] = operation
        seen["params"] = params
        return [{"channel": "search", "allocation": 60_000}]

    out = mmm_tools.optimize_budget(model_id="m1", total_budget=100_000, read=read)
    assert out["row_count"] == 1
    assert seen["operation"] == mmm_tools.OP_OPTIMIZE
    assert isinstance(seen["params"], dict)
    assert seen["params"]["total_budget"] == 100_000


def test_optimize_budget_defaults_total_budget():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["params"] = params
        return []

    mmm_tools.optimize_budget(model_id="m1", read=read)
    assert isinstance(seen["params"], dict)
    assert seen["params"]["total_budget"] == mmm_tools.DEFAULT_TOTAL_BUDGET


def test_fit_model_uses_fit_operation_and_passes_dataset_and_config():
    seen: dict[str, object] = {}
    config: dict[str, object] = {"kpi_column": "sales"}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["operation"] = operation
        seen["params"] = params
        return [{"model_id": "meridian-1", "status": "fitted"}]

    out = mmm_tools.fit_model(dataset_ref="bq://proj.ds.input", config=config, read=read)
    assert out["row_count"] == 1
    assert seen["operation"] == mmm_tools.OP_FIT
    params = seen["params"]
    assert isinstance(params, dict)
    assert params["dataset_ref"] == "bq://proj.ds.input"
    assert params["config"] == config


# --- backend-not-configured degradation -----------------------------------------------------


def test_model_summary_backend_not_configured():
    out = mmm_tools.model_summary(model_id="m1", read=None)
    assert isinstance(out["error"], dict)
    assert out["error"]["code"] == "BACKEND_NOT_CONFIGURED"


def test_roi_by_channel_backend_not_configured():
    out = mmm_tools.roi_by_channel(model_id="m1", read=None)
    assert isinstance(out["error"], dict)
    assert out["error"]["code"] == "BACKEND_NOT_CONFIGURED"


def test_optimize_budget_backend_not_configured():
    out = mmm_tools.optimize_budget(model_id="m1", read=None)
    assert isinstance(out["error"], dict)
    assert out["error"]["code"] == "BACKEND_NOT_CONFIGURED"


def test_fit_model_backend_not_configured():
    out = mmm_tools.fit_model(dataset_ref="x", config={}, read=None)
    assert isinstance(out["error"], dict)
    assert out["error"]["code"] == "BACKEND_NOT_CONFIGURED"


def test_read_tools_degrade_when_backend_missing():
    from quantum_ads.server import build_server

    # No backends wired -> ctx.backend("meridian.api") is None.
    assembled = build_server(
        env=_env(),
        stream_factory=_stream,
        connectors=[register_meridian],
    )
    names = {t.name for t in assembled.registry.all_tools()}
    assert "meridian.model.summary" in names
