"""Ed25519-signed, hash-chained audit ledger.

Every applied mutation appends a record signed over (actor, op, payload, ts, prev_hash), where
``prev_hash`` is the SHA-256 digest of the previous record — so an edited, deleted or reordered
record breaks ``verify_chain``, not only a forged one.

``AuditLedger.open(directory)`` persists the ledger: an append-only ``audit.jsonl`` plus the
signing key ``audit_ed25519.pem`` (created on first use, reused on restart so one public key
verifies the whole history). ``AuditLedger.ephemeral()`` keeps records in memory with a
throwaway key (tests, or a server started without an audit directory).
"""

from __future__ import annotations

import contextlib
import datetime as dt
import hashlib
import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

GENESIS_HASH = "0" * 64
LOG_NAME = "audit.jsonl"
KEY_NAME = "audit_ed25519.pem"

Clock = Callable[[], str]


def _utc_now() -> str:
    return dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


@dataclass(frozen=True)
class AuditRecord:
    actor: str
    op: str
    payload: dict[str, object]
    ts: str
    signature: bytes
    prev_hash: str = GENESIS_HASH

    @property
    def digest(self) -> str:
        """SHA-256 of the signed content + signature; the next record's ``prev_hash``."""
        return hashlib.sha256(self.signed_bytes() + self.signature).hexdigest()

    def signed_bytes(self) -> bytes:
        return _canonical(self.actor, self.op, self.payload, self.ts, self.prev_hash)

    def to_json(self) -> str:
        return json.dumps(
            {
                "actor": self.actor,
                "op": self.op,
                "payload": self.payload,
                "ts": self.ts,
                "prev_hash": self.prev_hash,
                "signature": self.signature.hex(),
            },
            sort_keys=True,
            separators=(",", ":"),
        )

    @classmethod
    def from_json(cls, line: str) -> AuditRecord:
        raw = json.loads(line)
        return cls(
            actor=raw["actor"],
            op=raw["op"],
            payload=raw["payload"],
            ts=raw["ts"],
            signature=bytes.fromhex(raw["signature"]),
            prev_hash=raw["prev_hash"],
        )


def _canonical(actor: str, op: str, payload: dict[str, object], ts: str, prev_hash: str) -> bytes:
    return json.dumps(
        {"actor": actor, "op": op, "payload": payload, "ts": ts, "prev_hash": prev_hash},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def _load_or_create_key(path: Path) -> Ed25519PrivateKey:
    if path.exists():
        key = serialization.load_pem_private_key(path.read_bytes(), password=None)
        if not isinstance(key, Ed25519PrivateKey):
            raise ValueError(f"{path} is not an Ed25519 private key")
        return key
    key = Ed25519PrivateKey.generate()
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(pem)
    return key


class AuditLedger:
    def __init__(
        self,
        private_key: Ed25519PrivateKey,
        *,
        log_path: Path | None = None,
        clock: Clock = _utc_now,
    ) -> None:
        self._sk = private_key
        self._pk: Ed25519PublicKey = private_key.public_key()
        self._log_path = log_path
        self._clock = clock
        self.records: list[AuditRecord] = []

    @classmethod
    def ephemeral(cls, *, clock: Clock = _utc_now) -> AuditLedger:
        return cls(Ed25519PrivateKey.generate(), clock=clock)

    @classmethod
    def open(cls, directory: Path, *, clock: Clock = _utc_now) -> AuditLedger:
        """Persistent ledger in ``directory`` (created if missing), resuming its history."""
        directory.mkdir(parents=True, exist_ok=True)
        ledger = cls(
            _load_or_create_key(directory / KEY_NAME), log_path=directory / LOG_NAME, clock=clock
        )
        if ledger._log_path is not None and ledger._log_path.exists():
            lines = ledger._log_path.read_text(encoding="utf-8").splitlines()
            ledger.records = [AuditRecord.from_json(line) for line in lines if line.strip()]
        return ledger

    def append(
        self,
        *,
        actor: str,
        op: str,
        payload: dict[str, object],
        ts: str | None = None,
    ) -> AuditRecord:
        prev_hash = self.records[-1].digest if self.records else GENESIS_HASH
        stamp = ts or self._clock()
        signature = self._sk.sign(_canonical(actor, op, payload, stamp, prev_hash))
        record = AuditRecord(actor, op, payload, stamp, signature, prev_hash)
        if self._log_path is not None:
            with self._log_path.open("a", encoding="utf-8") as handle:
                handle.write(record.to_json() + "\n")
                handle.flush()
                with contextlib.suppress(OSError):
                    os.fsync(handle.fileno())
        self.records.append(record)
        return record

    def verify(self, record: AuditRecord) -> bool:
        try:
            self._pk.verify(record.signature, record.signed_bytes())
            return True
        except InvalidSignature:
            return False

    def verify_chain(self) -> dict[str, object]:
        """Check every signature and every ``prev_hash`` link, reporting the first bad record."""
        expected = GENESIS_HASH
        for index, record in enumerate(self.records):
            if record.prev_hash != expected or not self.verify(record):
                return {"ok": False, "records": len(self.records), "first_bad_index": index}
            expected = record.digest
        return {"ok": True, "records": len(self.records), "first_bad_index": None}

    def public_key_pem(self) -> str:
        return self._pk.public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode()

    def status(self) -> dict[str, object]:
        return {
            "persistent": self._log_path is not None,
            "path": str(self._log_path) if self._log_path is not None else None,
            "chain": self.verify_chain(),
            "public_key_pem": self.public_key_pem(),
        }
