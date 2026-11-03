"""Agent eval harness: a real LLM operates the MCP server on scripted backends; each task is scored.

The model sees the server's tools (OpenAI function-calling format, over any OpenAI-compatible
endpoint) and a user request. Tool calls go through a real MCP client to the real server, whose
backends are in-memory fakes that record what was asked. A task passes when its check accepts
the recorded calls and the final answer. Nothing touches a Google account.
"""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from fastmcp import Client, FastMCP

# (messages, tools) -> assistant message dict (``content`` and/or ``tool_calls``).
ChatFn = Callable[[list[dict[str, Any]], list[dict[str, Any]]], dict[str, Any]]
MAX_RESULT_CHARS = 4000


@dataclass
class Record:
    """What the fake backends saw during one task."""

    queries: list[str] = field(default_factory=list)
    mutations: list[tuple[str, list[dict[str, object]], bool]] = field(default_factory=list)
    calls: list[tuple[str, dict[str, object]]] = field(default_factory=list)
    answer: str = ""

    @property
    def applied(self) -> list[dict[str, object]]:
        """Operations that were committed (not only previewed)."""
        return [op for _, ops, preview in self.mutations if not preview for op in ops]


@dataclass(frozen=True)
class Task:
    name: str
    prompt: str
    build: Callable[[Record], FastMCP]
    check: Callable[[Record], bool]


def wire_name(name: str) -> str:
    """Function names allow ``[a-zA-Z0-9_-]``; MCP tool names use dots."""
    return re.sub(r"[^a-zA-Z0-9_-]", "_", name)


def openai_tools(tools: list[Any]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    specs, names = [], {}
    for tool in tools:
        wired = wire_name(tool.name)
        names[wired] = tool.name
        specs.append(
            {
                "type": "function",
                "function": {
                    "name": wired,
                    "description": (tool.description or "")[:1024],
                    "parameters": tool.input_schema or {"type": "object", "properties": {}},
                },
            }
        )
    return specs, names


async def run_task(task: Task, chat: ChatFn, *, max_steps: int = 8) -> Record:
    record = Record()
    app = task.build(record)
    async with Client(app) as client:
        specs, names = openai_tools(await client.list_tools())
        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": "You operate a Google marketing MCP server. Use the tools to do what "
                "the user asks, then answer briefly. Write tools apply directly.",
            },
            {"role": "user", "content": task.prompt},
        ]
        for _ in range(max_steps):
            reply = chat(messages, specs)
            calls = reply.get("tool_calls") or []
            messages.append(
                {"role": "assistant", "content": reply.get("content") or "", "tool_calls": calls}
                if calls
                else {"role": "assistant", "content": reply.get("content") or ""}
            )
            if not calls:
                record.answer = str(reply.get("content") or "")
                break
            for call in calls:
                name = names.get(call["function"]["name"], call["function"]["name"])
                try:
                    args = json.loads(call["function"].get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                record.calls.append((name, args))
                result = await client.call_tool(name, args, raise_on_error=False)
                payload = result.structured_content or {"content": str(result.content)}
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.get("id", name),
                        "content": json.dumps(payload, default=str)[:MAX_RESULT_CHARS],
                    }
                )
    return record


def evaluate(tasks: list[Task], chat: ChatFn) -> list[dict[str, object]]:
    """Run every task; a crash in one task counts as a failure, never stops the suite."""
    results: list[dict[str, object]] = []
    for task in tasks:
        try:
            record = asyncio.run(run_task(task, chat))
            passed = bool(task.check(record))
            detail = [name for name, _ in record.calls]
        except Exception as exc:  # noqa: BLE001 - reported per task
            passed, detail = False, [f"error: {exc}"]
        results.append({"task": task.name, "passed": passed, "calls": detail})
    return results
