"""Read-only safety mode. Default ON for SP0; mutations land in SP1+ behind explicit opt-out."""

from __future__ import annotations


class MutationBlocked(PermissionError):
    """Raised when a mutating operation is attempted in read-only mode."""


class SafetyMode:
    def __init__(self, read_only: bool = True):
        self.read_only = read_only

    def guard_mutation(self, op: str) -> None:
        if self.read_only:
            raise MutationBlocked(
                f"read-only mode: '{op}' refused "
                "(set QUANTUM_ADS_READ_ONLY=false to enable mutations in SP1+)"
            )

    def guard_read(self, op: str) -> None:
        return None
