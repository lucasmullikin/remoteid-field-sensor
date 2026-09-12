from remoteid_sensor.astm.messages import parse_message
from remoteid_sensor.receivers.frames import (build_bluetooth_ad, build_wifi_ie,
                                              extract_from_bluetooth_ad,
                                              extract_from_wifi_ie)
from tests import builders as b

# A realistic AD prefix: Flags structure, then a shortened local name.
FLAGS_AD = bytes([0x02, 0x01, 0x06])
NAME_AD = bytes([0x05, 0x08]) + b"UAV1"

# A realistic IE prefix: SSID element, then Supported Rates.
SSID_IE = bytes([0x00, 0x04]) + b"test"
RATES_IE = bytes([0x01, 0x04, 0x82, 0x84, 0x8B, 0x96])


def test_bluetooth_extract_round_trip():
    msg = b.basic_id("1596F123456789ABCDEF")
    ad = build_bluetooth_ad(msg, message_counter=7)
    got = extract_from_bluetooth_ad(ad)
    assert got is not None
    assert got.payload == msg
    assert got.message_counter == 7
    assert got.transport == "bluetooth"


def test_bluetooth_skips_preceding_structures():
    """Offsets are not fixed; flags and names come first on many transmitters."""
    msg = b.basic_id("ABCD4TEST")
    ad = build_bluetooth_ad(msg, prefix_structures=FLAGS_AD + NAME_AD)
    got = extract_from_bluetooth_ad(ad)
    assert got is not None and got.payload == msg


def test_bluetooth_ignores_unrelated_advertising():
    assert extract_from_bluetooth_ad(FLAGS_AD + NAME_AD) is None


def test_bluetooth_truncated_structure_does_not_read_past_end():
    ad = bytes([0x20, 0x16, 0xFA, 0xFF])   # claims 32 bytes, supplies 2
    assert extract_from_bluetooth_ad(ad) is None


def test_bluetooth_zero_length_terminates():
    assert extract_from_bluetooth_ad(bytes([0x00, 0x16, 0xFA, 0xFF])) is None


def test_wifi_extract_round_trip():
    msg = b.location(43.6, -116.2)
    ie = build_wifi_ie(msg, message_counter=3)
    got = extract_from_wifi_ie(ie)
    assert got is not None
    assert got.payload == msg
    assert got.message_counter == 3
    assert got.transport == "wifi"


def test_wifi_skips_preceding_elements():
    msg = b.basic_id("ABCD4TEST")
    ie = build_wifi_ie(msg, prefix_elements=SSID_IE + RATES_IE)
    got = extract_from_wifi_ie(ie)
    assert got is not None and got.payload == msg


def test_wifi_ignores_unrelated_elements():
    assert extract_from_wifi_ie(SSID_IE + RATES_IE) is None


def test_wifi_truncated_element_does_not_read_past_end():
    assert extract_from_wifi_ie(bytes([0xDD, 0x40, 0xFA, 0x0B, 0xBC])) is None


def test_end_to_end_bluetooth_to_decoded_message():
    """Envelope to decoded field, the whole software path minus the radio."""
    ad = build_bluetooth_ad(b.basic_id("1596F123456789ABCDEF"),
                            prefix_structures=FLAGS_AD)
    got = extract_from_bluetooth_ad(ad)
    msg = parse_message(got.payload)
    assert msg.payload.uas_id == "1596F123456789ABCDEF"


def test_end_to_end_wifi_message_pack():
    pack = b.message_pack(b.basic_id("ABCD4TEST"), b.location(43.6, -116.2))
    ie = build_wifi_ie(pack, prefix_elements=SSID_IE)
    got = extract_from_wifi_ie(ie)
    assert got.payload == pack


def test_wifi_receiver_refuses_a_2ghz_only_channel_list():
    """Skydio broadcasts on 5 GHz only; a 2.4-only sensor reports a false empty sky."""
    import pytest

    from remoteid_sensor.liveness import ReceiverCounters
    from remoteid_sensor.receivers.wifi import WifiReceiver

    with pytest.raises(ValueError, match="silently blind to 5 GHz"):
        WifiReceiver("wlan1", ReceiverCounters(name="wifi"), channels=[1, 6, 11])


def test_wifi_receiver_accepts_a_dual_band_channel_list():
    from remoteid_sensor.liveness import ReceiverCounters
    from remoteid_sensor.receivers.wifi import WifiReceiver

    rx = WifiReceiver("wlan1", ReceiverCounters(name="wifi"), channels=[1, 36, 149])
    assert 149 in rx.channels
