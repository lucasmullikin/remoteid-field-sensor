"""Synthetic F3411 message builders, used only by tests.

These construct byte-exact messages so the parser can be checked against known
input. They are deliberately separate from the parser: a test that encodes with
the parser's own logic proves only that it is self-consistent.
"""

from __future__ import annotations

import struct

from remoteid_sensor.astm.messages import F3411_EPOCH_UNIX, MESSAGE_SIZE


def _pad(body: bytes) -> bytes:
    assert len(body) <= 24, f"body too long: {len(body)}"
    return body + b"\x00" * (24 - len(body))


def header(msg_type: int, version: int = 2) -> bytes:
    return bytes([((msg_type & 0x0F) << 4) | (version & 0x0F)])


def basic_id(uas_id: str, id_type: int = 1, ua_type: int = 2) -> bytes:
    body = bytes([((id_type & 0x0F) << 4) | (ua_type & 0x0F)])
    body += uas_id.encode("ascii").ljust(20, b"\x00")[:20]
    return header(0x0) + _pad(body)


def location(lat: float, lon: float, *, status: int = 2, track: int = 90,
             speed_raw: int = 40, geodetic_alt_m: float = 120.0,
             timestamp_tenths: int = 1234) -> bytes:
    flags = ((status & 0x0F) << 4)
    body = bytes([flags, track, speed_raw, 0])
    body += struct.pack("<ii", int(round(lat * 1e7)), int(round(lon * 1e7)))
    alt_raw = int(round((geodetic_alt_m + 1000.0) / 0.5))
    body += struct.pack("<HHH", 0, alt_raw, 0)
    body += bytes([0x00, 0x00])
    body += struct.pack("<H", timestamp_tenths)
    body += bytes([0x00, 0x00])
    return header(0x1) + _pad(body)


def system(op_lat: float, op_lon: float, *, unix_time: int | None = None,
           area_count: int = 1, area_radius_10m: int = 5) -> bytes:
    body = bytes([0x01])
    body += struct.pack("<ii", int(round(op_lat * 1e7)), int(round(op_lon * 1e7)))
    body += struct.pack("<H", area_count)
    body += bytes([area_radius_10m])
    body += struct.pack("<HH", 0, 0)
    body += bytes([0x00])
    body += struct.pack("<H", 0)
    ts = 0 if unix_time is None else (unix_time - F3411_EPOCH_UNIX)
    body += struct.pack("<I", ts)
    return header(0x4) + _pad(body)


def operator_id(op_id: str) -> bytes:
    body = bytes([0x00]) + op_id.encode("ascii").ljust(20, b"\x00")[:20]
    return header(0x5) + _pad(body)


def self_id(text: str) -> bytes:
    body = bytes([0x00]) + text.encode("ascii").ljust(23, b"\x00")[:23]
    return header(0x3) + _pad(body)


def message_pack(*messages: bytes) -> bytes:
    for m in messages:
        assert len(m) == MESSAGE_SIZE
    return header(0xF) + bytes([MESSAGE_SIZE, len(messages)]) + b"".join(messages)
