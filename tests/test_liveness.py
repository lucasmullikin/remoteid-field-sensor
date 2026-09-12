from remoteid_sensor.liveness import (ReceiverCounters, ReceiverState,
                                      heartbeat_record, window_is_provable)


def _hb(t, state):
    return {"sensor_time_unix": t, "overall_state": state}


def test_receiver_up_with_traffic_is_healthy():
    r = ReceiverCounters(name="wifi", interface_up=True)
    r.note_frame()
    assert r.snapshot(now=100.0).state is ReceiverState.HEALTHY


def test_receiver_up_with_no_traffic_is_degraded_not_healthy():
    """An interface that is up but deaf cannot prove the sky was empty."""
    r = ReceiverCounters(name="wifi", interface_up=True)
    assert r.snapshot(now=100.0).state is ReceiverState.DEGRADED


def test_receiver_down_is_down():
    r = ReceiverCounters(name="wifi", interface_up=False)
    r.note_frame()
    assert r.snapshot(now=100.0).state is ReceiverState.DOWN


def test_frame_delta_resets_between_heartbeats():
    r = ReceiverCounters(name="wifi", interface_up=True)
    r.note_frame()
    r.note_frame()
    assert r.snapshot(now=1.0).frames_since_last == 2
    assert r.snapshot(now=2.0).frames_since_last == 0
    assert r.snapshot(now=2.0).state is ReceiverState.DEGRADED


def test_heartbeat_permits_coverage_claim_only_when_healthy():
    up = ReceiverCounters(name="wifi", interface_up=True)
    up.note_frame()
    rec = heartbeat_record([up], sensor_id="s1", sensor_position=None, now=10.0)
    assert rec["coverage_claim_permitted"] is True

    deaf = ReceiverCounters(name="wifi", interface_up=True)
    rec = heartbeat_record([deaf], sensor_id="s1", sensor_position=None, now=10.0)
    assert rec["coverage_claim_permitted"] is False


def test_any_receiver_down_blocks_the_coverage_claim():
    good = ReceiverCounters(name="wifi", interface_up=True)
    good.note_frame()
    bad = ReceiverCounters(name="bluetooth", interface_up=False)
    rec = heartbeat_record([good, bad], sensor_id="s1", sensor_position=None, now=10.0)
    assert rec["overall_state"] == ReceiverState.DOWN.value
    assert rec["coverage_claim_permitted"] is False


def test_continuous_healthy_coverage_is_provable():
    hbs = [_hb(t, "healthy") for t in range(0, 601, 60)]
    ok, why = window_is_provable(hbs, start=0, end=600, max_gap_s=90)
    assert ok, why


def test_gap_in_coverage_is_not_provable():
    hbs = [_hb(t, "healthy") for t in [0, 60, 120, 480, 540, 600]]
    ok, why = window_is_provable(hbs, start=0, end=600, max_gap_s=90)
    assert not ok
    assert "gap in healthy coverage" in why


def test_degraded_heartbeats_do_not_count_as_coverage():
    hbs = [_hb(t, "degraded") for t in range(0, 601, 60)]
    ok, why = window_is_provable(hbs, start=0, end=600, max_gap_s=90)
    assert not ok
    assert "no healthy heartbeats" in why


def test_silence_is_never_a_negative_result():
    """The core guarantee: no heartbeats means non-result, not 'nothing flew'."""
    ok, why = window_is_provable([], start=0, end=600, max_gap_s=90)
    assert not ok


def test_coverage_ending_early_is_not_provable():
    hbs = [_hb(t, "healthy") for t in range(0, 301, 60)]
    ok, why = window_is_provable(hbs, start=0, end=600, max_gap_s=90)
    assert not ok
    assert "before window end" in why


def test_coverage_starting_late_is_not_provable():
    hbs = [_hb(t, "healthy") for t in range(300, 601, 60)]
    ok, why = window_is_provable(hbs, start=0, end=600, max_gap_s=90)
    assert not ok
    assert "after window start" in why
