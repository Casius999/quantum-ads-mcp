"""Live conformance for the BigQuery connector (run with `pytest -m live`).

Reads (datasets.list / tables.list / query.dry_run / query.run) + a validate_only mutate preview
(no dataset/table is created). Needs a broad-scope OAuth token (cloud-platform) in GOOGLE_OAUTH_*
and GOOGLE_CLOUD_PROJECT. query.run only runs `SELECT 1` (0 bytes billed).
"""

import os

import pytest

pytestmark = pytest.mark.live

_REQ = ("GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_OAUTH_CLIENT_SECRET", "GOOGLE_OAUTH_REFRESH_TOKEN")


def _project() -> str:
    proj = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not proj:
        pytest.skip("GOOGLE_CLOUD_PROJECT not set")
    return proj


def _creds() -> dict[str, object]:
    if any(not os.environ.get(k) for k in _REQ):
        pytest.skip("broad OAuth creds missing (run scripts/get_refresh_token.py)")
    proj = _project()
    return {
        "client_id": os.environ["GOOGLE_OAUTH_CLIENT_ID"],
        "client_secret": os.environ["GOOGLE_OAUTH_CLIENT_SECRET"],
        "refresh_token": os.environ["GOOGLE_OAUTH_REFRESH_TOKEN"],
        "project_id": proj,
        "quota_project_id": proj,
    }


def _read():
    from quantum_ads.connectors.bigquery.sdk import default_read_factory

    return default_read_factory(_creds(), "v2")


def test_bigquery_datasets_list_live():
    rows = _read()("datasets.list", {"project_id": _project()})
    assert isinstance(rows, list)


def test_bigquery_query_dry_run_live():
    rows = _read()("query.dry_run", {"sql": "SELECT 1 AS x"})
    assert rows and "total_bytes_processed" in rows[0]
    assert int(rows[0]["total_bytes_processed"]) >= 0


def test_bigquery_query_run_live():
    rows = _read()("query.run", {"sql": "SELECT 1 AS x", "max_bytes_billed": 10_000_000})
    assert rows == [{"x": 1}]


def test_bigquery_tables_list_live():
    read = _read()
    datasets = read("datasets.list", {"project_id": _project()})
    if not datasets:
        pytest.skip("no dataset available to list tables")
    out = read("tables.list", {"project_id": _project(), "dataset_id": datasets[0]["dataset_id"]})
    assert isinstance(out, list)


def test_bigquery_create_dataset_validate_only_live():
    from quantum_ads.connectors.bigquery.sdk import default_mutate_factory

    proj = _project()
    ops: list[dict[str, object]] = [
        {"entity": "dataset", "project_id": proj, "dataset_id": "qa_smoke_never_created"}
    ]
    out = default_mutate_factory(_creds(), "v2")(proj, ops, True)  # preview only
    assert out["validate_only"] is True
