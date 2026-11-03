"""Free creative backends: any OpenAI-compatible chat endpoint, and FLUX images on Hugging Face.

Untyped third-party boundary (mypy-ignored, coverage-omitted, smoke-gated). They let the
creative studio run without a billed Google Cloud project: text through an OpenAI-compatible
``/chat/completions`` endpoint (NVIDIA NIM, OVHcloud AI Endpoints, a local LM Studio/Ollama...)
and images through the public ``black-forest-labs/FLUX.1-schnell`` ZeroGPU Space.
"""

from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

ReadFn = Callable[[str, dict[str, object]], list[dict[str, object]]]
FLUX_SPACE = "black-forest-labs/FLUX.1-schnell"
RATE_LIMIT_ATTEMPTS = 3
MAX_RETRY_WAIT_S = 65.0


def _post_with_retry(
    request: urllib.request.Request, attempts: int = RATE_LIMIT_ATTEMPTS
) -> dict[str, Any]:
    """POST once; on 429 wait for ``Retry-After`` (capped) and retry - free tiers are RPM-bound."""
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310
                return dict(json.loads(response.read()))
        except urllib.error.HTTPError as exc:
            if exc.code != 429 or attempt == attempts - 1:
                raise
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            delay = float(retry_after) if retry_after and retry_after.isdigit() else 30.0
            time.sleep(min(delay, MAX_RETRY_WAIT_S))
    raise RuntimeError("unreachable")


def openai_chat_factory(creds: dict[str, object], version: str) -> ReadFn:
    base_url = str(creds["base_url"]).rstrip("/")
    model = str(creds.get("model") or "")
    api_key = str(creds.get("api_key") or "")

    def read(op: str, params: dict[str, object]) -> list[dict[str, object]]:
        if op != "chat":
            raise ValueError(f"unsupported llm operation: {op!r}")
        body = {
            "model": str(params.get("model") or model),
            "messages": [{"role": "user", "content": str(params["prompt"])}],
            "max_tokens": int(params.get("max_tokens") or 2048),
            "temperature": float(params.get("temperature") or 0.7),
        }
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        request = urllib.request.Request(
            f"{base_url}/chat/completions", data=json.dumps(body).encode(), headers=headers
        )
        payload = _post_with_retry(request)
        text = payload["choices"][0]["message"]["content"]
        return [{"text": text, "model": payload.get("model", body["model"])}]

    return read


def openai_image_factory(creds: dict[str, object], version: str) -> ReadFn:
    """``/images/generations`` on the same OpenAI-compatible endpoint (e.g. OVHcloud SDXL)."""
    base_url = str(creds["base_url"]).rstrip("/")
    model = str(creds.get("image_model") or "")
    api_key = str(creds.get("api_key") or "")

    def read(op: str, params: dict[str, object]) -> list[dict[str, object]]:
        if op != "image":
            raise ValueError(f"unsupported image operation: {op!r}")
        if not model:
            raise ValueError("QUANTUM_ADS_IMAGE_MODEL is not set")
        body = {
            "model": model,
            "prompt": str(params["prompt"]),
            "n": 1,
            "size": f"{params.get('width') or 1024}x{params.get('height') or 1024}",
            "response_format": "b64_json",
        }
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        request = urllib.request.Request(
            f"{base_url}/images/generations", data=json.dumps(body).encode(), headers=headers
        )
        payload = _post_with_retry(request)
        return [{"image_base64": payload["data"][0]["b64_json"], "provider": model}]

    return read


def free_image_factory(creds: dict[str, object], version: str) -> ReadFn:
    from gradio_client import Client

    token = str(creds["hf_token"]) if creds.get("hf_token") else None
    holder: dict[str, Any] = {}

    def read(op: str, params: dict[str, object]) -> list[dict[str, object]]:
        if op != "image":
            raise ValueError(f"unsupported image operation: {op!r}")
        if "client" not in holder:
            holder["client"] = Client(FLUX_SPACE, token=token, verbose=False)
        result = holder["client"].predict(
            prompt=str(params["prompt"]),
            seed=0,
            randomize_seed=True,
            width=int(params.get("width") or 1024),
            height=int(params.get("height") or 1024),
            num_inference_steps=4,
            api_name="/infer",
        )
        path = result[0] if isinstance(result, tuple | list) else result
        if isinstance(path, dict):
            path = path.get("path") or path.get("url")
        data = Path(str(path)).read_bytes()
        return [{"image_base64": base64.b64encode(data).decode(), "provider": "flux-schnell"}]

    return read
