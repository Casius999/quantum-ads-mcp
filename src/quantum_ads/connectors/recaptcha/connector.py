"""reCAPTCHA Enterprise connector registrar: mounts the read + guarded write planes in one call.

Read backend is keyed ``"recaptcha.api"`` (a ``ReadFn``); write backend ``"recaptcha.mutate"`` (a
``MutateFn`` whose ``account_id`` carries the GCP project id). Both degrade gracefully: when a
backend is not wired the tools return a structured ``*_NOT_CONFIGURED`` error rather than raising.

Read plane (the lead-quality / fraud signal): ``recaptcha.keys.list`` enumerates site keys, and
``recaptcha.assessment.create`` scores a user-response token, returning a risk score in
``[0.0, 1.0]`` plus reason codes — the core signal feeding conversion quality. The write plane is a
single guarded mutation, ``recaptcha.assessment.annotate``, feeding LEGITIMATE/FRAUDULENT ground
truth back to improve the model (validate_only preview -> confirm token -> signed audit).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from fastmcp import FastMCP

from ...core.context import ServerContext
from ...core.mcp.register import add_tool
from ...core.registry.registry import Capability, ToolSpec
from ...core.safety.write_executor import MutateFn, WriteExecutor
from . import read_tools
from .builders import build_annotate_ops
from .types import ReadFn

READ_BACKEND_KEY = "recaptcha.api"
WRITE_BACKEND_KEY = "recaptcha.mutate"

_READ_NOT_CONFIGURED: dict[str, object] = {
    "error": {"code": "BACKEND_NOT_CONFIGURED", "message": f"{READ_BACKEND_KEY} not wired"}
}
_WRITE_NOT_CONFIGURED: dict[str, object] = {
    "error": {"code": "MUTATE_NOT_CONFIGURED", "message": f"{WRITE_BACKEND_KEY} not wired"}
}


def register_recaptcha(app: FastMCP, ctx: ServerContext) -> None:
    """Mount the full reCAPTCHA connector (read + guarded write) onto the FastMCP app."""
    _register_read(app, ctx)
    _register_write(app, ctx)


def _register_read(app: FastMCP, ctx: ServerContext) -> None:
    def read_backend() -> ReadFn | None:
        backend = ctx.backend(READ_BACKEND_KEY)
        if backend is None:
            return None
        return cast(ReadFn, backend)

    def recaptcha_keys_list(project_id: str) -> dict[str, object]:
        read = read_backend()
        if read is None:
            return dict(_READ_NOT_CONFIGURED)
        return read_tools.list_keys(project_id=project_id, read=read)

    def recaptcha_assessment_create(
        project_id: str, site_key: str, token: str, expected_action: str
    ) -> dict[str, object]:
        read = read_backend()
        if read is None:
            return dict(_READ_NOT_CONFIGURED)
        return read_tools.create_assessment(
            project_id=project_id,
            site_key=site_key,
            token=token,
            expected_action=expected_action,
            read=read,
        )

    tools: list[tuple[str, str, Callable[..., Any]]] = [
        (
            "recaptcha.keys.list",
            "List the reCAPTCHA site keys configured under a project.",
            recaptcha_keys_list,
        ),
        (
            "recaptcha.assessment.create",
            "Score a reCAPTCHA token: risk score 0.0-1.0 + reasons (the lead-quality signal).",
            recaptcha_assessment_create,
        ),
    ]
    for name, description, fn in tools:
        add_tool(app, name, description, fn)

    ctx.registry.register(
        Capability(
            connector="recaptcha",
            domain="read",
            tools=[ToolSpec(name=name, summary=description) for name, description, _ in tools],
        )
    )


def _register_write(app: FastMCP, ctx: ServerContext) -> None:
    holder: dict[str, WriteExecutor] = {}

    def executor() -> WriteExecutor | None:
        backend = ctx.backend(WRITE_BACKEND_KEY)
        if backend is None:
            return None
        if "ex" not in holder:
            holder["ex"] = WriteExecutor(cast(MutateFn, backend), ctx.safety, ctx.audit)
        return holder["ex"]

    def recaptcha_assessment_annotate(
        project_id: str, assessment_id: str, annotation: str, confirm: str | None = None
    ) -> dict[str, object]:
        ex = executor()
        if ex is None:
            return dict(_WRITE_NOT_CONFIGURED)
        return ex.execute(
            op="recaptcha.assessment.annotate",
            customer_id=project_id,
            operations=build_annotate_ops(project_id, assessment_id, annotation),
            confirm=confirm,
        )

    tools: list[tuple[str, str, Callable[..., Any]]] = [
        (
            "recaptcha.assessment.annotate",
            "Annotate an assessment LEGITIMATE/FRAUDULENT to improve the model (guarded).",
            recaptcha_assessment_annotate,
        ),
    ]
    for name, description, fn in tools:
        add_tool(app, name, description, fn)

    ctx.registry.register(
        Capability(
            connector="recaptcha",
            domain="write",
            tools=[
                ToolSpec(name=name, summary=description, read_only=False)
                for name, description, _ in tools
            ],
        )
    )
