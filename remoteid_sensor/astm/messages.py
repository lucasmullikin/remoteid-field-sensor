"""ASTM F3411 Remote ID message parsing.

Every Remote ID message is exactly 25 bytes: one header byte followed by a
24-byte body. This module decodes the message types that carry the fields
docs/DATA-POLICY.md permits this project to record, and deliberately does not
decode anything else.

Field scaling and offsets follow ASTM F3411-22. Where a field's interpretation
could not be independently confirmed it is surfaced as a raw value and marked
in the docstring rather than guessed at, matching the TBC convention used in
hardware/BOM.md.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

MESSAGE_SIZE = 25
BODY_SIZE = 24

#: Altitude, ceiling and floor fields share one encoding: 0.5 m resolution
#: with a -1000 m offset.
_ALT_SCALE = 0.5
_ALT_OFFSET = -1000.0

#: F3411 System-message timestamps count seconds from this epoch, not the Unix
#: epoch. Getting this wrong silently shifts every operator record by decades.
F3411_EPOCH_UNIX = 1546300800  # 2019-01-01T00:00:00Z

#: Sentinel meaning "the transmitter did not supply this value".
INVALID_ALT_RAW = 0
INVALID_LATLON = 0


class MessageType(IntEnum):
    BASIC_ID = 0x0
    LOCATION = 0x1
    AUTH = 0x2
    SELF_ID = 0x3
    SYSTEM = 0x4
    OPERATOR_ID = 0x5
    MESSAGE_PACK = 0xF


class IDType(IntEnum):
    NONE = 0
    SERIAL_NUMBER = 1        # ANSI/CTA-2063-A
    CAA_REGISTRATION = 2
    UTM_ASSIGNED_UUID = 3
    SPECIFIC_SESSION_ID = 4


class UAType(IntEnum):
    NONE = 0
    AEROPLANE = 1
    ROTORCRAFT = 2           # helicopter or multirotor
    GYROPLANE = 3
    HYBRID_LIFT = 4
    ORNITHOPTER = 5
    GLIDER = 6
    KITE = 7
    FREE_BALLOON = 8
    CAPTIVE_BALLOON = 9
    AIRSHIP = 10
    FREE_FALL_PARACHUTE = 11
    ROCKET = 12
    TETHERED_POWERED = 13
    GROUND_OBSTACLE = 14
    OTHER = 15


class OperationalStatus(IntEnum):
    UNDECLARED = 0
    GROUND = 1
    AIRBORNE = 2
    EMERGENCY = 3
    REMOTE_ID_SYSTEM_FAILURE = 4


class ParseError(ValueError):
    """Raised when a buffer cannot be a valid F3411 message."""


def _ascii_field(raw: bytes) -> str:
    """Decode a fixed-width ASCII field, stripping NUL and space padding.

    Transmitters pad inconsistently; some use NUL, some use spaces, some send
    trailing garbage after the NUL. Anything undecodable is dropped rather than
    substituted, so a mangled ID never silently becomes a plausible one.
    """
    cut = raw.split(b"\x00", 1)[0]
    return cut.decode("ascii", errors="ignore").strip()


def _altitude(raw: int) -> float | None:
    if raw == INVALID_ALT_RAW:
        return None
    return raw * _ALT_SCALE + _ALT_OFFSET


def _latlon(raw: int) -> float | None:
    """Scale an F3411 int32 coordinate to degrees.

    Exactly zero is the "not supplied" sentinel. Null Island is not a place a
    drone flies, and treating 0 as a real fix would plant every unsupplied
    position off the coast of Ghana.
    """
    if raw == INVALID_LATLON:
        return None
    return raw * 1e-7


@dataclass(frozen=True)
class BasicID:
    """Message 0x0 - identity. Carries the CTA-2063-A serial."""
    id_type: int
    ua_type: int
    uas_id: str

    @property
    def is_serial_number(self) -> bool:
        return self.id_type == IDType.SERIAL_NUMBER


@dataclass(frozen=True)
class Location:
    """Message 0x1 - aircraft position and vector."""
    status: int
    track_deg: int | None
    speed_ms: float | None
    vertical_speed_ms: float | None
    latitude: float | None
    longitude: float | None
    pressure_altitude_m: float | None
    geodetic_altitude_m: float | None
    height_m: float | None
    height_is_agl: bool
    horizontal_accuracy: int
    vertical_accuracy: int
    speed_accuracy: int
    timestamp_tenths: int
    timestamp_accuracy: int


@dataclass(frozen=True)
class SelfID:
    """Message 0x3 - free-text description supplied by the operator."""
    description_type: int
    description: str


@dataclass(frozen=True)
class System:
    """Message 0x4 - operator ground-station position.

    This is the message that makes the project work: it is the mandatory
    launch-site position, which is what lets an observed flight be matched
    against a published flight record.
    """
    operator_location_type: int
    classification_type: int
    operator_latitude: float | None
    operator_longitude: float | None
    area_count: int
    area_radius_m: int
    area_ceiling_m: float | None
    area_floor_m: float | None
    operator_altitude_m: float | None
    timestamp_unix: int | None


@dataclass(frozen=True)
class OperatorID:
    """Message 0x5 - the operator's CAA-issued registration ID."""
    operator_id_type: int
    operator_id: str


