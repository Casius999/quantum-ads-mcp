"""Autonomous write mode and the optional write policy (guardrails off unless configured)."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from quantum_ads.core.safety.audit import AuditLedger
from quantum_ads.core.safety.mode import SafetyMode
from quantum_ads.core.safety.policy import WritePolicy, load_policy
from quantum_ads.core.safety.write_executor import WriteExecutor
from quantum_ads.core.tenancy import SCOPE_READ, SCOPE_WRITE, Principal, acting_as

_BUDGET = [{"entity": "campaign_budget", "amount_micros": 50_000_000}]


class Recorder:
    def __init__(self, fail_validation: bool = False) -> None:
        self.calls: list[bool] = []
        self.fail_validation = fail_validation

    def __call__(
        self, cid: str, ops: list[dict[str, object]], validate_only: bool
    ) -> dict[str, object]:
        self.calls.append(validate_only)
        if validate_only and self.fail_validation:
            raise RuntimeError("INVALID_ARGUMENT: budget too low")
        return {"validate_only": validate_only}


def _executor(mutate: Recorder, **safety: object) -> WriteExecutor:
    return WriteExecutor(mutate, SafetyMode(read_only=False, **safety), AuditLedger.ephemeral())  # type: ignore[arg-type]


def test_auto_mode_validates_then_applies_in_one_call():
    mutate = Recorder()
    result = _executor(mutate, write_mode="auto").execute(
        op="ads.budget.update", customer_id="1", operations=_BUDGET
    )
    assert result["applied"] is True
    assert mutate.calls == [True, False]  # validate_only preview, then the real mutation
    assert result["preview"] == {"validate_only": True}


def test_auto_mode_never_applies_when_validation_fails():
    mutate = Recorder(fail_validation=True)
    result = _executor(mutate, write_mode="auto").execute(
        op="ads.budget.update", customer_id="1", operations=_BUDGET
    )
    assert result["applied"] is False
    assert result["error"]["code"] == "VALIDATION_FAILED"  # type: ignore[index]
    assert mutate.calls == [True]


def test_confirm_mode_keeps_the_two_step_flow():
    mutate = Recorder()
    executor = _executor(mutate)
    first = executor.execute(op="ads.budget.update", customer_id="1", operations=_BUDGET)
    assert first["applied"] is False and "confirm_token" in first
    second = executor.execute(
        op="ads.budget.update",
        customer_id="1",
        operations=_BUDGET,
        confirm=str(first["confirm_token"]),
    )
    assert second["applied"] is True


def test_unknown_write_mode_is_refused():
    with pytest.raises(ValueError, match="write_mode"):
        SafetyMode(read_only=False, write_mode="yolo")


def test_no_policy_means_no_limits():
    assert (
        WritePolicy().check(op="merchant.product.delete", operations=_BUDGET * 50, tenant="t")
        is None
    )


def test_policy_blocks_forbidden_operations_by_pattern():
    policy = WritePolicy(forbidden_ops=("*.delete",))
    mutate = Recorder()
    result = _executor(mutate, write_mode="auto", policy=policy).execute(
        op="merchant.product.delete", customer_id="1", operations=[{"id": "x"}]
    )
    assert result["error"]["code"] == "POLICY_DENIED"  # type: ignore[index]
    assert mutate.calls == []  # refused before any API call


def test_policy_allowlist_amount_cap_size_and_hours():
    assert WritePolicy(allowed_ops=("ads.*",)).check(op="gtm.create_tag", operations=[], tenant="t")
    assert WritePolicy(max_amount_micros=10_000_000).check(
        op="ads.budget.update", operations=_BUDGET, tenant="t"
    )
    nested = [{"campaign_budget": {"amount_micros": 5}}]
    assert WritePolicy(max_amount_micros=1).check(op="x.update", operations=nested, tenant="t")
    assert WritePolicy(max_operations_per_call=1).check(
        op="x.update", operations=_BUDGET * 2, tenant="t"
    )
    night = dt.datetime(2026, 11, 3, 2, 0, tzinfo=dt.UTC)
    assert WritePolicy(allowed_hours_utc=(8, 20)).check(
        op="x.update", operations=[], tenant="t", now=night
    )
    assert (
        WritePolicy(allowed_hours_utc=(8, 20)).check(
            op="x.update", operations=[], tenant="t", now=night.replace(hour=9)
        )
        is None
    )


def test_daily_write_quota_is_per_tenant():
    policy = WritePolicy(max_writes_per_day=1)
    executor = _executor(Recorder(), write_mode="auto", policy=policy)
    with acting_as(Principal("acme", "a", frozenset({SCOPE_READ, SCOPE_WRITE}))):
        assert executor.execute(op="x.update", customer_id="1", operations=[])["applied"] is True
        second = executor.execute(op="x.update", customer_id="1", operations=[])
        assert second["error"]["code"] == "POLICY_DENIED"  # type: ignore[index]
    with acting_as(Principal("globex", "g", frozenset({SCOPE_READ, SCOPE_WRITE}))):
        assert executor.execute(op="x.update", customer_id="1", operations=[])["applied"] is True


def test_policy_file_with_per_tenant_overrides(tmp_path: Path):
    path = tmp_path / "policy.json"
    path.write_text(
        json.dumps(
            {
                "default": {"max_amount_micros": 100, "forbidden_ops": ["*.delete"]},
                "tenants": {"acme": {"max_amount_micros": 1000}},
            }
        ),
        encoding="utf-8",
    )
    policy = load_policy({"QUANTUM_ADS_POLICY_FILE": str(path)})
    assert policy is not None
    ops = [{"amount_micros": 500}]
    assert policy.for_tenant("globex").check(op="x.update", operations=ops, tenant="globex")
    assert policy.for_tenant("acme").check(op="x.update", operations=ops, tenant="acme") is None
    assert policy.for_tenant("acme").check(op="m.delete", operations=[], tenant="acme")  # inherited
    assert load_policy({}) is None


def test_policy_file_rejects_unknown_keys(tmp_path: Path):
    path = tmp_path / "policy.json"
    path.write_text(json.dumps({"default": {"max_spend": 1}}), encoding="utf-8")
    with pytest.raises(ValueError, match="max_spend"):
        load_policy({"QUANTUM_ADS_POLICY_FILE": str(path)})
