"""Thin FastMCP registration helper (isolated so the framework boundary stays mypy-relaxed)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastmcp import FastMCP


def add_tool(app: FastMCP, name: str, description: str, fn: Callable[..., Any]) -> None:
    app.tool(name=name, description=description)(fn)
