"""Live boundary — smoke-gated, not unit-tested.

Real Looker SDK glue: lazy factories building the read callable (all_dashboards, all_looks,
run_look, run_inline_query) and the dashboard mutate callable (create_dashboard). Isolated at the
untyped third-party boundary (``looker_sdk.*`` is mypy-ignored; this module is coverage-omitted via
the live gate). Imports are local so importing this module stays cheap and credential-free; the
Looker API credentials (base_url / client_id / client_secret) are derived from the shared creds
dict. SDK-derived values stay implicitly typed (``Any``).

Targets **looker_sdk** (the official Looker Python SDK). The client is built with ``init40()`` over
an in-memory settings object so no looker.ini / env file is required; the API3 client id + secret
and instance base URL come from the injected creds dict.

Python package: ``looker_sdk``.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

ReadFn = Callable[[str, dict[str, object]], list[dict[str, object]]]
MutateFn = Callable[[str, list[dict[str, object]], bool], dict[str, object]]


def _settings(creds: dict[str, object]) -> Any:
    """Build an in-memory Looker ApiSettings carrying base_url + API3 client id/secret."""
    from looker_sdk.rtl.api_settings import ApiSettings, SettingsConfig

    config: SettingsConfig = {
        "base_url": str(creds["base_url"]),
        "client_id": str(creds["client_id"]),
        "client_secret": str(creds["client_secret"]),
        "verify_ssl": "true",
    }

    class _InMemorySettings(ApiSettings):
        def read_config(self) -> SettingsConfig:
            return config

    return _InMemorySettings()


def read_factory(creds: dict[str, object], version: str) -> ReadFn:
    """Build the Looker ReadFn dispatching the four read operations."""
    import looker_sdk

    sdk = looker_sdk.init40(config_settings=_settings(creds))

    def _dashboards_list(params: dict[str, object]) -> list[dict[str, object]]:
        return [dict(d) for d in sdk.all_dashboards()]

    def _looks_list(params: dict[str, object]) -> list[dict[str, object]]:
        return [dict(look) for look in sdk.all_looks()]

    def _look_run(params: dict[str, object]) -> list[dict[str, object]]:
        raw = sdk.run_look(
            look_id=str(params["look_id"]),
            result_format=str(params["result_format"]),
        )
        return _parse_result(raw, str(params["result_format"]))

    def _query_run(params: dict[str, object]) -> list[dict[str, object]]:
        from looker_sdk.sdk.api40.models import WriteQuery

        query = sdk.create_query(
            body=WriteQuery(
                model=str(params["model"]),
                view=str(params["view"]),
                fields=list(params["fields"]),  # type: ignore[arg-type]
                filters=dict(params["filters"]),  # type: ignore[arg-type]
            )
        )
        raw = sdk.run_query(query_id=query.id, result_format="json")
        return _parse_result(raw, "json")

    handlers: dict[str, Callable[[dict[str, object]], list[dict[str, object]]]] = {
        "dashboards.list": _dashboards_list,
        "looks.list": _looks_list,
        "look.run": _look_run,
        "query.run": _query_run,
    }

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        handler = handlers.get(operation)
        if handler is None:
            raise ValueError(f"unsupported looker read operation: {operation!r}")
        return handler(params)

    return read


def _parse_result(raw: Any, result_format: str) -> list[dict[str, object]]:
    """Normalize a Looker run result to a list of row dicts.

    ``json`` results deserialize to a list of row objects; any other format is wrapped as a single
    ``{"result": <raw>}`` row so the shared envelope stays uniform.
    """
    if result_format == "json":
        parsed = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
        if isinstance(parsed, list):
            return [dict(row) for row in parsed]
        return [{"result": parsed}]
    return [{"result": raw}]


def mutate_factory(creds: dict[str, object], version: str) -> MutateFn:
    """Build the dashboard MutateFn over the Looker create_dashboard endpoint.

    ``validate_only`` short-circuits to a synthetic preview because the create_dashboard endpoint
    does not expose a server-side validate-only flag; the guarded preview still surfaces the exact
    op dicts that would be applied before the confirm step. ``account_id`` is the constant
    ``"looker"``.
    """
    import looker_sdk

    sdk = looker_sdk.init40(config_settings=_settings(creds))

    def _create_dashboard(account_id: str, op: dict[str, object]) -> dict[str, object]:
        from looker_sdk.sdk.api40.models import WriteDashboard

        created = sdk.create_dashboard(
            body=WriteDashboard(title=str(op["title"]), model=str(op["model"]))
        )
        return {"dashboard_id": created.id, "title": created.title}

    handlers: dict[str, Callable[[str, dict[str, object]], dict[str, object]]] = {
        "dashboard": _create_dashboard,
    }

    def mutate(
        account_id: str, operations: list[dict[str, object]], validate_only: bool
    ) -> dict[str, object]:
        if validate_only:
            return {"validate_only": True, "preview": operations}
        results: list[dict[str, object]] = []
        for op in operations:
            handler = handlers.get(str(op["entity"]))
            if handler is None:
                raise ValueError(f"unsupported looker mutate entity: {op.get('entity')!r}")
            results.append(handler(account_id, op))
        return {"validate_only": False, "results": results}

    return mutate
