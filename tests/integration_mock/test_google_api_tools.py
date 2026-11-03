"""google.api.* tools over a real MCP client with a fake Discovery backend and mutate backend."""

from __future__ import annotations

import asyncio
import copy

from fastmcp import Client

from quantum_ads.connectors.googleapi import register_google_api
from quantum_ads.server import build_server
from tests.unit.test_googleapi_discovery import DOC

_ENV = {
    "GOOGLE_ADS_DEVELOPER_TOKEN": "d",
    "GOOGLE_ADS_CLIENT_ID": "c",
    "GOOGLE_ADS_CLIENT_SECRET": "s",
    "GOOGLE_ADS_REFRESH_TOKEN": "r",
}


def _doc(api: str, version: str) -> dict[str, object]:
    doc = copy.deepcopy(DOC)
    doc["name"], doc["version"] = api, version
    for resource in doc["resources"].values():  # type: ignore[attr-defined]
        _rename(resource, api)
    return doc


def _rename(node: dict[str, object], api: str) -> None:
    for method in node.get("methods", {}).values():  # type: ignore[attr-defined]
        method["id"] = api + method["id"][len("demo") :]
    for child in node.get("resources", {}).values():  # type: ignore[attr-defined]
        _rename(child, api)


class Fake:
    def __init__(self) -> None:
        self.mutations: list[tuple[str, list[dict[str, object]], bool]] = []
        self.reads: list[dict[str, object]] = []

    def read(self, op: str, params: dict[str, object]) -> list[dict[str, object]]:
        if op == "discovery":
            return [_doc(str(params["api"]), str(params["version"]))]
        self.reads.append(params)
        return [{"widgets": [{"name": "widgets/1"}]}]

    def mutate(
        self, target: str, operations: list[dict[str, object]], validate_only: bool
    ) -> dict[str, object]:
        self.mutations.append((target, operations, validate_only))
        if validate_only:
            return {"validated": True}
        inverse = [
            {
                "api": "sheets",
                "version": "v4",
                "method": "sheets.widgets.delete",
                "params": {"name": "widgets/9"},
                "body": None,
            }
        ]
        return {
            "results": [{"name": "widgets/9"}],
            # Every commit carries an inverse, rollbacks included: only the audit op keeps
            # a rollback from being undone by the next one.
            "inverse_operations": inverse,
        }


def _no_stream(creds: dict[str, object], version: str):  # type: ignore[no-untyped-def]
    raise AssertionError("google.api never streams GAQL")


def _session(fake: Fake | None, env: dict[str, str] | None = None):  # type: ignore[no-untyped-def]
    backends = {} if fake is None else {"google.api": fake.read, "google.api.mutate": fake.mutate}
    return build_server(
        env={
            **_ENV,
            "QUANTUM_ADS_READ_ONLY": "false",
            "QUANTUM_ADS_WRITE_MODE": "auto",
            **(env or {}),
        },
        stream_factory=_no_stream,
        connectors=[register_google_api],
        backends=backends,
    ).app


def _calls(app, *calls: tuple[str, dict[str, object]]) -> list[dict[str, object]]:  # type: ignore[no-untyped-def]
    async def scenario() -> list[dict[str, object]]:
        out = []
        async with Client(app) as client:
            for name, args in calls:
                result = await client.call_tool(name, args, raise_on_error=False)
                assert isinstance(result.structured_content, dict), result
                out.append(result.structured_content)
        return out

    return asyncio.run(scenario())


def test_discovery_tools_list_and_describe():
    fake = Fake()
    listed, methods, writes, described = _calls(
        _session(fake),
        ("google.api.list", {}),
        ("google.api.methods", {"api": "sheets"}),
        (
            "google.api.methods",
            {"api": "sheets", "resource": "widgets.gadgets", "writes_only": True},
        ),
        ("google.api.describe", {"api": "sheets", "method": "widgets.patch"}),
    )
    assert {"api": "sheets", "default_version": "v4"} in listed["apis"]  # type: ignore[operator]
    assert methods["count"] == 14 and methods["version"] == "v4"
    assert [m["method"] for m in writes["methods"]] == [  # type: ignore[union-attr]
        "sheets.widgets.gadgets.delete",
        "sheets.widgets.gadgets.insert",
    ]
    assert described["validate_only"] is True and described["request"] == "Widget"
    assert described["parameters"]["name"]["pattern"] == "^widgets/[^/]+$"  # type: ignore[index]
    assert "displayName" in described["request_fields"]  # type: ignore[operator]


def test_read_runs_only_read_methods():
    fake = Fake()
    ok, refused, bad = _calls(
        _session(fake),
        ("google.api.read", {"api": "drive", "method": "widgets.list", "params": {"view": "FULL"}}),
        (
            "google.api.read",
            {"api": "drive", "method": "widgets.create", "params": {"parent": "p"}},
        ),
        ("google.api.read", {"api": "nope", "method": "x"}),
    )
    assert ok["response"] == {"widgets": [{"name": "widgets/1"}]}
    assert fake.reads[0]["method"] == "drive.widgets.list" and fake.reads[0]["version"] == "v3"
    assert (
        refused["error"]["code"] == "INVALID_CALL"
        and "use google.api.call" in refused["error"]["message"]
    )  # type: ignore[index]
    assert "is not exposed" in bad["error"]["message"]  # type: ignore[index]


