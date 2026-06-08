"""Shared Pydantic models for structured MCP output."""

from __future__ import annotations

from pydantic import BaseModel


class ToolError(BaseModel):
    """Structured, secret-free error surfaced to the MCP client."""

    code: str
    message: str
    request_id: str | None = None
    fields: list[str] = []
