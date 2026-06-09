"""Generic guarded mutation runner reused by every connector.

Flow: read-only guard -> validate_only preview -> two-step confirm -> signed audit.
The concrete API call is an injected ``MutateFn`` so the logic is fully unit-testable
without any live SDK.
"""

from __future__ import annotations

from collections.abc import Callable

from .audit import AuditLedger
from .confirm import confirm_token, matches
from .mode import MutationBlocked, SafetyMode

# (customer_id, operations, validate_only) -> API result.
MutateFn = Callable[[str, list[dict[str, object]], bool], dict[str, object]]


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
        payload: dict[str, object] = {"customer_id": customer_id, "operations": operations}
        preview = self._mutate(customer_id, operations, True)
        token = confirm_token(op, payload)
        if not matches(op, payload, confirm):
            return {
                "applied": False,
                "preview": preview,
                "confirm_token": token,
                "message": "re-call with confirm=<confirm_token> to apply",
            }
        result = self._mutate(customer_id, operations, False)
        record = self._audit.append(actor="default", op=op, payload=payload)
        return {"applied": True, "result": result, "audit_signature": record.signature.hex()}
