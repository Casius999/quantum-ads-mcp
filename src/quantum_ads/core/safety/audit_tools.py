"""Core MCP tools over the signed audit ledger: status, Bitcoin anchoring, anchor status."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastmcp import FastMCP

from ..context import ServerContext
from ..mcp.register import add_tool
from ..registry.registry import Capability, ToolSpec
from ..tenancy import SCOPE_WRITE, current_principal

_INSTALL_HINT = "install the anchoring extra: `uv sync --extra anchoring`"


def _denied() -> dict[str, object] | None:
    """Anchoring publishes to third parties: over HTTP it needs the write scope."""
    principal = current_principal()
    if principal is not None and not principal.can_write:
        return {"error": {"code": "FORBIDDEN", "message": f"requires the {SCOPE_WRITE} scope"}}
    return None


def _guarded(run: Callable[[], Any]) -> Any:
    try:
        return run()
    except ImportError:
        return {"error": {"code": "MISSING_DEPENDENCY", "message": _INSTALL_HINT}}
    except (ValueError, RuntimeError) as exc:
        return {"error": {"code": "ANCHOR_FAILED", "message": str(exc)}}


def register_audit_tools(app: FastMCP, ctx: ServerContext) -> None:
    def audit_status() -> dict[str, object]:
        return ctx.audit.status()

    def audit_anchor() -> dict[str, object]:
        from .anchor import anchor_ledger

        return _denied() or _guarded(lambda: anchor_ledger(ctx.audit))

    def audit_anchor_status() -> dict[str, object]:
        from .anchor import anchor_status

        denied = _denied()
        if denied is not None:
            return denied
        result = _guarded(lambda: anchor_status(ctx.audit))
        return result if isinstance(result, dict) else {"anchors": result}

    tools: list[tuple[str, str, Callable[..., Any]]] = [
        (
            "audit.status",
            "Signed audit ledger: persistence, path, chain verification, public key.",
            audit_status,
        ),
        (
            "audit.anchor",
            "Anchor the audit chain head in Bitcoin via OpenTimestamps (only its SHA-256 leaves).",
            audit_anchor,
        ),
        (
            "audit.anchor_status",
            "Upgrade pending OpenTimestamps proofs; report pending vs Bitcoin-confirmed anchors.",
            audit_anchor_status,
        ),
    ]
    for name, description, fn in tools:
        add_tool(app, name, description, fn)
    ctx.registry.register(
        Capability(
            connector="core",
            domain="audit",
            tools=[ToolSpec(name=name, summary=summary) for name, summary, _ in tools],
        )
    )
