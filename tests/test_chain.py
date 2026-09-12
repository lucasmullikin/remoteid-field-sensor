import json

import pytest

from remoteid_sensor.store.chain import (GENESIS_PREV_HASH, ChainError,
                                         RecordChain, RetentionClass,
                                         canonical_json, compute_hash)


@pytest.fixture
def chain(tmp_path):
    return RecordChain(tmp_path / "records.jsonl")


def test_empty_chain_verifies(chain):
    assert chain.verify() == []
    assert chain.head_hash == GENESIS_PREV_HASH


def test_append_links_to_genesis(chain):
    e = chain.append({"type": "detection", "serial": "ABCD1X"})
    assert e["seq"] == 0
    assert e["prev_hash"] == GENESIS_PREV_HASH
    assert chain.verify() == []


def test_chain_links_sequentially(chain):
    a = chain.append({"n": 1})
    b = chain.append({"n": 2})
    c = chain.append({"n": 3})
    assert b["prev_hash"] == a["hash"]
    assert c["prev_hash"] == b["hash"]
    assert chain.verify() == []


def test_edited_record_is_detected(chain):
    chain.append({"serial": "ABCD1X", "lat": 43.6})
    chain.append({"serial": "ABCD1X", "lat": 43.7})

    lines = chain.path.read_text().splitlines()
    entry = json.loads(lines[0])
    entry["record"]["lat"] = 99.9           # the doctored value
    lines[0] = canonical_json(entry)
    chain.path.write_text("\n".join(lines) + "\n")

    breaks = RecordChain(chain.path).verify()
    assert breaks, "a doctored record must not verify"
    assert any("does not match its hash" in b.reason for b in breaks)


def test_deleted_record_is_detected(chain):
    for i in range(4):
        chain.append({"n": i})

    lines = chain.path.read_text().splitlines()
    del lines[1]                              # excise one record
    chain.path.write_text("\n".join(lines) + "\n")

    breaks = RecordChain(chain.path).verify()
    assert breaks, "a deleted record must not verify"
    assert any(b.reason in ("sequence gap or reorder",
                            "prev_hash does not match preceding record")
               for b in breaks)


def test_reordered_records_are_detected(chain):
    for i in range(3):
        chain.append({"n": i})

    lines = chain.path.read_text().splitlines()
    lines[0], lines[1] = lines[1], lines[0]
    chain.path.write_text("\n".join(lines) + "\n")

    assert RecordChain(chain.path).verify()


def test_appended_forgery_is_detected(chain):
    chain.append({"n": 0})
    forged = {"seq": 1, "prev_hash": "0" * 64, "hash": "f" * 64,
              "written_at": 0.0, "retention": "raw", "record": {"n": 1}}
    with chain.path.open("a") as fh:
        fh.write(canonical_json(forged) + "\n")

    assert RecordChain(chain.path).verify()


def test_verify_or_raise(chain):
    chain.append({"n": 0})
    chain.verify_or_raise()

    lines = chain.path.read_text().splitlines()
    e = json.loads(lines[0])
    e["record"]["n"] = 99
    chain.path.write_text(canonical_json(e) + "\n")

    with pytest.raises(ChainError, match="chain broken at seq 0"):
        RecordChain(chain.path).verify_or_raise()


def test_reopen_resumes_sequence(chain):
    chain.append({"n": 0})
    chain.append({"n": 1})
    reopened = RecordChain(chain.path)
    assert reopened.next_seq == 2
    e = reopened.append({"n": 2})
    assert e["seq"] == 2
    assert reopened.verify() == []


def test_canonical_json_is_key_order_independent():
    assert canonical_json({"b": 1, "a": 2}) == canonical_json({"a": 2, "b": 1})


def test_hash_is_reproducible():
    r = {"serial": "ABCD1X", "lat": 43.6}
    assert compute_hash(0, GENESIS_PREV_HASH, r) == compute_hash(0, GENESIS_PREV_HASH, r)


def test_retention_class_recorded(chain):
    e = chain.append({"n": 0}, retention=RetentionClass.PUBLISHED)
    assert e["retention"] == "published"
