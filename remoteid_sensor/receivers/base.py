"""Receiver interface.

A receiver's only job is to produce (transport_address, payload) pairs and to
keep its liveness counters honest. Decoding belongs to the pipeline; this
separation is what lets the entire software path be tested with no radio.

VERIFICATION STATUS
-------------------
Everything in remoteid_sensor/receivers/frames.py is tested and passing.
The capture paths in bluetooth_lr.py and wifi.py are UNVERIFIED: they have
never been run against hardware, because the hardware does not exist yet.
They are written to be reviewable, not to be trusted. Each carries a status
banner saying exactly what remains unproven.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass

from ..liveness import ReceiverCounters


@dataclass(frozen=True)
class CapturedFrame:
    transport_address: str
    payload: bytes
    message_counter: int
    rssi_dbm: int | None = None


class Receiver(abc.ABC):
    """Base class for a Remote ID receiver."""

    #: Set False in any subclass that has been validated against real hardware.
    UNVERIFIED_AGAINST_HARDWARE = True

    def __init__(self, name: str, counters: ReceiverCounters):
        self.name = name
        self.counters = counters

    @abc.abstractmethod
    def open(self) -> None:
        """Bring the interface up. Must set counters.interface_up truthfully."""

    @abc.abstractmethod
    def frames(self):
        """Yield CapturedFrame. Must call counters.note_frame() for EVERY frame
        seen, including non-Remote-ID traffic.

        That counter is what distinguishes 'the sky was empty' from 'the
        receiver was deaf'. A receiver that only counts Remote ID frames makes
        its own failure indistinguishable from a true negative.
        """

    def close(self) -> None:
        self.counters.interface_up = False
