"""Assemble discrete Remote ID messages into flight sessions.

Remote ID broadcasts identity, position and operator location as separate
messages, and position messages routinely arrive before any identity message.
Correlation therefore happens in two stages:

1. Messages are grouped by the transport address that carried them (a Wi-Fi or
   Bluetooth MAC). This is available on every frame, including identity-less
   position frames.
2. When a Basic ID arrives on that transport session, the session is BOUND to
   the aircraft serial.

The binding is recorded as an observation with the time it occurred, not as a
retroactive fact. Messages received before the binding keep their own record of
having been unidentified at receive time. Nothing is rewritten after the fact.

Consequence, stated plainly: MAC randomization can split one physical flight
into several sessions. That is visible in the output and can be reconciled by a
human later. The alternative - joining sessions on a guess - would silently
attribute one aircraft's positions to another, which is the failure this design
refuses to risk.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from .astm.cta2063a import SerialNumber, parse_serial
from .astm.messages import BasicID, Location, MessageType, OperatorID, System

#: A transport session with no traffic for this long is considered closed.
SESSION_IDLE_TIMEOUT_S = 300.0


@dataclass
class Session:
    """One transport-layer session, possibly bound to an aircraft identity."""
    transport_address: str
    first_seen: float
    last_seen: float
    serial: SerialNumber | None = None
    bound_at: float | None = None
    messages_before_binding: int = 0
    message_count: int = 0
    ua_type: int | None = None
    operator_id: str | None = None
    operator_latitude: float | None = None
    operator_longitude: float | None = None
    last_latitude: float | None = None
    last_longitude: float | None = None
    problems: list[str] = field(default_factory=list)

    @property
    def is_identified(self) -> bool:
        return self.serial is not None

    @property
    def session_id(self) -> str:
        """Stable key for this session. Deliberately NOT the serial.

        The serial identifies an aircraft; this identifies one observed
        transmission session. Keying records on the serial would merge separate
        observations of the same airframe into a single record and destroy the
        ability to say how many times it was independently seen.
        """
        return f"{self.transport_address}@{self.first_seen:.3f}"


class Correlator:
    """Groups messages into sessions and binds identity when it arrives."""

    def __init__(self, idle_timeout_s: float = SESSION_IDLE_TIMEOUT_S):
        self._idle_timeout = idle_timeout_s
        self._open: dict[str, Session] = {}

    def observe(self, transport_address: str, message, received_at: float | None = None) -> Session:
        """Fold one decoded message into its session and return that session."""
        now = time.time() if received_at is None else received_at
        session = self._open.get(transport_address)

        if session is not None and (now - session.last_seen) > self._idle_timeout:
            del self._open[transport_address]
            session = None

        if session is None:
            session = Session(transport_address=transport_address,
                              first_seen=now, last_seen=now)
            self._open[transport_address] = session

        session.last_seen = now
        session.message_count += 1
        payload = message.payload

        if isinstance(payload, BasicID):
            self._bind(session, payload, now)
        elif isinstance(payload, Location):
            if payload.latitude is not None:
                session.last_latitude = payload.latitude
                session.last_longitude = payload.longitude
        elif isinstance(payload, System):
            session.operator_latitude = payload.operator_latitude
            session.operator_longitude = payload.operator_longitude
        elif isinstance(payload, OperatorID):
            session.operator_id = payload.operator_id or None

        if not session.is_identified and not isinstance(payload, BasicID):
            session.messages_before_binding += 1

        return session

    def _bind(self, session: Session, basic: BasicID, now: float) -> None:
        session.ua_type = basic.ua_type
        if not basic.is_serial_number or not basic.uas_id:
            return

        serial = parse_serial(basic.uas_id)

        if session.serial is None:
            session.serial = serial
            session.bound_at = now
            return

        # An identity change mid-session is not something this code resolves by
        # picking a winner. Both are kept and the conflict is surfaced.
        if session.serial.raw != serial.raw:
            session.problems.append(
                f"identity changed mid-session: {session.serial.raw!r} -> {serial.raw!r}")

    def expire(self, now: float | None = None) -> list[Session]:
        """Close and return sessions idle past the timeout."""
        now = time.time() if now is None else now
        closed = [s for s in self._open.values() if (now - s.last_seen) > self._idle_timeout]
        for s in closed:
            self._open.pop(s.transport_address, None)
        return closed

    @property
    def open_sessions(self) -> list[Session]:
        return list(self._open.values())
