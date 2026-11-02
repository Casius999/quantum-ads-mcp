"""Thin FastMCP registration helper (isolated so the framework boundary stays mypy-relaxed).

Long-running tools (generation, warehouse queries, model fits) get a timeout and, when the
server has MCP background tasks enabled (``enable_tasks``), run as tasks: the client receives a
task handle and polls for the result instead of holding the call open. Tools stay synchronous
functions; the task path wraps them to run in a worker thread with the same signature.
"""

from __future__ import annotations

import functools
import weakref
from collections.abc import Callable
from typing import Any

import anyio
from fastmcp import FastMCP

# Tool name -> timeout in seconds. These calls take tens of seconds to minutes.
LONG_RUNNING: dict[str, float] = {
    "video.generate": 900,
    "vertex.veo.generate": 900,
    "vertex.imagen.generate": 300,
    "vertex.gemini.generate": 300,
    "bigquery.query.run": 900,
    "meridian.fit": 3600,
    "meridian.budget.optimize": 900,
    "adh.query.start": 300,
}

_TASK_APPS: weakref.WeakSet[FastMCP] = weakref.WeakSet()


def enable_tasks(app: FastMCP) -> bool:
    """Register the MCP tasks extension on ``app``; False if ``fastmcp-tasks`` is missing."""
    try:
        from fastmcp_tasks import TasksExtension
    except ImportError:
        return False
    app.add_extension(TasksExtension())
    _TASK_APPS.add(app)
    return True


def _as_async(fn: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(fn)
    async def run(*args: Any, **kwargs: Any) -> Any:
        return await anyio.to_thread.run_sync(functools.partial(fn, *args, **kwargs))

    return run


def add_tool(app: FastMCP, name: str, description: str, fn: Callable[..., Any]) -> None:
    timeout = LONG_RUNNING.get(name)
    if timeout is not None and app in _TASK_APPS:
        app.tool(name=name, description=description, task=True, timeout=timeout)(_as_async(fn))
    elif timeout is not None:
        app.tool(name=name, description=description, timeout=timeout)(fn)
    else:
        app.tool(name=name, description=description)(fn)
