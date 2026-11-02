"""Write safety settings: read-only switch, write mode and the optional policy.

Read-only is ON by default; guarded writes run only after an explicit opt-out. Over HTTP the
request's principal must also hold the write scope: the server-wide flag can only narrow what a
token allows, never widen it.

``write_mode`` decides how an agent commits a write: ``confirm`` returns a validate_only preview
and a token to re-send (two calls), ``auto`` validates and applies in one call — the agent is the
decision-maker and a failed validation still blocks the write.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..tenancy import SCOPE_WRITE, current_principal

if TYPE_CHECKING:
    from .policy import PolicySet, WritePolicy

WRITE_MODES = ("confirm", "auto")


class MutationBlocked(PermissionError):
    """Raised when a mutating operation is attempted in read-only mode."""


class SafetyMode:
    def __init__(
        self,
        read_only: bool = True,
        *,
        write_mode: str = "confirm",
        policy: WritePolicy | PolicySet | None = None,
    ):
        if write_mode not in WRITE_MODES:
            raise ValueError(f"write_mode must be one of {WRITE_MODES}, got {write_mode!r}")
        self.read_only = read_only
        self.write_mode = write_mode
        self.policy = policy

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

    def policy_for(self, tenant: str) -> WritePolicy | None:
        from .policy import PolicySet

        if isinstance(self.policy, PolicySet):
            return self.policy.for_tenant(tenant)
        return self.policy
