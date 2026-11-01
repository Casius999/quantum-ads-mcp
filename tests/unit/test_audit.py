import dataclasses
import json
from pathlib import Path

from quantum_ads.core.safety.audit import GENESIS_HASH, AuditLedger


def test_append_and_verify():
    ledger = AuditLedger.ephemeral()
    record = ledger.append(actor="default", op="ads.gaql.query", payload={"customer_id": "123"})
    assert ledger.verify(record)
    assert len(ledger.records) == 1


def test_tamper_detected():
    ledger = AuditLedger.ephemeral()
    record = ledger.append(actor="default", op="ads.gaql.query", payload={"customer_id": "123"})
    forged = dataclasses.replace(record, op="ads.campaign.create")
    assert not ledger.verify(forged)


def test_records_carry_a_real_utc_timestamp_by_default():
    ledger = AuditLedger.ephemeral(clock=lambda: "2026-11-01T03:30:00Z")
    record = ledger.append(actor="default", op="gtm.tag.create", payload={})
    assert record.ts == "2026-11-01T03:30:00Z"
    assert AuditLedger.ephemeral().append(actor="a", op="o", payload={}).ts.startswith("20")


def test_records_are_hash_chained():
    ledger = AuditLedger.ephemeral()
    first = ledger.append(actor="a", op="one", payload={})
    second = ledger.append(actor="a", op="two", payload={})
    assert first.prev_hash == GENESIS_HASH
    assert second.prev_hash == first.digest
    assert ledger.verify_chain() == {"ok": True, "records": 2, "first_bad_index": None}


def test_chain_detects_a_deleted_record():
    ledger = AuditLedger.ephemeral()
    for op in ("one", "two", "three"):
        ledger.append(actor="a", op=op, payload={})
    del ledger.records[1]
    assert ledger.verify_chain() == {"ok": False, "records": 2, "first_bad_index": 1}


def test_persistent_ledger_survives_restart_with_the_same_key(tmp_path: Path):
    ledger = AuditLedger.open(tmp_path)
    first = ledger.append(actor="a", op="one", payload={"x": 1})
    public_key = ledger.public_key_pem()

    reopened = AuditLedger.open(tmp_path)
    second = reopened.append(actor="a", op="two", payload={})

    assert reopened.public_key_pem() == public_key
    assert [r.op for r in reopened.records] == ["one", "two"]
    assert second.prev_hash == first.digest
    assert reopened.verify_chain()["ok"] is True
    lines = (tmp_path / "audit.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["op"] for line in lines] == ["one", "two"]


def test_persistent_ledger_flags_an_edited_line(tmp_path: Path):
    ledger = AuditLedger.open(tmp_path)
    ledger.append(actor="a", op="ads.budget.update", payload={"amount_micros": 1})
    log = tmp_path / "audit.jsonl"
    log.write_text(
        log.read_text(encoding="utf-8").replace('"amount_micros":1', '"amount_micros":9')
    )
    assert AuditLedger.open(tmp_path).verify_chain() == {
        "ok": False,
        "records": 1,
        "first_bad_index": 0,
    }


def test_status_reports_persistence(tmp_path: Path):
    assert AuditLedger.ephemeral().status()["persistent"] is False
    status = AuditLedger.open(tmp_path).status()
    assert status["persistent"] is True
    assert status["path"] == str(tmp_path / "audit.jsonl")
    assert status["chain"] == {"ok": True, "records": 0, "first_bad_index": None}
    assert str(status["public_key_pem"]).startswith("-----BEGIN PUBLIC KEY-----")
