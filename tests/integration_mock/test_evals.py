"""The eval harness with a scripted oracle agent: every task is solvable and every check discriminates."""

from __future__ import annotations

import json
from typing import Any

import pytest

from quantum_ads.evals import __main__ as runner
from quantum_ads.evals.harness import Task, evaluate, wire_name
from quantum_ads.evals.tasks import TASKS

CID = "7750839245"


def _call(name: str, args: dict[str, object], n: int = 0) -> dict[str, Any]:
    return {
        "tool_calls": [
            {
                "id": f"c{n}",
                "type": "function",
                "function": {"name": wire_name(name), "arguments": json.dumps(args)},
            }
        ]
    }


def _last_tool(messages: list[dict[str, Any]]) -> dict[str, Any]:
    return json.loads(next(m for m in reversed(messages) if m["role"] == "tool")["content"])


def _oracle(task: str) -> Any:
    def chat(messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        step = sum(1 for m in messages if m["role"] == "assistant")
        if task in ("pause_campaign", "read_only_is_respected"):
            if step == 0:
                return _call(
                    "ads.campaign.set_status",
                    {"customer_id": CID, "campaign_id": "42", "status": "PAUSED"},
                )
            return {"content": json.dumps(_last_tool(messages))[:200]}
        if task == "top_spender":
            if step == 0:
                query = "SELECT campaign.id, campaign.name, metrics.cost_micros FROM campaign"
                return _call("ads.gaql.query", {"customer_id": CID, "query": query})
            rows = _last_tool(messages)["rows"]
            top = max(rows, key=lambda r: r["metrics.cost_micros"])
            return {"content": f"{top['campaign.name']} spent the most."}
        if task == "negative_wasted_terms":
            if step == 0:
                return _call("insights.search_terms", {"customer_id": CID})
            if step == 1:
                ops = [n["operation"] for n in _last_tool(messages)["negative_keywords"]]
                return _call("ads.mutate", {"customer_id": CID, "operations": ops}, 1)
            return {"content": "Added."}
        if step == 0:
            return _call(
                "google.api.call",
                {
                    "api": "analyticsadmin",
                    "method": "properties.customDimensions.create",
                    "params": {"parent": "properties/123"},
                    "body": {
                        "parameterName": "plan_tier",
                        "displayName": "Plan tier",
                        "scope": "EVENT",
                    },
                },
            )
        return {"content": "Created."}

    return chat


@pytest.mark.parametrize("task", TASKS, ids=lambda t: t.name)
def test_oracle_agent_passes_every_task(task: Task):
    (result,) = evaluate([task], _oracle(task.name))
    assert result["passed"] is True, result


@pytest.mark.parametrize("task", TASKS, ids=lambda t: t.name)
def test_an_agent_that_does_nothing_fails_the_action_tasks(task: Task):
    (result,) = evaluate([task], lambda messages, tools: {"content": "Done."})
    # Only the read-only task passes without acting: refusing is the right outcome there.
    assert result["passed"] is (task.name == "read_only_is_respected")


def test_broken_agents_are_reported_not_raised():
    def garbled(messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        if len(messages) < 4:
            return {
                "tool_calls": [{"id": "x", "function": {"name": "health", "arguments": "{oops"}}]
            }
        return {"content": "ok"}

    def crashing(messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        raise RuntimeError("endpoint down")

    (garbled_result,) = evaluate(TASKS[:1], garbled)
    assert garbled_result["passed"] is False and garbled_result["calls"] == ["health"]
    (crashed,) = evaluate(TASKS[:1], crashing)
    assert crashed == {"task": "pause_campaign", "passed": False, "calls": ["error: endpoint down"]}


def test_runner_needs_an_endpoint_and_reports(monkeypatch: pytest.MonkeyPatch, capsys):
    monkeypatch.delenv("QUANTUM_ADS_LLM_BASE_URL", raising=False)
    assert runner.main([]) == 2
    monkeypatch.setenv("QUANTUM_ADS_LLM_BASE_URL", "https://llm.example/v1")
    monkeypatch.setenv("QUANTUM_ADS_LLM_MODEL", "m")
    monkeypatch.setattr(runner, "openai_chat", lambda *a: _oracle("pause_campaign"))
    assert runner.main(["pause_campaign"]) == 0
    assert '"passed": 1, "total": 1' in capsys.readouterr().out
    monkeypatch.setattr(runner, "openai_chat", lambda *a: lambda m, t: {"content": "no"})
    assert runner.main(["pause_campaign"]) == 1


def test_openai_chat_posts_tools_and_returns_the_message(monkeypatch: pytest.MonkeyPatch):
    sent: list[dict[str, Any]] = []

    def post(request):  # type: ignore[no-untyped-def]
        sent.append({"body": json.loads(request.data), "auth": request.get_header("Authorization")})
        return {"choices": [{"message": {"content": "hi"}}]}

    monkeypatch.setattr(runner, "_post_with_retry", post)
    message = runner.openai_chat("https://llm.example/v1/", "m", "k")(
        [{"role": "user", "content": "x"}], []
    )
    assert message == {"content": "hi"} and sent[0]["auth"] == "Bearer k"
    assert sent[0]["body"]["temperature"] == 0
    runner.openai_chat("https://llm.example/v1", "m")([], [])
    assert sent[1]["auth"] is None
