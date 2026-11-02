"""Anchor the audit chain head in Bitcoin with OpenTimestamps.

The hash chain makes the ledger tamper-evident *relative to its own head*; whoever controls the
server could still rewrite the whole file and re-sign it. Anchoring publishes the head to a
neutral, append-only record: ``anchor_ledger`` writes a statement (chain head, record count,
time, the ledger's public key) under ``<audit dir>/anchors/`` and submits its SHA-256 — only the
hash leaves the machine — to public OpenTimestamps calendars, which aggregate it into a Bitcoin
transaction within hours. The ``.ots`` proof beside the statement is the standard format, so
anyone can verify it independently with ``ots verify anchor-N.json.ots``.
``anchor_status`` upgrades pending proofs once Bitcoin has confirmed them, reports the block
heights and — instead of trusting the calendar — checks each attested message against that
block's merkle root from a public block explorer (``bitcoin_verified``). Requires the
``anchoring`` extra (``opentimestamps``).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from typing import Any

from .audit import AuditLedger

DEFAULT_CALENDARS: tuple[str, ...] = (
    "https://a.pool.opentimestamps.org",
    "https://b.pool.opentimestamps.org",
    "https://a.pool.eternitywall.com",
)
CALENDAR_TIMEOUT_S = 15

CalendarFactory = Callable[[str], Any]
# Block height -> that block's merkle root, hex as block explorers display it (byte-reversed).
MerkleRootFn = Callable[[int], str]
_EXPLORER = "https://mempool.space/api"


def mempool_merkle_root(height: int) -> str:
    """Merkle root of the Bitcoin block at ``height`` from the public mempool.space API."""
    import json
    import urllib.request

    def get(path: str) -> bytes:
        with urllib.request.urlopen(f"{_EXPLORER}{path}", timeout=CALENDAR_TIMEOUT_S) as reply:  # noqa: S310
            return bytes(reply.read())

    block_hash = get(f"/block-height/{int(height)}").decode().strip()
    return str(json.loads(get(f"/block/{block_hash}"))["merkle_root"])


def _remote_calendar(url: str) -> Any:
    from opentimestamps.calendar import RemoteCalendar

    return RemoteCalendar(url)


def _anchors_dir(ledger: AuditLedger) -> Path:
    directory = ledger.directory
    if directory is None:
        raise ValueError("only a persistent ledger (QUANTUM_ADS_AUDIT_DIR) can be anchored")
    return directory / "anchors"


def anchor_ledger(
    ledger: AuditLedger,
    *,
    calendars: Sequence[str] = DEFAULT_CALENDARS,
    calendar_factory: CalendarFactory = _remote_calendar,
) -> dict[str, object]:
    """Timestamp the current chain head; return the statement + proof paths."""
    from opentimestamps.core.op import OpSHA256
    from opentimestamps.core.serialize import StreamSerializationContext
    from opentimestamps.core.timestamp import DetachedTimestampFile, Timestamp

    anchors = _anchors_dir(ledger)
    if not ledger.records:
        raise ValueError("the audit ledger is empty: nothing to anchor")
    anchors.mkdir(parents=True, exist_ok=True)
    sequence = len(list(anchors.glob("anchor-*.json"))) + 1
    statement = anchors / f"anchor-{sequence}.json"
    body = {
        "chain_head": ledger.records[-1].digest,
        "records": len(ledger.records),
        "anchored_at": dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "public_key_pem": ledger.public_key_pem(),
    }
    data = json.dumps(body, sort_keys=True, indent=2).encode()
    digest = hashlib.sha256(data).digest()

    proof = DetachedTimestampFile(OpSHA256(), Timestamp(digest))
    reached = 0
    for url in calendars:
        try:
            proof.timestamp.merge(calendar_factory(url).submit(digest, timeout=CALENDAR_TIMEOUT_S))
            reached += 1
        except Exception:  # noqa: BLE001, S112 - a down calendar is skipped; one is enough
            continue
    if reached == 0:
        raise RuntimeError("no calendar accepted the timestamp; retry later")
    statement.write_bytes(data)
    proof_path = statement.with_name(statement.name + ".ots")
    with proof_path.open("wb") as handle:
        proof.serialize(StreamSerializationContext(handle))
    return {
        "statement": str(statement),
        "proof": str(proof_path),
        "sha256": digest.hex(),
        "chain_head": body["chain_head"],
        "records": body["records"],
        "calendars_ok": reached,
    }


def _nodes(stamp: Any) -> Iterator[Any]:
    yield stamp
    for child in stamp.ops.values():
        yield from _nodes(child)


def _verify_blocks(
    attestations: list[tuple[bytes, int]], merkle_root: MerkleRootFn | None
) -> bool | None:
    """True if every attested message equals its block's merkle root; None if not checkable."""
    if not attestations or merkle_root is None:
        return None
    try:
        return all(msg[::-1].hex() == merkle_root(height) for msg, height in attestations)
    except Exception:  # noqa: BLE001 - explorer unreachable: unknown, not failed
        return None


def anchor_status(
    ledger: AuditLedger,
    *,
    calendar_factory: CalendarFactory = _remote_calendar,
    merkle_root: MerkleRootFn | None = mempool_merkle_root,
) -> list[dict[str, object]]:
    """Upgrade pending proofs; report pending vs Bitcoin-confirmed, verified against the chain."""
    from opentimestamps.core.notary import BitcoinBlockHeaderAttestation, PendingAttestation
    from opentimestamps.core.serialize import (
        StreamDeserializationContext,
        StreamSerializationContext,
    )
    from opentimestamps.core.timestamp import DetachedTimestampFile

    anchors = _anchors_dir(ledger)
    report: list[dict[str, object]] = []
    for proof_path in sorted(anchors.glob("anchor-*.json.ots")) if anchors.exists() else []:
        with proof_path.open("rb") as handle:
            proof = DetachedTimestampFile.deserialize(StreamDeserializationContext(handle))
        upgraded = False
        for node in list(_nodes(proof.timestamp)):
            for attestation in list(node.attestations):
                if not isinstance(attestation, PendingAttestation):
                    continue
                try:
                    node.merge(
                        calendar_factory(attestation.uri).get_timestamp(
                            node.msg, timeout=CALENDAR_TIMEOUT_S
                        )
                    )
                    upgraded = True
                except Exception:  # noqa: BLE001, S112 - still pending, or calendar unreachable
                    continue
        if upgraded:
            with proof_path.open("wb") as handle:
                proof.serialize(StreamSerializationContext(handle))
        blocks = [
            (msg, att.height)
            for msg, att in proof.timestamp.all_attestations()
            if isinstance(att, BitcoinBlockHeaderAttestation)
        ]
        heights = sorted({height for _, height in blocks})
        report.append(
            {
                "statement": str(proof_path.with_suffix("")),
                "status": "bitcoin" if heights else "pending",
                "bitcoin_block_heights": heights,
                "bitcoin_verified": _verify_blocks(blocks, merkle_root),
            }
        )
    return report
