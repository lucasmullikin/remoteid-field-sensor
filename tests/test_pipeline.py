import time

from remoteid_sensor.pipeline import Pipeline, SensorPosition
from remoteid_sensor.store.chain import RecordChain
from tests import builders as b

POS = SensorPosition(latitude=43.6150, longitude=-116.2023, altitude_m=824.0,
                     fix_quality="3d", gnss_time_unix=1757000000.0)
MAC = "aa:bb:cc:dd:ee:01"


def _pipeline(tmp_path):
    p = Pipeline(RecordChain(tmp_path / "records.jsonl"), sensor_id="sensor-01")
    p.register_receiver("bluetooth")
    p.register_receiver("wifi")
    return p


def test_detection_is_recorded_and_chain_verifies(tmp_path):
    p = _pipeline(tmp_path)
    written = p.ingest(transport_address=MAC, payload=b.basic_id("1596F123456789ABCDEF"),
                       transport="bluetooth", message_counter=1,
                       sensor_position=POS, received_at=1000.0, rssi_dbm=-72)
    assert len(written) == 1
    assert p.chain.verify() == []
    rec = written[0]["record"]
    assert rec["type"] == "detection"
    assert rec["sensor_id"] == "sensor-01"
    assert rec["serial"]["manufacturer_code"] == "1596"
    assert rec["rssi_dbm"] == -72


def test_both_clocks_recorded_separately(tmp_path):
    p = _pipeline(tmp_path)
    claimed = 1_757_000_500
    written = p.ingest(transport_address=MAC, payload=b.system(43.4, -116.2, unix_time=claimed),
                       transport="wifi", message_counter=1,
                       sensor_position=POS, received_at=1_757_000_000.0)
    rec = written[0]["record"]
    assert rec["sensor_time_unix"] == 1_757_000_000.0
    assert rec["transmitter_time_unix"] == claimed
    assert rec["clock_delta_s"] == 500


def test_sensor_position_recorded_at_full_precision(tmp_path):
    p = _pipeline(tmp_path)
    written = p.ingest(transport_address=MAC, payload=b.basic_id("ABCD4TEST"),
                       transport="wifi", message_counter=0,
                       sensor_position=POS, received_at=1000.0)
    pos = written[0]["record"]["sensor_position"]
    assert pos["latitude"] == 43.6150
    assert pos["longitude"] == -116.2023


def test_message_pack_writes_one_record_per_message(tmp_path):
    p = _pipeline(tmp_path)
    pack = b.message_pack(b.basic_id("ABCD4TEST"), b.location(43.6, -116.2),
                          b.system(43.4, -116.2))
    written = p.ingest(transport_address=MAC, payload=pack, transport="wifi",
                       message_counter=2, sensor_position=POS, received_at=1000.0)
    assert len(written) == 3
    assert p.chain.verify() == []


def test_undecodable_payload_is_still_recorded_with_raw_bytes(tmp_path):
    """A parser found wrong later must be re-runnable against what arrived."""
    p = _pipeline(tmp_path)
    written = p.ingest(transport_address=MAC, payload=b"\xff\xff", transport="wifi",
                       message_counter=0, sensor_position=POS, received_at=1000.0)
    rec = written[0]["record"]
    assert rec["type"] == "undecodable"
    assert rec["raw_hex"] == "ffff"
    assert p.chain.verify() == []


def test_raw_hex_retained_on_every_detection(tmp_path):
    p = _pipeline(tmp_path)
    written = p.ingest(transport_address=MAC, payload=b.basic_id("ABCD4TEST"),
                       transport="wifi", message_counter=0,
                       sensor_position=POS, received_at=1000.0)
    assert len(bytes.fromhex(written[0]["record"]["raw_hex"])) == 25


def test_heartbeat_written_into_the_same_chain(tmp_path):
    p = _pipeline(tmp_path)
    p.receivers["wifi"].interface_up = True
    p.receivers["wifi"].note_frame()
    p.receivers["bluetooth"].interface_up = True
    p.receivers["bluetooth"].note_frame()
    entry = p.heartbeat(POS, now=1000.0)
    assert entry["record"]["type"] == "heartbeat"
    assert entry["record"]["coverage_claim_permitted"] is True
    assert p.chain.verify() == []


def test_position_before_identity_then_bound(tmp_path):
    p = _pipeline(tmp_path)
    p.ingest(transport_address=MAC, payload=b.location(43.6, -116.2), transport="wifi",
             message_counter=0, sensor_position=POS, received_at=1000.0)
    written = p.ingest(transport_address=MAC, payload=b.basic_id("1596F123456789ABCDEF"),
                       transport="wifi", message_counter=1,
                       sensor_position=POS, received_at=1001.0)
    entries = list(p.chain)
    assert entries[0]["record"]["identified_at_receive_time"] is False
    assert entries[1]["record"]["identified_at_receive_time"] is True
    assert entries[0]["record"]["session_id"] == entries[1]["record"]["session_id"]
