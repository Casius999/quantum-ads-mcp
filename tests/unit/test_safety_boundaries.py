"""Exact boundaries of the safety layer (each test pins down a mutant that used to survive)."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from quantum_ads.core.safety.audit import AuditLedger
from quantum_ads.core.safety.confirm import confirm_token, matches
from quantum_ads.core.safety.policy import WritePolicy, load_policy
from quantum_ads.core.safety.reversal import reversible

AT = dt.datetime(2026, 11, 3, 12, tzinfo=dt.UTC)


def test_confirm_token_ignores_key_order_and_is_stable():
    first = confirm_token("ads.mutate", {"b": 1, "a": {"y": 2, "x": 3}})
    second = confirm_token("ads.mutate", {"a": {"x": 3, "y": 2}, "b": 1})
    assert first == second
    # Golden value: tokens must not change across releases for the same (op, payload).
    assert confirm_token("ads.mutate", {"a": 1}) == "59f1221ff9785c32"
    assert matches("ads.mutate", {"a": 1}, "59f1221ff9785c32")
    assert not matches("ads.mutate", {"a": 2}, "59f1221ff9785c32")
    assert not matches("ads.mutate", {"a": 1}, None)


def test_policy_limits_are_inclusive_caps():
    policy = WritePolicy(max_operations_per_call=2, max_amount_micros=100)
    assert policy.check(op="x", operations=[{}, {}], tenant="t", now=AT) is None
    assert policy.check(op="x", operations=[{}, {}, {}], tenant="t", now=AT)
    assert policy.check(op="x", operations=[{"amount_micros": 100}], tenant="t", now=AT) is None
    assert policy.check(op="x", operations=[{"amount_micros": 101}], tenant="t", now=AT)


def test_allowed_hours_include_the_start_and_exclude_the_end():
    policy = WritePolicy(allowed_hours_utc=(9, 17))
    at = lambda hour: AT.replace(hour=hour)  # noqa: E731
    assert policy.check(op="x", operations=[], tenant="t", now=at(9)) is None
    assert policy.check(op="x", operations=[], tenant="t", now=at(16)) is None
    assert policy.check(op="x", operations=[], tenant="t", now=at(17))
    assert policy.check(op="x", operations=[], tenant="t", now=at(8))


def test_daily_write_cap_counts_per_tenant_and_day():
    policy = WritePolicy(max_writes_per_day=1)
    policy.record_write("t", now=AT)
    assert policy.check(op="x", operations=[], tenant="t", now=AT)
    assert policy.check(op="x", operations=[], tenant="other", now=AT) is None
    assert policy.check(op="x", operations=[], tenant="t", now=AT + dt.timedelta(days=1)) is None
    WritePolicy().record_write("t")  # no cap: nothing to count, never raises


def test_policy_file_sections_and_errors(tmp_path: Path):
    path = tmp_path / "policy.json"
    path.write_text(
        json.dumps(
            {
                "default": {"forbidden_ops": ["*.delete"], "max_amount_micros": 10},
                "tenants": {"acme": {"max_amount_micros": 99}},
            }
        ),
        encoding="utf-8",
    )
    policies = load_policy({"QUANTUM_ADS_POLICY_FILE": str(path)})
    assert policies is not None
    acme, other = policies.for_tenant("acme"), policies.for_tenant("globex")
    assert acme.max_amount_micros == 99 and acme.forbidden_ops == ("*.delete",)
    assert other.max_amount_micros == 10
    acme.record_write("acme")
    assert other._counts == {}  # tenants never share counters with the default
    for bad, message in (
        ([], "expected an object with 'default'"),
        ({"default": []}, "default: expected an object"),
        ({"default": {"max_ops": 1}}, r"unknown policy keys \['max_ops'\]"),
        ({"tenants": {"acme": {"nope": 1}}}, "tenant 'acme'"),
    ):
        path.write_text(json.dumps(bad), encoding="utf-8")
        with pytest.raises(ValueError, match=message):
            load_policy({"QUANTUM_ADS_POLICY_FILE": str(path)})
    assert load_policy({}) is None


def test_rollback_tenant_is_the_actor_prefix_even_with_colons_in_the_subject():
    ledger = AuditLedger.ephemeral()
    ledger.append(actor="acme:svc:bot", op="ads.mutate", payload={"inverse_operations": [1]})
    assert [i for i, _ in reversible(ledger.records, prefix="ads.", tenant="acme")] == [0]
    assert reversible(ledger.records, prefix="ads.", tenant="acme:svc") == []
