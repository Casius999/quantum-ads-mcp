# 1. Record architecture decisions

- Status: accepted
- Date: 2026-06-09

## Context

This repository implements a broad, security-sensitive control plane. Decisions about safety,
honesty, and structure need a durable, reviewable trail.

## Decision

We record architecture decisions as MADR-format files under `docs/adr/`, numbered sequentially.

## Consequences

Reviewers (and recruiters) can see *why* the system is shaped the way it is, not just *what* it does.
Superseded decisions are kept and marked, not deleted.
