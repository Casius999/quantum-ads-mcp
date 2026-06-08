"""Ed25519-signed audit ledger.

Every mutation (SP1+) appends a signed record; SP8 wires persistent key storage and optional
external anchoring. SP0 uses an ephemeral key to exercise the signing/verification path.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


@dataclass
class AuditRecord:
    actor: str
    op: str
    payload: dict[str, object]
    ts: str
    signature: bytes


def _canonical(actor: str, op: str, payload: dict[str, object], ts: str) -> bytes:
    return json.dumps(
        {"actor": actor, "op": op, "payload": payload, "ts": ts},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


class AuditLedger:
    def __init__(self, private_key: Ed25519PrivateKey):
        self._sk = private_key
        self._pk: Ed25519PublicKey = private_key.public_key()
        self.records: list[AuditRecord] = []

    @classmethod
    def ephemeral(cls) -> AuditLedger:
        return cls(Ed25519PrivateKey.generate())

    def append(
        self,
        *,
        actor: str,
        op: str,
        payload: dict[str, object],
        ts: str = "1970-01-01T00:00:00Z",
    ) -> AuditRecord:
        signature = self._sk.sign(_canonical(actor, op, payload, ts))
        record = AuditRecord(actor=actor, op=op, payload=payload, ts=ts, signature=signature)
        self.records.append(record)
        return record

    def verify(self, record: AuditRecord) -> bool:
        try:
            self._pk.verify(
                record.signature, _canonical(record.actor, record.op, record.payload, record.ts)
            )
            return True
        except InvalidSignature:
            return False