@dataclass(frozen=True)
class Auth:
    """Message 0x2 - authentication pages.

    Recorded as opaque bytes. This project does not attempt to verify or break
    authentication; see docs/LEGAL-POSTURE.md.
    """
    auth_type: int
    page_number: int
    last_page_index: int | None
    length: int | None
    timestamp_unix: int | None
    data: bytes


@dataclass(frozen=True)
class Message:
    """One decoded F3411 message."""
    message_type: int
    protocol_version: int
    payload: Any
    raw: bytes = field(repr=False)


def parse_message(buf: bytes) -> Message:
    """Decode a single 25-byte F3411 message."""
    if len(buf) != MESSAGE_SIZE:
        raise ParseError(f"message must be {MESSAGE_SIZE} bytes, got {len(buf)}")

    header = buf[0]
    msg_type = (header >> 4) & 0x0F
    version = header & 0x0F
    body = buf[1:]

    decoder = _DECODERS.get(msg_type)
    payload = decoder(body) if decoder else None
    return Message(message_type=msg_type, protocol_version=version,
                   payload=payload, raw=buf)


def parse_message_pack(buf: bytes) -> list[Message]:
    """Decode a 0xF message pack into its constituent messages.

    A pack declares its own element size and count; both are validated against
    the buffer instead of trusted, because a malformed count is the easiest way
    to make a parser read structure that is not there.
    """
    if len(buf) < 3:
        raise ParseError("message pack too short for its header")

    header = buf[0]
    if ((header >> 4) & 0x0F) != MessageType.MESSAGE_PACK:
        raise ParseError("not a message pack")

    msg_size = buf[1]
    count = buf[2]

    if msg_size != MESSAGE_SIZE:
        raise ParseError(f"pack declares {msg_size}-byte messages, expected {MESSAGE_SIZE}")
    if not 1 <= count <= 9:
        raise ParseError(f"pack declares {count} messages, outside 1..9")

    expected = 3 + count * MESSAGE_SIZE
    if len(buf) < expected:
        raise ParseError(f"pack declares {count} messages but buffer holds {len(buf)} bytes")

    return [parse_message(buf[3 + i * MESSAGE_SIZE: 3 + (i + 1) * MESSAGE_SIZE])
            for i in range(count)]


def _decode_basic_id(b: bytes) -> BasicID:
    return BasicID(id_type=(b[0] >> 4) & 0x0F,
                   ua_type=b[0] & 0x0F,
                   uas_id=_ascii_field(b[1:21]))


