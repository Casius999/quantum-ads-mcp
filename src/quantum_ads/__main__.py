"""Stdio entrypoint for the Quantum ADS MCP server."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from .backends import build_backends
from .connectors.google_ads.sdk import default_mutate_factory, default_stream_factory
from .server import DEFAULT_CONNECTORS, build_server

# The shipped server keeps its signed audit ledger across restarts unless told otherwise.
DEFAULT_AUDIT_DIR = Path.home() / ".quantum-ads" / "audit"


def runtime_env(environ: Mapping[str, str]) -> dict[str, str]:
    """Process env, defaulting QUANTUM_ADS_AUDIT_DIR (set it empty to keep the ledger in memory)."""
    return {"QUANTUM_ADS_AUDIT_DIR": str(DEFAULT_AUDIT_DIR), **environ}


def main() -> None:
    env = runtime_env(os.environ)
    assembled = build_server(
        env=env,
        stream_factory=default_stream_factory,
        connectors=DEFAULT_CONNECTORS,
        mutate_factory=default_mutate_factory,
        backends=build_backends(env),
    )
    assembled.app.run()  # stdio transport


if __name__ == "__main__":
    main()
