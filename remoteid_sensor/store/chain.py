"""Tamper-evident append-only record store.

The project's central claim is that published drone flight records can be
verified rather than trusted. That claim is worthless if this sensor's own
records can be quietly edited after the fact, so every record is linked to its
predecessor by hash:

    hash[n] = sha256( canonical_json( seq, prev_hash, record ) )

Any later edit, reorder, insertion or deletion changes a hash and breaks every
link after it. `verify()` finds the exact record where the chain broke.

RETENTION AND THE CHAIN
-----------------------
Deleting a record to satisfy the 30-day retention policy would break the chain
and destroy the integrity proof for everything recorded afterwards. Retention
is therefore enforced by REDACTION, not deletion:

  - the record's content is replaced by a tombstone
  - the original hash is preserved, so the chain still verifies end to end
  - the tombstone records when and why the content was removed

The result is that an expired record proves it existed and when, proves it has
not been substituted, and no longer discloses what it contained. If the
original content is ever produced from elsewhere it can be checked against the
retained hash. Nothing about the redaction is silent.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Iterator

GENESIS_PREV_HASH = "0" * 64


class RetentionClass(str, Enum):
    """How long a record's content survives.

    RAW expires on the retention clock. PUBLISHED is the evidentiary basis of
    something already asserted publicly and is never auto-expired; retracting
    it is a deliberate human act, not a timer.
    """
    RAW = "raw"
    PUBLISHED = "published"


class ChainError(Exception):
    """The chain does not verify."""


@dataclass(frozen=True)
class ChainBreak:
    seq: int
    expected: str
    found: str
    reason: str


def canonical_json(obj: Any) -> str:
    """Serialize deterministically so a hash is reproducible anywhere.

    Sorted keys, no incidental whitespace, no non-ASCII escaping surprises.
    Two machines must agree byte-for-byte or the chain is meaningless.
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def compute_hash(seq: int, prev_hash: str, record: dict) -> str:
    payload = canonical_json({"seq": seq, "prev_hash": prev_hash, "record": record})
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


class RecordChain:
    """Append-only hash-linked JSONL store."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._seq, self._head = self._read_tail()

    def _read_tail(self) -> tuple[int, str]:
        """Recover sequence and head hash without loading the whole file."""
        if not self.path.exists() or self.path.stat().st_size == 0:
            return -1, GENESIS_PREV_HASH
        last = None
        with self.path.open("r", encoding="ascii") as fh:
            for line in fh:
                if line.strip():
                    last = line
        if last is None:
            return -1, GENESIS_PREV_HASH
        entry = json.loads(last)
        return entry["seq"], entry["hash"]

    @property
    def head_hash(self) -> str:
        return self._head

    @property
    def next_seq(self) -> int:
        return self._seq + 1

    def append(self, record: dict,
               retention: RetentionClass = RetentionClass.RAW) -> dict:
        """Append one record and return the stored entry.

        The write is flushed and fsynced before the in-memory head advances, so
        a power loss mid-write cannot leave the chain claiming a record that is
        not on disk. A field sensor on a battery bank loses power for real.
        """
        seq = self._seq + 1
        prev = self._head
        digest = compute_hash(seq, prev, record)

        entry = {
            "seq": seq,
            "prev_hash": prev,
            "hash": digest,
            "written_at": time.time(),
            "retention": retention.value,
            "record": record,
        }

        with self.path.open("a", encoding="ascii") as fh:
            fh.write(canonical_json(entry) + "\n")
            fh.flush()
            os.fsync(fh.fileno())

        self._seq, self._head = seq, digest
        return entry

    def __iter__(self) -> Iterator[dict]:
        if not self.path.exists():
            return
        with self.path.open("r", encoding="ascii") as fh:
            for line in fh:
                if line.strip():
                    yield json.loads(line)

    def verify(self) -> list[ChainBreak]:
        """Walk the chain and report every break. Empty list means intact.

        Returns breaks rather than raising on the first one: when a store is
        damaged you need to know the full extent, not just where it started.
        """
        breaks: list[ChainBreak] = []
        prev_hash = GENESIS_PREV_HASH
        expected_seq = 0

        for entry in self:
            seq = entry["seq"]

            if seq != expected_seq:
                breaks.append(ChainBreak(seq=seq, expected=str(expected_seq),
                                         found=str(seq), reason="sequence gap or reorder"))
            if entry["prev_hash"] != prev_hash:
                breaks.append(ChainBreak(seq=seq, expected=prev_hash,
                                         found=entry["prev_hash"],
                                         reason="prev_hash does not match preceding record"))

            # A redacted record keeps the hash computed over its original
            # content, which by design can no longer be recomputed. The link is
            # still checked; the content hash is not.
            if not _is_redacted(entry["record"]):
                recomputed = compute_hash(seq, entry["prev_hash"], entry["record"])
                if recomputed != entry["hash"]:
                    breaks.append(ChainBreak(seq=seq, expected=entry["hash"],
                                             found=recomputed,
                                             reason="record content does not match its hash"))

            prev_hash = entry["hash"]
            expected_seq = seq + 1

        return breaks

    def verify_or_raise(self) -> None:
        breaks = self.verify()
        if breaks:
            first = breaks[0]
            raise ChainError(f"chain broken at seq {first.seq}: {first.reason} "
                             f"({len(breaks)} break(s) total)")


def _is_redacted(record: dict) -> bool:
    return isinstance(record, dict) and record.get("_redacted") is True


def make_tombstone(reason: str, original_retention: str, now: float | None = None) -> dict:
    return {
        "_redacted": True,
        "reason": reason,
        "redacted_at": time.time() if now is None else now,
        "original_retention": original_retention,
    }
