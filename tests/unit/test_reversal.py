"""Rollback targets walk back through history and never undo a rollback."""

from __future__ import annotations

from quantum_ads.core.safety.audit import AuditLedger
from quantum_ads.core.safety.reversal import reversible, rollback_op


def _ledger(*ops: tuple[str, str, bool]) -> AuditLedger:
    ledger = AuditLedger.ephemeral()
    for actor, op, has_inverse in ops:
        payload: dict[str, object] = {"customer_id": "1", "operations": []}
        if has_inverse:
            payload["inverse_operations"] = [{"undo": op}]
        ledger.append(actor=actor, op=op, payload=payload)
    return ledger


def _targets(ledger: AuditLedger, **kwargs: object) -> list[int]:
    found = reversible(
        ledger.records,
        prefix="ads.",
        tenant=kwargs.get("tenant"),
        audit_index=kwargs.get("audit_index"),
    )  # type: ignore[arg-type]
    return [index for index, _ in found]


def test_rollbacks_walk_back_and_are_never_targets_themselves():
    ledger = _ledger(
        ("default", "ads.mutate", True),  # 0
        ("default", "ads.mutate", True),  # 1
        ("default", "ads.mutate", False),  # 2: irreversible
        ("default", rollback_op("ads.rollback", 1), True),  # 3: undid 1, carries its own inverse
        ("default", "ads.rollback", True),  # 4: legacy rollback record without an index
    )
    assert rollback_op("ads.rollback", 1) == "ads.rollback:1"
    assert _targets(ledger) == [0]
    ledger.append(
        actor="default", op=rollback_op("ads.rollback", 0), payload={"inverse_operations": [1]}
    )
    assert _targets(ledger) == []


def test_tenant_and_index_filters():
    ledger = _ledger(("acme:alice", "ads.mutate", True), ("globex:bob", "ads.mutate", True))
    assert _targets(ledger, tenant="acme") == [0]
    assert _targets(ledger, audit_index=1) == [1]
    assert _targets(ledger, tenant="acme", audit_index=1) == []
    assert reversible(ledger.records, prefix="google.api.call:", tenant=None) == []
