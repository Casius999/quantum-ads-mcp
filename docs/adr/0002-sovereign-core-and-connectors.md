# 2. Sovereign core + per-product connectors, in a clean public repo

- Status: accepted
- Date: 2026-06-09

## Context

The predecessor (`QUANTUM_ADS_MCP`, private) was pinned to a sunset Google Ads API version, had
committed live credentials in history, and bundled duplicated one-off scripts. A June 2026 survey
showed no open, self-hostable server that is simultaneously complete, write-capable, safe, tested,
version-resilient, and multi-product across the Google marketing stack.

## Decision

Start a **fresh public repository** with zero secrets in history. Build a **sovereign core**
(multi-tenant auth, version resilience, a GAQL/query engine, a read-only-by-default safety spine
with a signed audit ledger, a connector registry) and mount **per-product connectors** that each
reach their API through a named backend (`ctx.backend`). Decompose delivery into sub-projects
(SP0 foundation → SP8 remote/multi-tenant).

## Consequences

Connectors are independent and uniformly guarded. The platform spans the full agency stack
(20 connectors) without bespoke coupling. The old repo's leaked credentials are not present here;
rotating them remains the owner's responsibility.
