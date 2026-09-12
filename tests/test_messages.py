import struct

import pytest

from remoteid_sensor.astm import messages as m
from tests import builders as b


def test_basic_id_round_trip():
    msg = m.parse_message(b.basic_id("1596FABCDEF123456", ua_type=2))
    assert msg.message_type == m.MessageType.BASIC_ID
    assert msg.payload.uas_id == "1596FABCDEF123456"
    assert msg.payload.is_serial_number
    assert msg.payload.ua_type == m.UAType.ROTORCRAFT


def test_basic_id_strips_nul_padding_not_content():
    msg = m.parse_message(b.basic_id("ABC"))
    assert msg.payload.uas_id == "ABC"


def test_location_decodes_coordinates():
    msg = m.parse_message(b.location(43.6150, -116.2023))
    loc = msg.payload
    assert loc.latitude == pytest.approx(43.6150, abs=1e-6)
    assert loc.longitude == pytest.approx(-116.2023, abs=1e-6)
    assert loc.geodetic_altitude_m == pytest.approx(120.0, abs=0.5)
    assert loc.status == m.OperationalStatus.AIRBORNE


def test_zero_coordinates_are_not_null_island():
    """0/0 is the 'not supplied' sentinel, not a position off Ghana."""
    msg = m.parse_message(b.location(0.0, 0.0))
    assert msg.payload.latitude is None
    assert msg.payload.longitude is None


def test_unsupplied_altitude_is_none_not_negative_1000m():
    msg = m.parse_message(b.location(43.6, -116.2, geodetic_alt_m=-1000.0))
    assert msg.payload.pressure_altitude_m is None


def test_speed_fine_scale():
    msg = m.parse_message(b.location(43.6, -116.2, speed_raw=40))
    assert msg.payload.speed_ms == pytest.approx(10.0)


def test_system_message_carries_operator_position():
    ts = 1757000000
    msg = m.parse_message(b.system(43.4666, -116.2500, unix_time=ts))
    sysm = msg.payload
    assert sysm.operator_latitude == pytest.approx(43.4666, abs=1e-6)
    assert sysm.operator_longitude == pytest.approx(-116.2500, abs=1e-6)
    assert sysm.timestamp_unix == ts
    assert sysm.area_radius_m == 50


def test_system_timestamp_uses_f3411_epoch_not_unix():
    """A raw 0 means 'not supplied'; a real value must be offset by the 2019 epoch."""
    expected = m.F3411_EPOCH_UNIX + 1000
    msg = m.parse_message(b.system(43.4, -116.2, unix_time=expected))
    assert msg.payload.timestamp_unix == expected
    assert msg.payload.timestamp_unix > 1_500_000_000


def test_operator_id_round_trip():
    msg = m.parse_message(b.operator_id("FA3RM7K2QW"))
    assert msg.payload.operator_id == "FA3RM7K2QW"


def test_self_id_round_trip():
    msg = m.parse_message(b.self_id("survey flight"))
    assert msg.payload.description == "survey flight"


def test_message_pack_unpacks_all_members():
    pack = b.message_pack(
        b.basic_id("1596FABCDEF123456"),
        b.location(43.6, -116.2),
        b.system(43.4, -116.2),
    )
    msgs = m.parse_message_pack(pack)
    assert [x.message_type for x in msgs] == [
        m.MessageType.BASIC_ID, m.MessageType.LOCATION, m.MessageType.SYSTEM]
    assert msgs[0].payload.uas_id == "1596FABCDEF123456"


def test_pack_with_lying_count_is_rejected_not_read_past_end():
    pack = bytearray(b.message_pack(b.basic_id("ABC1DEF")))
    pack[2] = 9  # claim nine messages, supply one
    with pytest.raises(m.ParseError, match="declares 9 messages"):
        m.parse_message_pack(bytes(pack))


def test_pack_with_wrong_element_size_is_rejected():
    pack = bytearray(b.message_pack(b.basic_id("ABC1DEF")))
    pack[1] = 24
    with pytest.raises(m.ParseError, match="declares 24-byte"):
        m.parse_message_pack(bytes(pack))


def test_wrong_length_message_rejected():
    with pytest.raises(m.ParseError, match="must be 25 bytes"):
        m.parse_message(b"\x00" * 24)


def test_unknown_message_type_kept_with_raw_not_discarded():
    """An unrecognised type must still be recorded; the spec grows."""
    msg = m.parse_message(b.header(0x9) + b"\x00" * 24)
    assert msg.message_type == 0x9
    assert msg.payload is None
    assert len(msg.raw) == 25
