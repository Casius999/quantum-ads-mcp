"""Read-only safety mode: ON by default; guarded writes run only after an explicit opt-out.

Over HTTP the request's principal must also hold the write scope: the server-wide flag can only
narrow what a token allows, never widen it.
"""

from __future__ import annotations

from ..tenancy import SCOPE_WRITE, current_principal


class MutationBlocked(PermissionError):
    """Raised when a mutating operation is attempted in read-only mode."""


class SafetyMode:
    def __init__(self, read_only: bool = True):
        self.read_only = read_only

    def guard_mutation(self, op: str) -> None:
        if self.read_only:
            raise MutationBlocked(
                f"read-only mode: '{op}' refused "
                "(set QUANTUM_ADS_READ_ONLY=false to enable guarded writes)"
            )
        principal = current_principal()
        if principal is not None and not principal.can_write:
            raise MutationBlocked(f"'{op}' refused: the access token lacks the {SCOPE_WRITE} scope")

    def guard_read(self, op: str) -> None:
        return None
