"""Generic guarded mutation runner reused by every connector.

Flow: read-only / scope guard -> optional policy -> validate_only preview -> commit -> signed
audit. ``confirm`` mode commits on a second call carrying the preview's token; ``auto`` mode
commits in the same call once validation passes. The concrete API call is an injected
``MutateFn`` so the logic is fully unit-testable without any live SDK.
"""

from __future__ import annotations

from collections.abc import Callable

from ..tenancy import current_principal
from .audit import AuditLedger
from .confirm import confirm_token, matches
from .mode import MutationBlocked, SafetyMode

# (customer_id, operations, validate_only) -> API result.
MutateFn = Callable[[str, list[dict[str, object]], bool], dict[str, object]]


def _error(code: str, message: str) -> dict[str, object]:
    return {"applied": False, "error": {"code": code, "message": message}}


class WriteExecutor:
    def __init__(self, mutate: MutateFn, safety: SafetyMode, audit: AuditLedger) -> None:
        self._mutate = mutate
        self._safety = safety
        self._audit = audit

    def execute(
        self,
        *,
        op: str,
        customer_id: str,
        operations: list[dict[str, object]],
        confirm: str | None = None,
    ) -> dict[str, object]:
        try:
            self._safety.guard_mutation(op)
        except MutationBlocked as exc:
            return {"error": {"code": "READ_ONLY", "message": str(exc)}}
        principal = current_principal()
        tenant = principal.tenant_id if principal is not None else "operator"
        policy = self._safety.policy_for(tenant)
        if policy is not None:
            refusal = policy.check(op=op, operations=operations, tenant=tenant)
            if refusal is not None:
                return _error("POLICY_DENIED", refusal)

        payload: dict[str, object] = {"customer_id": customer_id, "operations": operations}
        try:
            preview = self._mutate(customer_id, operations, True)
        except Exception as exc:  # noqa: BLE001 - the API's own validation verdict
            return _error("VALIDATION_FAILED", str(exc)[:1000])
        token = confirm_token(op, payload)
        if self._safety.write_mode == "confirm" and not matches(op, payload, confirm):
            return {
                "applied": False,
                "preview": preview,
                "confirm_token": token,
                "message": "re-call with confirm=<confirm_token> to apply",
            }
        result = self._mutate(customer_id, operations, False)
        if policy is not None:
            policy.record_write(tenant)
        actor = principal.actor if principal is not None else "default"
        record = self._audit.append(actor=actor, op=op, payload=payload)
        return {
            "applied": True,
            "preview": preview,
            "result": result,
            "audit_signature": record.signature.hex(),
        }
