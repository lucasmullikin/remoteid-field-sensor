import time

import pytest

from remoteid_sensor.store.chain import RecordChain, RetentionClass
from remoteid_sensor.store.retention import (DEFAULT_RAW_RETENTION_S, enforce,
                                             promote)

DAY = 86400


@pytest.fixture
def chain(tmp_path):
    return RecordChain(tmp_path / "records.jsonl")


def _age(chain, seq, seconds_ago, now):
    """Rewrite one record's written_at so it appears older than it is."""
    import json
    from remoteid_sensor.store.chain import canonical_json
    lines = chain.path.read_text().splitlines()
    out = []
    for line in lines:
        e = json.loads(line)
        if e["seq"] == seq:
            e["written_at"] = now - seconds_ago
        out.append(canonical_json(e))
    chain.path.write_text("\n".join(out) + "\n")


def test_fresh_records_are_not_redacted(chain):
    chain.append({"serial": "ABCD1X"})
    report = enforce(chain, now=time.time())
    assert report.redacted == 0


def test_expired_raw_record_is_redacted(chain):
    now = time.time()
    chain.append({"serial": "ABCD1X", "lat": 43.6})
    _age(chain, 0, 31 * DAY, now)

    report = enforce(chain, now=now)
    assert report.redacted == 1

    entry = next(iter(RecordChain(chain.path)))
    assert entry["record"]["_redacted"] is True
    assert "lat" not in entry["record"]
    assert "serial" not in entry["record"]


def test_redaction_does_not_break_the_chain(chain):
    """The whole point: privacy expiry must not destroy the integrity proof."""
    now = time.time()
    for i in range(5):
        chain.append({"n": i, "serial": f"ABCD1X{i}"})
    for seq in (0, 1, 2):
        _age(chain, seq, 31 * DAY, now)

    enforce(chain, now=now)

    reopened = RecordChain(chain.path)
    assert reopened.verify() == [], "chain must still verify after redaction"


def test_redacted_record_keeps_its_original_hash(chain):
    now = time.time()
    e = chain.append({"secret": "value"})
    original_hash = e["hash"]
    _age(chain, 0, 31 * DAY, now)
    enforce(chain, now=now)

    entry = next(iter(RecordChain(chain.path)))
    assert entry["hash"] == original_hash


def test_published_records_survive_expiry(chain):
    now = time.time()
    chain.append({"n": "raw"}, retention=RetentionClass.RAW)
    chain.append({"n": "published"}, retention=RetentionClass.PUBLISHED)
    _age(chain, 0, 400 * DAY, now)
    _age(chain, 1, 400 * DAY, now)

    report = enforce(chain, now=now)
    assert report.redacted == 1
    assert report.retained_published == 1

    entries = list(RecordChain(chain.path))
    assert entries[0]["record"]["_redacted"] is True
    assert entries[1]["record"] == {"n": "published"}


def test_dry_run_changes_nothing(chain):
    now = time.time()
    chain.append({"n": 0})
    _age(chain, 0, 31 * DAY, now)
    before = chain.path.read_text()

    report = enforce(chain, now=now, dry_run=True)
    assert report.redacted == 1
    assert chain.path.read_text() == before


def test_promote_protects_from_future_expiry(chain):
    now = time.time()
    chain.append({"n": 0})
    assert promote(chain, {0}, note="cited in published analysis") == 1
    _age(chain, 0, 400 * DAY, now)

    report = enforce(chain, now=now)
    assert report.redacted == 0
    assert report.retained_published == 1
    assert RecordChain(chain.path).verify() == []


def test_default_retention_is_30_days():
    assert DEFAULT_RAW_RETENTION_S == 30 * DAY


def test_redaction_is_idempotent(chain):
    now = time.time()
    chain.append({"n": 0})
    _age(chain, 0, 31 * DAY, now)
    enforce(chain, now=now)
    second = enforce(chain, now=now)
    assert second.redacted == 0
    assert second.already_redacted == 1
