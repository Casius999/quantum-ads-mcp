from quantum_ads.connectors.google_ads.write.executor import WriteExecutor
from quantum_ads.core.safety.audit import AuditLedger
from quantum_ads.core.safety.mode import SafetyMode


def _mutate_factory() -> tuple[object, list[bool]]:
    calls: list[bool] = []

    def mutate(
        customer_id: str, ops: list[dict[str, object]], validate_only: bool
    ) -> dict[str, object]:
        calls.append(validate_only)
        return {"validate_only": validate_only, "ops": len(ops)}

    return mutate, calls


def test_read_only_blocks_and_never_calls_api():
    mutate, calls = _mutate_factory()
    executor = WriteExecutor(mutate, SafetyMode(read_only=True), AuditLedger.ephemeral())
    out = executor.execute(op="ads.budget.update", customer_id="1", operations=[{"a": 1}])
    assert isinstance(out["error"], dict)
    assert out["error"]["code"] == "READ_ONLY"
    assert calls == []


def test_first_call_previews_then_confirm_applies():
    mutate, calls = _mutate_factory()
    executor = WriteExecutor(mutate, SafetyMode(read_only=False), AuditLedger.ephemeral())

    first = executor.execute(op="ads.budget.update", customer_id="1", operations=[{"a": 1}])
    assert first["applied"] is False
    assert calls == [True]  # validate_only only

    token = first["confirm_token"]
    assert isinstance(token, str)
    second = executor.execute(
        op="ads.budget.update", customer_id="1", operations=[{"a": 1}], confirm=token
    )
    assert second["applied"] is True
    assert calls == [True, True, False]  # preview re-run, then real apply
    assert isinstance(second["audit_signature"], str)


def test_wrong_confirm_does_not_apply():
    mutate, calls = _mutate_factory()
    executor = WriteExecutor(mutate, SafetyMode(read_only=False), AuditLedger.ephemeral())
    out = executor.execute(
        op="ads.budget.update", customer_id="1", operations=[{"a": 1}], confirm="bad"
    )
    assert out["applied"] is False
    assert False not in calls  # validate_only=False (real apply) never happened
