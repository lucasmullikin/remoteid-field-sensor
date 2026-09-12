"""Proof that the sensor was listening.

The single most dangerous output this project could produce is silence
misread as absence. "No detection" and "the receiver was dead" look identical
in a log that only records detections, and one of them is a finding while the
other is a fault.

So the sensor writes heartbeats into the same hash-chained store as detections.
A heartbeat asserts only what it can actually observe:

  - each receiver's interface was present and in the expected mode
  - how many frames of ANY kind that receiver has seen since the last heartbeat
  - how long it has been since that receiver last decoded a Remote ID message

The frame counter is what makes a heartbeat mean something. A receiver that is
up but has seen zero frames of any kind is not evidence of an empty sky; it is
an unproven receiver, and it is reported as DEGRADED rather than HEALTHY.

An analysis may only claim "nothing flew over" across a window fully covered by
HEALTHY heartbeats. Any other window is a non-result.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum


class ReceiverState(str, Enum):
    #: Interface up AND frames observed since the last heartbeat.
    HEALTHY = "healthy"
    #: Interface up but no frames of any kind seen. Cannot prove it can hear.
    DEGRADED = "degraded"
    #: Interface missing, wrong mode, or erroring.
    DOWN = "down"


@dataclass
class ReceiverHealth:
    name: str
    state: ReceiverState
    frames_since_last: int
    seconds_since_last_remoteid: float | None
    detail: str = ""

    def as_record(self) -> dict:
        return {
            "receiver": self.name,
            "state": self.state.value,
            "frames_since_last_heartbeat": self.frames_since_last,
            "seconds_since_last_remoteid": self.seconds_since_last_remoteid,
            "detail": self.detail,
        }


@dataclass
class ReceiverCounters:
    """Mutable counters a receiver updates as it runs."""
    name: str
    interface_up: bool = False
    interface_detail: str = ""
    frames_total: int = 0
    remoteid_total: int = 0
    last_remoteid_at: float | None = None
    _frames_at_last_heartbeat: int = field(default=0, repr=False)

    def note_frame(self) -> None:
        self.frames_total += 1

    def note_remoteid(self, at: float | None = None) -> None:
        self.remoteid_total += 1
        self.last_remoteid_at = time.time() if at is None else at

    def snapshot(self, now: float | None = None) -> ReceiverHealth:
        now = time.time() if now is None else now
        delta = self.frames_total - self._frames_at_last_heartbeat
        self._frames_at_last_heartbeat = self.frames_total

        if not self.interface_up:
            state = ReceiverState.DOWN
        elif delta == 0:
            state = ReceiverState.DEGRADED
        else:
            state = ReceiverState.HEALTHY

        since = None if self.last_remoteid_at is None else (now - self.last_remoteid_at)
        return ReceiverHealth(name=self.name, state=state, frames_since_last=delta,
                              seconds_since_last_remoteid=since,
                              detail=self.interface_detail)


def heartbeat_record(receivers: list[ReceiverCounters],
                     sensor_id: str,
                     sensor_position: dict | None,
                     now: float | None = None) -> dict:
    """Build the heartbeat record written to the chain."""
    now = time.time() if now is None else now
    health = [r.snapshot(now) for r in receivers]
    states = {h.state for h in health}

    if ReceiverState.HEALTHY in states and ReceiverState.DOWN not in states:
        overall = ReceiverState.HEALTHY
    elif states == {ReceiverState.DEGRADED}:
        overall = ReceiverState.DEGRADED
    else:
        overall = ReceiverState.DOWN

    return {
        "type": "heartbeat",
        "sensor_id": sensor_id,
        "sensor_time_unix": now,
        "sensor_position": sensor_position,
        "overall_state": overall.value,
        "receivers": [h.as_record() for h in health],
        "coverage_claim_permitted": overall is ReceiverState.HEALTHY,
    }


def window_is_provable(heartbeats: list[dict], start: float, end: float,
                       max_gap_s: float) -> tuple[bool, str]:
    """Decide whether a time window may support a 'nothing flew over' claim.

    Requires unbroken HEALTHY coverage across the entire window with no gap
    longer than max_gap_s. Returns the reason when it cannot, because an
    unprovable window must be reported as a non-result, never rounded down to
    a negative finding.
    """
    if end <= start:
        return False, "empty or inverted window"

    healthy = sorted((h["sensor_time_unix"] for h in heartbeats
                      if h.get("overall_state") == ReceiverState.HEALTHY.value))
    if not healthy:
        return False, "no healthy heartbeats in window"

    if healthy[0] > start + max_gap_s:
        return False, f"no healthy heartbeat until {healthy[0] - start:.0f}s after window start"
    if healthy[-1] < end - max_gap_s:
        return False, f"healthy heartbeats stop {end - healthy[-1]:.0f}s before window end"

    for a, b in zip(healthy, healthy[1:]):
        if (b - a) > max_gap_s:
            return False, f"{b - a:.0f}s gap in healthy coverage"

    return True, "continuous healthy coverage"
