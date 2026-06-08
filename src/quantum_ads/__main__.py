"""Stdio entrypoint for the Quantum ADS MCP server."""

from __future__ import annotations

import os

from .connectors.google_ads.sdk import default_mutate_factory, default_stream_factory
from .server import DEFAULT_CONNECTORS, build_server


def main() -> None:
    assembled = build_server(
        env=os.environ,
        stream_factory=default_stream_factory,
        connectors=DEFAULT_CONNECTORS,
        mutate_factory=default_mutate_factory,
    )
    assembled.app.run()  # stdio transport


if __name__ == "__main__":
    main()
