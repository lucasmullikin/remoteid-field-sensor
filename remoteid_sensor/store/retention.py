"""Retention enforcement by redaction.

Policy (docs/DATA-POLICY.md):
  - raw records expire 30 days after they were written
  - records promoted to PUBLISHED are the evidentiary basis of a public claim
    and are never expired by a timer

Expiry redacts content in place and preserves the hash, so the integrity chain
survives. See remoteid_sensor/store/chain.py for why deletion is not an option.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from .chain import RecordChain, RetentionClass, canonical_json, make_tombstone

#: Default raw retention. 30 days, per the data policy.
DEFAULT_RAW_RETENTION_S = 30 * 24 * 3600


@dataclass(frozen=True)
class RetentionReport:
    examined: int
    redacted: int
    retained_published: int
    already_redacted: int
    cutoff: float

    def summary(self) -> str:
        return (f"examined {self.examined}, redacted {self.redacted}, "
                f"kept {self.retained_published} published, "
                f"{self.already_redacted} already redacted")


def enforce(chain: RecordChain,
            max_age_s: float = DEFAULT_RAW_RETENTION_S,
            now: float | None = None,
            dry_run: bool = False) -> RetentionReport:
    """Redact expired raw records in place.

    The rewrite goes to a temporary file in the same directory, is fsynced, and
    is then atomically renamed over the original. A retention pass interrupted
    by power loss must not be able to truncate the record store.
    """
    now = time.time() if now is None else now
    cutoff = now - max_age_s

    examined = redacted = retained_published = already = 0
    lines: list[str] = []

    for entry in chain:
        examined += 1
        record = entry["record"]

        if isinstance(record, dict) and record.get("_redacted") is True:
            already += 1
        elif entry.get("retention") == RetentionClass.PUBLISHED.value:
            retained_published += 1
        elif entry["written_at"] < cutoff:
            entry = dict(entry)
            entry["record"] = make_tombstone(
                reason=f"raw retention expired ({int(max_age_s // 86400)} days)",
                original_retention=entry.get("retention", RetentionClass.RAW.value),
                now=now)
            redacted += 1

        lines.append(canonical_json(entry))

    report = RetentionReport(examined=examined, redacted=redacted,
                             retained_published=retained_published,
                             already_redacted=already, cutoff=cutoff)

    if dry_run or redacted == 0:
        return report

    _atomic_rewrite(chain.path, lines)
    return report


def _atomic_rewrite(path: Path, lines: list[str]) -> None:
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".retention-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="ascii") as fh:
            for line in lines:
                fh.write(line + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def promote(chain: RecordChain, seqs: set[int], note: str) -> int:
    """Mark records PUBLISHED so retention will never expire them.

    Promotion is how a record becomes the evidentiary basis of a published
    claim. It is deliberately a separate, explicit act: nothing is promoted
    automatically, because nothing should become permanent by accident.
    """
    changed = 0
    lines: list[str] = []

    for entry in chain:
        if entry["seq"] in seqs and entry.get("retention") != RetentionClass.PUBLISHED.value:
            entry = dict(entry)
            entry["retention"] = RetentionClass.PUBLISHED.value
            entry["promoted_at"] = time.time()
            entry["promotion_note"] = note
            changed += 1
        lines.append(canonical_json(entry))

    if changed:
        _atomic_rewrite(chain.path, lines)
    return changed
