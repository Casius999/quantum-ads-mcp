"""Anchoring the audit chain head in Bitcoin via OpenTimestamps (calendars faked)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

pytest.importorskip("opentimestamps")

from opentimestamps.core.notary import BitcoinBlockHeaderAttestation, PendingAttestation
from opentimestamps.core.timestamp import Timestamp

from quantum_ads.core.safety.anchor import anchor_ledger, anchor_status
from quantum_ads.core.safety.audit import AuditLedger


class FakeCalendar:
    confirmed: dict[bytes, int] = {}

    def __init__(self, url: str) -> None:
        self.url = url

    def submit(self, digest: bytes, timeout: float | None = None) -> Timestamp:
        stamp = Timestamp(digest)
        stamp.attestations.add(PendingAttestation(self.url))
        return stamp

    def get_timestamp(self, commitment: bytes, timeout: float | None = None) -> Timestamp:
        height = self.confirmed.get(commitment)
        if height is None:
            raise KeyError("commitment not found")
        stamp = Timestamp(commitment)
        stamp.attestations.add(BitcoinBlockHeaderAttestation(height))
        return stamp


class DownCalendar(FakeCalendar):
    def submit(self, digest: bytes, timeout: float | None = None) -> Timestamp:
        raise ConnectionError("calendar unreachable")


CALENDARS = ("https://a.example", "https://b.example")


@pytest.fixture
def ledger(tmp_path: Path) -> AuditLedger:
    FakeCalendar.confirmed = {}
    ledger = AuditLedger.open(tmp_path)
    ledger.append(actor="acme:alice", op="ads.budget.update", payload={"amount_micros": 1})
    return ledger


def test_anchor_writes_a_statement_and_an_ots_proof(ledger: AuditLedger, tmp_path: Path):
    result = anchor_ledger(ledger, calendars=CALENDARS, calendar_factory=FakeCalendar)
    statement = Path(str(result["statement"]))
    proof = Path(str(result["proof"]))
    assert statement.parent == tmp_path / "anchors" and proof.name == statement.name + ".ots"
    body = json.loads(statement.read_text(encoding="utf-8"))
    assert body["chain_head"] == ledger.records[-1].digest
    assert body["records"] == 1
    assert body["public_key_pem"] == ledger.public_key_pem()
    assert result["calendars_ok"] == 2
    assert result["sha256"] == hashlib.sha256(statement.read_bytes()).hexdigest()
    assert proof.read_bytes().startswith(b"\x00OpenTimestamps\x00\x00Proof\x00")


def test_anchor_survives_a_down_calendar_but_needs_one(ledger: AuditLedger):
    def mixed(url: str) -> FakeCalendar:
        return DownCalendar(url) if url == CALENDARS[0] else FakeCalendar(url)

    assert anchor_ledger(ledger, calendars=CALENDARS, calendar_factory=mixed)["calendars_ok"] == 1
    with pytest.raises(RuntimeError, match="no calendar"):
        anchor_ledger(ledger, calendars=CALENDARS, calendar_factory=DownCalendar)


def test_empty_or_in_memory_ledgers_cannot_be_anchored(tmp_path: Path):
    with pytest.raises(ValueError, match="empty"):
        anchor_ledger(
            AuditLedger.open(tmp_path), calendars=CALENDARS, calendar_factory=FakeCalendar
        )
    memory = AuditLedger.ephemeral()
    memory.append(actor="a", op="o", payload={})
    with pytest.raises(ValueError, match="persistent"):
        anchor_ledger(memory, calendars=CALENDARS, calendar_factory=FakeCalendar)


def test_status_is_pending_then_upgraded_to_bitcoin(ledger: AuditLedger):
    result = anchor_ledger(ledger, calendars=CALENDARS, calendar_factory=FakeCalendar)
    pending = anchor_status(ledger, calendar_factory=FakeCalendar)
    assert pending == [
        {"statement": result["statement"], "status": "pending", "bitcoin_block_heights": []}
    ]

    FakeCalendar.confirmed[bytes.fromhex(str(result["sha256"]))] = 921_000
    confirmed = anchor_status(ledger, calendar_factory=FakeCalendar)
    assert confirmed[0]["status"] == "bitcoin"
    assert confirmed[0]["bitcoin_block_heights"] == [921_000]
    # the upgraded proof was saved: a fresh check needs no calendar any more
    offline = anchor_status(ledger, calendar_factory=DownCalendar)
    assert offline[0]["status"] == "bitcoin"
