"""The recording pipeline: envelope -> message -> session -> record.

This is where the project's decisions become code:

  - both clocks are recorded, never collapsed (sensor GNSS receive time AND
    the transmitter's claimed time), because disagreement between them is
    itself a finding
  - every record carries a sensor_id, so a second unit can be added later
    without migrating history
  - everything received is recorded; institutional-vs-other is a later human
    judgment, and exclusions are logged when publishing, not at capture
  - undecodable frames are still recorded, with the raw bytes, because a
    parser found wrong later must be re-runnable against what was actually
    received
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from .astm.messages import MESSAGE_SIZE, MessageType, ParseError, parse_message, parse_message_pack
from .correlate import Correlator
from .liveness import ReceiverCounters, heartbeat_record
from .store.chain import RecordChain, RetentionClass


@dataclass
class SensorPosition:
    """The sensor's own GNSS fix.

    Recorded and published at full precision, per the project's decision. A
    detection without the observer's position documents nothing verifiable.
    """
    latitude: float
    longitude: float
    altitude_m: float | None = None
    fix_quality: str | None = None
    gnss_time_unix: float | None = None

    def as_record(self) -> dict:
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "altitude_m": self.altitude_m,
            "fix_quality": self.fix_quality,
            "gnss_time_unix": self.gnss_time_unix,
        }


class Pipeline:
    def __init__(self, chain: RecordChain, sensor_id: str,
                 correlator: Correlator | None = None):
        self.chain = chain
        self.sensor_id = sensor_id
        self.correlator = correlator or Correlator()
        self.receivers: dict[str, ReceiverCounters] = {}

    def register_receiver(self, name: str) -> ReceiverCounters:
        counters = ReceiverCounters(name=name)
        self.receivers[name] = counters
        return counters

    def ingest(self, *, transport_address: str, payload: bytes, transport: str,
               message_counter: int, sensor_position: SensorPosition | None,
               received_at: float | None = None,
               rssi_dbm: int | None = None) -> list[dict]:
        """Record one Remote ID payload. Returns the entries written."""
        now = time.time() if received_at is None else received_at
        counters = self.receivers.get(transport)

        messages, decode_error = self._decode(payload)

        if decode_error is not None:
            return [self.chain.append({
                "type": "undecodable",
                "sensor_id": self.sensor_id,
                "sensor_time_unix": now,
                "sensor_position": sensor_position.as_record() if sensor_position else None,
                "transport": transport,
                "transport_address": transport_address,
                "rssi_dbm": rssi_dbm,
                "error": decode_error,
                "raw_hex": payload.hex(),
            }, retention=RetentionClass.RAW)]

        if counters is not None:
            counters.note_remoteid(now)

        written = []
        for msg in messages:
            session = self.correlator.observe(transport_address, msg, received_at=now)
            written.append(self.chain.append(
                self._detection_record(msg, session, transport, transport_address,
                                       message_counter, sensor_position, now, rssi_dbm),
                retention=RetentionClass.RAW))
        return written

    def _decode(self, payload: bytes):
        try:
            if len(payload) >= 1 and ((payload[0] >> 4) & 0x0F) == MessageType.MESSAGE_PACK:
                return parse_message_pack(payload), None
            if len(payload) >= MESSAGE_SIZE:
                return [parse_message(payload[:MESSAGE_SIZE])], None
            return [], f"payload too short: {len(payload)} bytes"
        except ParseError as exc:
            return [], str(exc)

    def _detection_record(self, msg, session, transport, transport_address,
                          message_counter, sensor_position, now, rssi_dbm) -> dict:
        payload = msg.payload
        claimed = getattr(payload, "timestamp_unix", None)

        record = {
            "type": "detection",
            "sensor_id": self.sensor_id,
            # Two clocks, kept apart on purpose.
            "sensor_time_unix": now,
            "transmitter_time_unix": claimed,
            "clock_delta_s": (claimed - now) if claimed is not None else None,
            "sensor_position": sensor_position.as_record() if sensor_position else None,
            "transport": transport,
            "transport_address": transport_address,
            "rssi_dbm": rssi_dbm,
            "message_counter": message_counter,
            "message_type": int(msg.message_type),
            "protocol_version": msg.protocol_version,
            "session_id": session.session_id,
            "identified_at_receive_time": session.is_identified,
            "raw_hex": msg.raw.hex(),
        }

        if session.serial is not None:
            record["serial"] = session.serial.as_record()
        if payload is not None:
            record["decoded"] = _payload_fields(payload)
        if session.problems:
            record["session_problems"] = list(session.problems)

        return record

    def heartbeat(self, sensor_position: SensorPosition | None,
                  now: float | None = None) -> dict:
        return self.chain.append(
            heartbeat_record(list(self.receivers.values()), self.sensor_id,
                             sensor_position.as_record() if sensor_position else None,
                             now=now),
            retention=RetentionClass.RAW)


def _payload_fields(payload) -> dict:
    """Flatten a decoded payload to plain JSON-safe fields."""
    from dataclasses import asdict, is_dataclass
    if not is_dataclass(payload):
        return {}
    out = {}
    for k, v in asdict(payload).items():
        out[k] = v.hex() if isinstance(v, bytes) else v
    return out
