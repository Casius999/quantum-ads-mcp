# 3. Smoke-gated SDK boundary

- Status: accepted
- Date: 2026-06-09

## Context

Each connector calls a real Google API. We cannot run those live in CI (no credentials, no live
mutations), yet we must keep `mypy --strict`, a high coverage gate, and honest claims.

## Decision

Isolate every connector's live SDK calls in a per-connector `sdk.py`. The SDK is imported only
inside functions (lazy), so importing the module needs no SDK installed. `sdk.py` modules are
excluded from strict typing (`ignore_errors`) and coverage (`omit`), and real-account checks sit
behind a `live` pytest marker. All tool logic, payload builders, and the safety flow are
unit/mock-tested with no live SDK.

## Consequences

The build is fully green and type-clean without credentials. Documentation states only what tests
prove; live calls are labelled smoke-gated and verified by the operator with real credentials. The
trade-off: a wrong field name inside `sdk.py` is caught at the live boundary, not by CI.