def test_call_is_validated_guarded_audited_and_rolled_back():
    fake = Fake()
    created, invalid, reads_only, delete_refused, deleted, undo_delete, rolled, nothing_left = (
        _calls(
            _session(fake),
            (
                "google.api.call",
                {
                    "api": "sheets",
                    "method": "widgets.create",
                    "params": {"parent": "p"},
                    "body": {"displayName": "QA"},
                },
            ),
            (
                "google.api.call",
                {
                    "api": "sheets",
                    "method": "widgets.create",
                    "params": {"parent": "p"},
                    "body": {"bogus": 1},
                },
            ),
            (
                "google.api.call",
                {"api": "sheets", "method": "widgets.get", "params": {"name": "widgets/1"}},
            ),
            (
                "google.api.call",
                {"api": "sheets", "method": "widgets.delete", "params": {"name": "widgets/1"}},
            ),
            (
                "google.api.call",
                {
                    "api": "sheets",
                    "method": "widgets.delete",
                    "params": {"name": "widgets/1"},
                    "allow_delete": True,
                },
            ),
            ("google.api.rollback", {}),
            ("google.api.rollback", {}),
            ("google.api.rollback", {}),
        )
    )
    assert created["applied"] is True and created["result"]["results"] == [{"name": "widgets/9"}]  # type: ignore[index]
    assert fake.mutations[0][0] == "sheets/v4" and fake.mutations[0][2] is True  # preview first
    assert "unknown field 'bogus'" in invalid["error"]["message"]  # type: ignore[index]
    assert "only reads" in reads_only["error"]["message"]  # type: ignore[index]
    assert "allow_delete" in delete_refused["error"]["message"]  # type: ignore[index]
    assert deleted["applied"] is True
    assert undo_delete["rolled_back"]["op"] == "google.api.call:sheets.widgets.delete"  # type: ignore[index]
    assert (
        rolled["applied"] is True
        and rolled["rolled_back"]["op"] == "google.api.call:sheets.widgets.create"
    )  # type: ignore[index]
    assert fake.mutations[-1][1] == [
        {"method": "sheets.widgets.delete", "params": {"name": "widgets/9"}, "body": None}
    ]
    # The create was undone; the rollback itself is never the next target.
    assert nothing_left["error"]["code"] == "INVALID_CALL"  # type: ignore[index]


def test_bigquery_jobs_are_routed_to_the_cost_guarded_tool():
    fake = Fake()

    def read(op: str, params: dict[str, object]) -> list[dict[str, object]]:
        doc = _doc("bigquery", "v2")
        doc["resources"]["jobs"] = {
            "methods": {"insert": {"id": "bigquery.jobs.insert", "httpMethod": "POST"}}
        }  # type: ignore[index]
        return [doc]

    app = build_server(
        env={**_ENV, "QUANTUM_ADS_READ_ONLY": "false"},
        stream_factory=_no_stream,
        connectors=[register_google_api],
        backends={"google.api": read, "google.api.mutate": fake.mutate},
    ).app
    out, read_out = _calls(
        app,
        ("google.api.call", {"api": "bigquery", "method": "jobs.insert"}),
        ("google.api.read", {"api": "bigquery", "method": "jobs.insert"}),
    )
    assert "bigquery.query" in out["error"]["message"] and fake.mutations == []  # type: ignore[index]
    assert "bigquery.query" in read_out["error"]["message"]  # type: ignore[index]


def test_read_only_mode_and_missing_backends():
    fake = Fake()
    (blocked,) = _calls(
        _session(fake, {"QUANTUM_ADS_READ_ONLY": "true"}),
        (
            "google.api.call",
            {"api": "sheets", "method": "widgets.create", "params": {"parent": "p"}},
        ),
    )
    assert blocked["error"]["code"] == "READ_ONLY"
    unwired, no_mutate = _calls(
        _session(None),
        ("google.api.methods", {"api": "sheets"}),
        ("google.api.rollback", {}),
    )
    assert unwired["error"]["code"] == "BACKEND_NOT_CONFIGURED"
    assert no_mutate["error"]["code"] == "INVALID_CALL"
    app = build_server(
        env=_ENV,
        stream_factory=_no_stream,
        connectors=[register_google_api],
        backends={"google.api": fake.read},
    ).app
    (missing,) = _calls(
        app,
        (
            "google.api.call",
            {"api": "sheets", "method": "widgets.create", "params": {"parent": "p"}},
        ),
    )
    assert missing["error"]["code"] == "BACKEND_NOT_CONFIGURED"


def test_api_failures_come_back_as_structured_errors():
    def read(op: str, params: dict[str, object]) -> list[dict[str, object]]:
        if op == "discovery":
            return [_doc(str(params["api"]), str(params["version"]))]
        raise RuntimeError("<HttpError 403 insufficient permissions>")

    app = build_server(
        env=_ENV,
        stream_factory=_no_stream,
        connectors=[register_google_api],
        backends={"google.api": read},
    ).app
    (out,) = _calls(app, ("google.api.read", {"api": "drive", "method": "widgets.list"}))
    assert out["error"]["code"] == "API_ERROR" and "403" in out["error"]["message"]  # type: ignore[index]
