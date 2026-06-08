from quantum_ads.core.safety.audit import AuditLedger


def test_append_and_verify():
    ledger = AuditLedger.ephemeral()
    record = ledger.append(actor="default", op="ads.gaql.query", payload={"customer_id": "123"})
    assert ledger.verify(record)
    assert len(ledger.records) == 1


def test_tamper_detected():
    ledger = AuditLedger.ephemeral()
    record = ledger.append(actor="default", op="ads.gaql.query", payload={"customer_id": "123"})
    record.op = "ads.campaign.create"
    assert not ledger.verify(record)
