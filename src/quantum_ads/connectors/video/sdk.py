"""Live glue for the free video connector: ``gradio_client`` calls to Hugging Face Spaces.

Untyped third-party boundary (mypy-ignored, coverage-omitted, smoke-gated). ``creds`` may carry
``hf_token`` (a free Hugging Face account token raises the ZeroGPU daily quota ~2.5x); without it
the Spaces are called anonymously. One ``Client`` per Space is reused across calls.
Python package: ``gradio_client``.
"""

from __future__ import annotations

from typing import Any

from .providers import SpaceCall


def free_video_factory(creds: dict[str, object], version: str) -> SpaceCall:
    from gradio_client import Client

    token = str(creds["hf_token"]) if creds.get("hf_token") else None
    clients: dict[str, Any] = {}

    def call(space: str, api_name: str, kwargs: dict[str, object]) -> object:
        if space not in clients:
            clients[space] = Client(space, token=token, verbose=False)
        return clients[space].predict(api_name=api_name, **kwargs)

    return call