def _decode_location(b: bytes) -> Location:
    flags = b[0]
    status = (flags >> 4) & 0x0F
    height_is_agl = bool((flags >> 2) & 0x01)
    ew_segment = bool((flags >> 1) & 0x01)
    speed_multiplier = flags & 0x01

    track_raw = b[1]
    track = track_raw + 180 if ew_segment else track_raw
    track_deg = track if track < 360 else None

    # Speed uses a split encoding: a fine 0.25 m/s scale below the break, and a
    # coarse 0.75 m/s scale above it that resumes where the fine scale ended.
    speed_raw = b[2]
    if speed_multiplier == 0:
        speed_ms = speed_raw * 0.25
    else:
        speed_ms = speed_raw * 0.75 + (255 * 0.25)
    if speed_raw == 255:
        speed_ms = None

    vs_raw = struct.unpack_from("<b", b, 3)[0]
    vertical_speed_ms = None if vs_raw == 63 else vs_raw * 0.5

    lat_raw, lon_raw = struct.unpack_from("<ii", b, 4)
    press_raw, geo_raw, height_raw = struct.unpack_from("<HHH", b, 12)

    return Location(
        status=status,
        track_deg=track_deg,
        speed_ms=speed_ms,
        vertical_speed_ms=vertical_speed_ms,
        latitude=_latlon(lat_raw),
        longitude=_latlon(lon_raw),
        pressure_altitude_m=_altitude(press_raw),
        geodetic_altitude_m=_altitude(geo_raw),
        height_m=_altitude(height_raw),
        height_is_agl=height_is_agl,
        horizontal_accuracy=b[18] & 0x0F,
        vertical_accuracy=(b[18] >> 4) & 0x0F,
        speed_accuracy=b[19] & 0x0F,
        timestamp_tenths=struct.unpack_from("<H", b, 20)[0],
        timestamp_accuracy=b[22] & 0x0F,
    )


def _decode_self_id(b: bytes) -> SelfID:
    return SelfID(description_type=b[0], description=_ascii_field(b[1:24]))


def _decode_system(b: bytes) -> System:
    lat_raw, lon_raw = struct.unpack_from("<ii", b, 1)
    area_count = struct.unpack_from("<H", b, 9)[0]
    ceiling_raw, floor_raw = struct.unpack_from("<HH", b, 12)
    operator_alt_raw = struct.unpack_from("<H", b, 17)[0]
    ts_raw = struct.unpack_from("<I", b, 19)[0]

    return System(
        operator_location_type=b[0] & 0x07,
        classification_type=(b[0] >> 3) & 0x03,
        operator_latitude=_latlon(lat_raw),
        operator_longitude=_latlon(lon_raw),
        area_count=area_count,
        area_radius_m=b[11] * 10,
        area_ceiling_m=_altitude(ceiling_raw),
        area_floor_m=_altitude(floor_raw),
        operator_altitude_m=_altitude(operator_alt_raw),
        timestamp_unix=(ts_raw + F3411_EPOCH_UNIX) if ts_raw else None,
    )


def _decode_operator_id(b: bytes) -> OperatorID:
    return OperatorID(operator_id_type=b[0], operator_id=_ascii_field(b[1:21]))


def _decode_auth(b: bytes) -> Auth:
    auth_type = (b[0] >> 4) & 0x0F
    page = b[0] & 0x0F
    if page == 0:
        ts_raw = struct.unpack_from("<I", b, 3)[0]
        return Auth(auth_type=auth_type, page_number=page,
                    last_page_index=b[1], length=b[2],
                    timestamp_unix=(ts_raw + F3411_EPOCH_UNIX) if ts_raw else None,
                    data=bytes(b[7:24]))
    return Auth(auth_type=auth_type, page_number=page, last_page_index=None,
                length=None, timestamp_unix=None, data=bytes(b[1:24]))


_DECODERS = {
    MessageType.BASIC_ID: _decode_basic_id,
    MessageType.LOCATION: _decode_location,
    MessageType.AUTH: _decode_auth,
    MessageType.SELF_ID: _decode_self_id,
    MessageType.SYSTEM: _decode_system,
    MessageType.OPERATOR_ID: _decode_operator_id,
}
