from remoteid_sensor.astm.messages import parse_message
from remoteid_sensor.correlate import Correlator
from tests import builders as b

MAC_A = "aa:bb:cc:dd:ee:01"
MAC_B = "aa:bb:cc:dd:ee:02"


def test_location_before_identity_is_retained():
    """At range, position frames routinely arrive before any identity frame."""
    c = Correlator()
    s = c.observe(MAC_A, parse_message(b.location(43.6, -116.2)), received_at=100.0)
    assert not s.is_identified
    assert s.last_latitude is not None

    s = c.observe(MAC_A, parse_message(b.basic_id("1596F123456789ABCDEF")), received_at=101.0)
    assert s.is_identified
    assert s.serial.manufacturer_code == "1596"
    assert s.messages_before_binding == 1


def test_sessions_are_keyed_per_transport_not_merged():
    c = Correlator()
    a = c.observe(MAC_A, parse_message(b.basic_id("ABCD4TEST")), received_at=100.0)
    bb = c.observe(MAC_B, parse_message(b.basic_id("ABCD4TEST")), received_at=100.0)
    assert a.session_id != bb.session_id, "two observations must stay distinguishable"


def test_system_message_captures_operator_position():
    c = Correlator()
    c.observe(MAC_A, parse_message(b.basic_id("ABCD4TEST")), received_at=100.0)
    s = c.observe(MAC_A, parse_message(b.system(43.4666, -116.25)), received_at=101.0)
    assert s.operator_latitude is not None
    assert round(s.operator_latitude, 4) == 43.4666


def test_operator_id_captured():
    c = Correlator()
    s = c.observe(MAC_A, parse_message(b.operator_id("FA3RM7K2QW")), received_at=100.0)
    assert s.operator_id == "FA3RM7K2QW"


def test_idle_session_expires_and_a_new_one_starts():
    c = Correlator(idle_timeout_s=300)
    first = c.observe(MAC_A, parse_message(b.basic_id("ABCD4TEST")), received_at=100.0)
    second = c.observe(MAC_A, parse_message(b.basic_id("ABCD4TEST")), received_at=100.0 + 400)
    assert first.session_id != second.session_id


def test_identity_change_mid_session_is_surfaced_not_silently_resolved():
    c = Correlator()
    c.observe(MAC_A, parse_message(b.basic_id("ABCD4AAAA")), received_at=100.0)
    s = c.observe(MAC_A, parse_message(b.basic_id("ABCD4BBBB")), received_at=101.0)
    assert s.problems
    assert "identity changed mid-session" in s.problems[0]
    assert s.serial.raw == "ABCD4AAAA", "first binding is not silently overwritten"


def test_expire_closes_idle_sessions():
    c = Correlator(idle_timeout_s=300)
    c.observe(MAC_A, parse_message(b.basic_id("ABCD4TEST")), received_at=100.0)
    assert c.expire(now=500.0) != []
    assert c.open_sessions == []


def test_message_count_tracks_all_traffic():
    c = Correlator()
    for i in range(3):
        s = c.observe(MAC_A, parse_message(b.location(43.6, -116.2)), received_at=100.0 + i)
    assert s.message_count == 3
