"""Command-line entry points."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from .liveness import ReceiverCounters
from .pipeline import Pipeline, SensorPosition
from .store.chain import RecordChain
from .store.retention import DEFAULT_RAW_RETENTION_S, enforce, promote


def cmd_verify(args) -> int:
    chain = RecordChain(args.store)
    breaks = chain.verify()
    total = sum(1 for _ in chain)

    if not breaks:
        print(f"OK: {total} records, chain intact, head {chain.head_hash[:16]}...")
        return 0

    print(f"FAIL: {len(breaks)} break(s) in {total} records", file=sys.stderr)
    for b in breaks[:20]:
        print(f"  seq {b.seq}: {b.reason}", file=sys.stderr)
        print(f"    expected {b.expected[:32]}", file=sys.stderr)
        print(f"    found    {b.found[:32]}", file=sys.stderr)
    return 1


def cmd_retention(args) -> int:
    chain = RecordChain(args.store)
    report = enforce(chain, max_age_s=args.max_age_days * 86400,
                     dry_run=args.dry_run)
    prefix = "DRY RUN: " if args.dry_run else ""
    print(f"{prefix}{report.summary()}")

    if not args.dry_run and report.redacted:
        breaks = RecordChain(args.store).verify()
        if breaks:
            print("ERROR: chain broken by retention pass", file=sys.stderr)
            return 1
        print("chain still verifies after redaction")
    return 0


def cmd_promote(args) -> int:
    chain = RecordChain(args.store)
    n = promote(chain, set(args.seq), note=args.note)
    print(f"promoted {n} record(s) to PUBLISHED (never auto-expired)")
    return 0


def cmd_stats(args) -> int:
    chain = RecordChain(args.store)
    counts: dict[str, int] = {}
    serials: set[str] = set()
    sessions: set[str] = set()

    for entry in chain:
        rec = entry["record"]
        kind = "redacted" if rec.get("_redacted") else rec.get("type", "unknown")
        counts[kind] = counts.get(kind, 0) + 1
        if rec.get("serial", {}).get("raw"):
            serials.add(rec["serial"]["raw"])
        if rec.get("session_id"):
            sessions.add(rec["session_id"])

    print(json.dumps({
        "records": sum(counts.values()),
        "by_type": counts,
        "distinct_serials": len(serials),
        "distinct_sessions": len(sessions),
        "head_hash": chain.head_hash,
    }, indent=2))
    return 0


def cmd_selftest(args) -> int:
    """Prove the software path end to end with no radio attached.

    Writes synthetic records to a scratch store, then verifies the chain. This
    is what to run before a deployment to confirm the recording path works;
    it says nothing about whether the radios can hear.
    """
    from tests import builders as b  # test-only helpers

    path = Path(args.store)
    pipeline = Pipeline(RecordChain(path), sensor_id=args.sensor_id)
    pipeline.register_receiver("wifi")
    pos = SensorPosition(latitude=43.6150, longitude=-116.2023)

    pipeline.ingest(transport_address="aa:bb:cc:dd:ee:01",
                    payload=b.message_pack(b.basic_id("1596F123456789ABCDEF"),
                                           b.location(43.6, -116.2),
                                           b.system(43.4666, -116.25)),
                    transport="wifi", message_counter=1, sensor_position=pos)
    pipeline.receivers["wifi"].interface_up = True
    pipeline.receivers["wifi"].note_frame()
    pipeline.heartbeat(pos)

    breaks = pipeline.chain.verify()
    if breaks:
        print(f"SELFTEST FAILED: {len(breaks)} chain break(s)", file=sys.stderr)
        return 1
    print(f"SELFTEST OK: {sum(1 for _ in pipeline.chain)} records written to {path}, "
          f"chain verifies")
    print("NOTE: this proves the recording path only. It proves nothing about "
          "radio reception.")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="remoteid-sensor",
                                description="Receive-only ASTM F3411 Remote ID field sensor")
    p.add_argument("--store", default="records.jsonl", help="path to the record chain")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("verify", help="verify the record chain is intact").set_defaults(func=cmd_verify)

    r = sub.add_parser("retention", help="apply the retention policy by redaction")
    r.add_argument("--max-age-days", type=float, default=DEFAULT_RAW_RETENTION_S / 86400)
    r.add_argument("--dry-run", action="store_true")
    r.set_defaults(func=cmd_retention)

    pr = sub.add_parser("promote", help="mark records PUBLISHED so they never expire")
    pr.add_argument("seq", type=int, nargs="+")
    pr.add_argument("--note", required=True, help="why these records are being retained")
    pr.set_defaults(func=cmd_promote)

    sub.add_parser("stats", help="summarise a record store").set_defaults(func=cmd_stats)

    st = sub.add_parser("selftest", help="exercise the recording path with no radio")
    st.add_argument("--sensor-id", default="selftest")
    st.set_defaults(func=cmd_selftest)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
