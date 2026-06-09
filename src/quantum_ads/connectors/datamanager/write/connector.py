"""Mount guarded Data Manager write tools (first-party uploads) onto the FastMCP app.

Mutations run through the shared :class:`WriteExecutor` (read-only guard -> validate_only preview
-> confirm token -> signed audit). The concrete API call is the ``MutateFn`` backend keyed
``"datamanager.api"``; ``customer_id`` carries the Data Manager destination id (``account_id``).

Every op dict carries ``entity`` (``"audience_member"`` | ``"conversion"``) + ``action`` + payload
(+ ``consent`` on the upload paths) so the SDK boundary can dispatch.

OPERATOR CONTRACT (not enforced here): member identifiers passed in ``members`` MUST already be
SHA-256 hashed and normalized, and ``consent`` (``ad_user_data`` / ``ad_personalization``) is
required for EEA traffic under Consent Mode v2.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from fastmcp import FastMCP

from ....core.context import ServerContext
from ....core.mcp.register import add_tool
from ....core.registry.registry import Capability, ToolSpec
from ....core.safety.write_executor import MutateFn, WriteExecutor
from .audience_ops import (
    build_remove_members_ops,
    build_upload_conversions_ops,
    build_upload_members_ops,
)

BACKEND_KEY = "datamanager.api"

_NOT_CONFIGURED: dict[str, object] = {
    "error": {"code": "MUTATE_NOT_CONFIGURED", "message": f"{BACKEND_KEY} not wired"}
}


def register_datamanager_write(app: FastMCP, ctx: ServerContext) -> None:
    holder: dict[str, WriteExecutor] = {}

    def executor() -> WriteExecutor | None:
        backend = ctx.backend(BACKEND_KEY)
        if backend is None:
            return None
        if "ex" not in holder:
            holder["ex"] = WriteExecutor(cast(MutateFn, backend), ctx.safety, ctx.audit)
        return holder["ex"]

    def datamanager_audience_upload_members(
        destination_id: str,
        audience_id: str,
        members: list[dict[str, object]],
        consent: dict[str, object],
        confirm: str | None = None,
    ) -> dict[str, object]:
        ex = executor()
        if ex is None:
            return dict(_NOT_CONFIGURED)
        return ex.execute(
            op="datamanager.audience.upload_members",
            customer_id=destination_id,
            operations=build_upload_members_ops(destination_id, audience_id, members, consent),
            confirm=confirm,
        )

    def datamanager_audience_remove_members(
        destination_id: str,
        audience_id: str,
        members: list[dict[str, object]],
        confirm: str | None = None,
    ) -> dict[str, object]:
        ex = executor()
        if ex is None:
            return dict(_NOT_CONFIGURED)
        return ex.execute(
            op="datamanager.audience.remove_members",
            customer_id=destination_id,
            operations=build_remove_members_ops(destination_id, audience_id, members),
            confirm=confirm,
        )

    def datamanager_conversions_upload(
        destination_id: str,
        conversions: list[dict[str, object]],
        consent: dict[str, object],
        confirm: str | None = None,
    ) -> dict[str, object]:
        ex = executor()
        if ex is None:
            return dict(_NOT_CONFIGURED)
        return ex.execute(
            op="datamanager.conversions.upload",
            customer_id=destination_id,
            operations=build_upload_conversions_ops(destination_id, conversions, consent),
            confirm=confirm,
        )

    tools: list[tuple[str, str, Callable[..., Any]]] = [
        (
            "datamanager.audience.upload_members",
            "Upload Customer Match audience members (guarded). Identifiers must be SHA-256 "
            "hashed/normalized; consent (ad_user_data/ad_personalization) required for EEA.",
            datamanager_audience_upload_members,
        ),
        (
            "datamanager.audience.remove_members",
            "Remove Customer Match audience members by hashed identifier (guarded).",
            datamanager_audience_remove_members,
        ),
        (
            "datamanager.conversions.upload",
            "Upload offline + enhanced conversions (guarded). Enhanced-conversion identifiers "
            "must be SHA-256 hashed/normalized; consent required for EEA.",
            datamanager_conversions_upload,
        ),
    ]
    for name, description, fn in tools:
        add_tool(app, name, description, fn)

    ctx.registry.register(
        Capability(
            connector="datamanager",
            domain="write",
            tools=[
                ToolSpec(name=name, summary=description, read_only=False)
                for name, description, _ in tools
            ],
        )
    )
