"""ANSI/CTA-2063-A serial number decoding.

A compliant Remote ID serial is structured, not opaque:

    MMMM  L  SSSSSSSSSSSSSSS
    |     |  |
    |     |  +-- manufacturer serial, 1..15 chars
    |     +----- length code: '1'..'9' = 1..9, 'A'..'F' = 10..15
    +----------- 4-char manufacturer code assigned by ANSI

The manufacturer code is the useful part for this project: it identifies the
airframe maker from the broadcast alone, without reference to any registry.

A serial that fails validation here is still recorded. This module reports
what it found; it never decides that evidence should be discarded. A validator
that silently drops non-conforming input is indistinguishable from a validator
that is simply wrong about the spec.
"""

from __future__ import annotations

from dataclasses import dataclass

MFR_CODE_LEN = 4
LENGTH_CODE_POS = 4

#: CTA-2063-A excludes I, O and Q from the serial character set so they cannot
#: be confused with 1 and 0. Treated as advisory: a violation is flagged, not
#: grounds for rejection.
_EXCLUDED = frozenset("IOQ")
_ALLOWED = frozenset("0123456789ABCDEFGHJKLMNPRSTUVWXYZ")


@dataclass(frozen=True)
class SerialNumber:
    """The result of attempting a CTA-2063-A decode.

    `valid` means the string parsed cleanly as CTA-2063-A. `raw` is always
    preserved verbatim regardless.
    """
    raw: str
    manufacturer_code: str | None
    declared_length: int | None
    manufacturer_serial: str | None
    valid: bool
    problems: tuple[str, ...]

    def as_record(self) -> dict:
        return {
            "raw": self.raw,
            "manufacturer_code": self.manufacturer_code,
            "manufacturer_serial": self.manufacturer_serial,
            "cta2063a_valid": self.valid,
            "problems": list(self.problems),
        }


def _decode_length_code(ch: str) -> int | None:
    if "1" <= ch <= "9":
        return int(ch)
    if "A" <= ch <= "F":
        return ord(ch) - ord("A") + 10
    return None


def parse_serial(raw: str) -> SerialNumber:
    """Decode a UAS ID as a CTA-2063-A serial, reporting rather than raising."""
    problems: list[str] = []

    if not raw:
        return SerialNumber(raw=raw, manufacturer_code=None, declared_length=None,
                            manufacturer_serial=None, valid=False,
                            problems=("empty",))

    if len(raw) < MFR_CODE_LEN + 2:
        return SerialNumber(raw=raw, manufacturer_code=None, declared_length=None,
                            manufacturer_serial=None, valid=False,
                            problems=(f"too short for CTA-2063-A ({len(raw)} chars)",))

    mfr = raw[:MFR_CODE_LEN]
    length = _decode_length_code(raw[LENGTH_CODE_POS])
    serial = raw[LENGTH_CODE_POS + 1:]

    if length is None:
        problems.append(f"length code {raw[LENGTH_CODE_POS]!r} is not 1-9 or A-F")
    elif len(serial) != length:
        problems.append(f"declared length {length} but {len(serial)} chars follow")

    bad = sorted(set(raw) - _ALLOWED)
    if bad:
        excluded = sorted(set(raw) & _EXCLUDED)
        if excluded:
            problems.append(f"contains excluded characters {''.join(excluded)}")
        other = [c for c in bad if c not in _EXCLUDED]
        if other:
            problems.append(f"contains out-of-charset characters {''.join(other)!r}")

    valid = not problems
    return SerialNumber(
        raw=raw,
        manufacturer_code=mfr if valid else (mfr if length is not None else None),
        declared_length=length,
        manufacturer_serial=serial if valid else None,
        valid=valid,
        problems=tuple(problems),
    )
