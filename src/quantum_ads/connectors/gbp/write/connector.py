"""Mount guarded Google Business Profile write tools onto the FastMCP app.

Mutations run through the shared :class:`WriteExecutor` (read-only guard -> validate_only preview
-> confirm token -> signed audit). The concrete API call is the ``MutateFn`` backend keyed
``"gbp.mutate"``; ``customer_id`` carries the GBP resource name the mutation hangs off (the review
resource name for a reply, the location resource name for an update).

Review replies still live on the legacy v4 ``mybusiness`` host; location updates use the Business
Information v1 host. Both are dispatched by the ``entity``/``action`` keys in the op dicts.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from fastmcp import FastMCP

from ....core.context import ServerContext
from ....core.mcp.register import add_tool
from ....core.registry.registry import Capability, ToolSpec
from ....core.safety.write_executor import MutateFn, WriteExecutor
from .mutate_tools import build_location_update_ops, build_review_reply_ops

BACKEND_KEY = "gbp.mutate"

_NOT_CONFIGURED: dict[str, object] = {
    "error": {"code": "MUTATE_NOT_CONFIGURED", "message": f"{BACKEND_KEY} not wired"}
}


def register_gbp_write(app: FastMCP, ctx: ServerContext) -> None:
    holder: dict[str, WriteExecutor] = {}

    def executor() -> WriteExecutor | None:
        backend = ctx.backend(BACKEND_KEY)
        if backend is None:
            return None
        if "ex" not in holder:
            holder["ex"] = WriteExecutor(cast(MutateFn, backend), ctx.safety, ctx.audit)
        return holder["ex"]

    def gbp_review_reply(
        review_name: str, comment: str, confirm: str | None = None
    ) -> dict[str, object]:
        ex = executor()
        if ex is None:
            return dict(_NOT_CONFIGURED)
        return ex.execute(
            op="gbp.review.reply",
            customer_id=review_name,
            operations=build_review_reply_ops(review_name, comment),
            confirm=confirm,
        )

    def gbp_location_update(
        location_name: str, fields: dict[str, object], confirm: str | None = None
    ) -> dict[str, object]:
        ex = executor()
        if ex is None:
            return dict(_NOT_CONFIGURED)
        return ex.execute(
            op="gbp.location.update",
            customer_id=location_name,
            operations=build_location_update_ops(location_name, fields),
            confirm=confirm,
        )

    tools: list[tuple[str, str, Callable[..., Any]]] = [
        (
            "gbp.review.reply",
            "Reply to a review by resource name (guarded: preview + confirm token).",
            gbp_review_reply,
        ),
        (
            "gbp.location.update",
            "Update a location's fields by resource name (guarded: preview + confirm token).",
            gbp_location_update,
        ),
    ]
    for name, description, fn in tools:
        add_tool(app, name, description, fn)

    ctx.registry.register(
        Capability(
            connector="gbp",
            domain="write",
            tools=[
                ToolSpec(name=name, summary=description, read_only=False)
                for name, description, _ in tools
            ],
        )
    )
