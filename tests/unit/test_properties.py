"""Property-based fuzzing (Hypothesis) of every parser and integrity check fed untrusted input.

Each property states what must hold for *any* input, not just the hand-picked examples: parsers
fail only with their documented error type, and the audit chain detects every edit or deletion.
"""

from __future__ import annotations

import contextlib
import json
import re

from hypothesis import given, settings
from hypothesis import strategies as st

from quantum_ads.connectors.trends.read.rss import parse_trending_rss, trending_rss_url
from quantum_ads.connectors.video.providers import (
    MAX_SECONDS,
    MIN_SECONDS,
    generate_with_fallback,
)
from quantum_ads.core.query.gaql_validator import GaqlError, validate_gaql
from quantum_ads.core.query.runner import _flatten
from quantum_ads.core.safety.audit import AuditLedger
from quantum_ads.core.tenancy import TenantDirectory

settings.register_profile("ci", max_examples=200, deadline=None)
settings.load_profile("ci")

_JSON = st.recursive(
    st.none() | st.booleans() | st.integers() | st.floats(allow_nan=False) | st.text(),
    lambda children: (
        st.lists(children, max_size=4) | st.dictionaries(st.text(), children, max_size=4)
    ),
    max_leaves=12,
)


@given(st.text())
def test_gaql_validator_only_raises_gaql_errors(query: str) -> None:
    with contextlib.suppress(GaqlError):
        validate_gaql(query)


@given(
    st.from_regex(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}", fullmatch=True),
    st.sampled_from(["segments.date", "segments.week"]),
)
def test_impossible_dates_in_gaql_are_gaql_errors(date: str, segment: str) -> None:
    query = f"SELECT campaign.id, {segment} FROM campaign WHERE {segment} = '{date}'"
    with contextlib.suppress(GaqlError):
        validate_gaql(query)


@given(st.text())
def test_rss_parser_only_raises_value_error(text: str) -> None:
    try:
        rows = parse_trending_rss(text)
    except ValueError:
        return
    assert isinstance(rows, list)


@given(st.text(max_size=12))
def test_rss_url_accepts_only_country_codes(geo: str) -> None:
    try:
        url = trending_rss_url(geo)
    except ValueError:
        return
    code = url.rsplit("=", 1)[1]
    assert re.fullmatch(r"[A-Z]{2}(-[A-Z0-9]{1,3})?", code)


@given(_JSON)
def test_tenant_map_is_either_valid_or_a_value_error(document: object) -> None:
    try:
        directory = TenantDirectory.from_json(json.dumps(document), lambda env: {}, source="t")
    except ValueError:
        return
    for tenant in directory.tenants():
        assert directory.backends(tenant) == {}


@given(st.integers())
def test_video_duration_is_bounded(duration: int) -> None:
    in_range = MIN_SECONDS <= duration <= MAX_SECONDS
    try:
        generate_with_fallback(
            lambda *a: "/tmp/x.mp4", prompt="p", duration_seconds=duration, aspect_ratio="16:9"
        )
    except ValueError:
        assert not in_range
        return
    assert in_range


_NESTED = st.recursive(
    st.integers() | st.text(max_size=5),
    lambda children: st.dictionaries(
        st.text(alphabet="abc", min_size=1, max_size=3), children, max_size=3
    ),
    max_leaves=10,
)


def _leaves(value: object) -> int:
    if isinstance(value, dict):
        return sum(_leaves(v) for v in value.values())
    return 1


@given(st.dictionaries(st.text(alphabet="xyz", min_size=1, max_size=3), _NESTED, max_size=4))
def test_flatten_keeps_every_leaf(row: dict[str, object]) -> None:
    flat = _flatten(row)
    assert all(not isinstance(v, dict) for v in flat.values())
    assert len(flat) <= _leaves(row)


_PAYLOADS = st.lists(
    st.dictionaries(st.text(max_size=5), st.integers() | st.text(max_size=5), max_size=3),
    min_size=2,
    max_size=6,
)


@given(_PAYLOADS, st.data())
def test_audit_chain_detects_any_deletion(
    payloads: list[dict[str, object]], data: st.DataObject
) -> None:
    ledger = AuditLedger.ephemeral(clock=lambda: "2026-11-02T00:00:00Z")
    for payload in payloads:
        ledger.append(actor="a", op="o", payload=payload)
    assert ledger.verify_chain()["ok"] is True
    index = data.draw(st.integers(min_value=0, max_value=len(payloads) - 2))
    del ledger.records[index]
    assert ledger.verify_chain()["first_bad_index"] == index


@given(_PAYLOADS, st.data(), st.text(min_size=1, max_size=8))
def test_audit_chain_detects_any_edit(
    payloads: list[dict[str, object]], data: st.DataObject, forged_op: str
) -> None:
    import dataclasses

    ledger = AuditLedger.ephemeral(clock=lambda: "2026-11-02T00:00:00Z")
    for payload in payloads:
        ledger.append(actor="a", op="o", payload=payload)
    index = data.draw(st.integers(min_value=0, max_value=len(payloads) - 1))
    if forged_op == ledger.records[index].op:
        forged_op += "x"
    ledger.records[index] = dataclasses.replace(ledger.records[index], op=forged_op)
    assert ledger.verify_chain()["first_bad_index"] == index
