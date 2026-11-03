"""Run the eval suite against any OpenAI-compatible chat endpoint with tool calling.

    QUANTUM_ADS_LLM_BASE_URL=... QUANTUM_ADS_LLM_MODEL=... [QUANTUM_ADS_LLM_API_KEY=...] \
        python -m quantum_ads.evals [task ...]

Prints one line per task and a JSON summary; exits non-zero when a task fails.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from typing import Any

from ..connectors.insights.sdk import _post_with_retry
from .harness import ChatFn, evaluate
from .tasks import TASKS


def openai_chat(base_url: str, model: str, api_key: str = "") -> ChatFn:
    def chat(messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        body = {
            "model": model,
            "messages": messages,
            "tools": tools,
            "max_tokens": 1024,
            "temperature": 0,
        }
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        request = urllib.request.Request(
            f"{base_url.rstrip('/')}/chat/completions",
            data=json.dumps(body).encode(),
            headers=headers,
        )
        return dict(_post_with_retry(request)["choices"][0]["message"])

    return chat


def main(argv: list[str] | None = None) -> int:
    base_url = os.environ.get("QUANTUM_ADS_LLM_BASE_URL")
    model = os.environ.get("QUANTUM_ADS_LLM_MODEL")
    if not (base_url and model):
        print("set QUANTUM_ADS_LLM_BASE_URL and QUANTUM_ADS_LLM_MODEL", file=sys.stderr)
        return 2
    wanted = set(argv if argv is not None else sys.argv[1:])
    tasks = [t for t in TASKS if not wanted or t.name in wanted]
    results = evaluate(
        tasks, openai_chat(base_url, model, os.environ.get("QUANTUM_ADS_LLM_API_KEY", ""))
    )
    for row in results:
        print(f"{'PASS' if row['passed'] else 'FAIL'}  {row['task']:<24} {row['calls']}")
    passed = sum(bool(r["passed"]) for r in results)
    print(json.dumps({"model": model, "passed": passed, "total": len(results)}))
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
