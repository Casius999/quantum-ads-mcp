# Quantum ADS MCP

Sovereign Google marketing agency control plane over the Model Context Protocol — Google Ads API v24 (SOTA June 2026), built on a shared core (multi-tenant auth, version resilience, GAQL engine, safety spine) with a read-only Google Ads connector as the reference implementation.

> **Status:** SP0 (foundation + Google Ads read connector) in progress. Read-only by default. See `docs` for the design spec and implementation plan. Full README lands with the v0.1.0 release.

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)

## Quickstart (dev)

```bash
uv sync --extra dev
uv run pytest -m "not live"
```

## License

MIT
