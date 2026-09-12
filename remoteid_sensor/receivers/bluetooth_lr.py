"""Bluetooth Remote ID receiver (legacy advertising and BT5 Long Range).

STATUS: UNVERIFIED. Never run against hardware. Requires a SONOFF ZBDongle-P
(TI CC2652P) reflashed with TI's packet-sniffer firmware. See hardware/BOM.md.

Two things here are genuinely unproven and must be confirmed on hardware
before any field claim rests on them:

  1. That the CC2652P sniffer firmware captures BT5 Coded PHY (Long Range)
     advertising, not only 1M PHY legacy advertising. Most Remote ID beacons
     transmit on both, but the Long Range PHY is where the range is.
  2. The exact TI sniffer framing. The structure below follows TI's documented
     packet format; the field offsets are marked TBC until read off a real
     device, matching the convention in hardware/BOM.md.

What is proven: the AD parsing in frames.py, covered by tests.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..liveness import ReceiverCounters
from .base import CapturedFrame, Receiver
from .frames import extract_from_bluetooth_ad

#: TI packet sniffer frames begin with this sync word.
TI_SYNC = bytes([0x40, 0x53])
TI_HEADER_LEN = 6  # TBC against hardware


@dataclass(frozen=True)
class TIPacket:
    payload: bytes
    rssi_dbm: int | None


def parse_ti_sniffer_frame(buf: bytes) -> TIPacket | None:
    """Parse one TI sniffer frame. Offsets TBC against hardware.

    Isolated as a pure function so it can be corrected and unit-tested the
    moment a real capture exists, without touching the capture loop.
    """
    if len(buf) < TI_HEADER_LEN + 1 or buf[:2] != TI_SYNC:
        return None
    length = int.from_bytes(buf[3:5], "little")
    body = buf[TI_HEADER_LEN:TI_HEADER_LEN + length]
    if not body:
        return None
    rssi = int.from_bytes(body[-2:-1], "little", signed=True) if len(body) >= 2 else None
    return TIPacket(payload=body, rssi_dbm=rssi)


class BluetoothReceiver(Receiver):
    UNVERIFIED_AGAINST_HARDWARE = True

    def __init__(self, device: str, counters: ReceiverCounters, baudrate: int = 3000000):
        super().__init__(name="bluetooth", counters=counters)
        self.device = device
        self.baudrate = baudrate
        self._serial = None

    def open(self) -> None:
        try:
            import serial  # lazy: keeps the package importable without pyserial
            self._serial = serial.Serial(self.device, self.baudrate, timeout=1)
            self.counters.interface_up = True
            self.counters.interface_detail = f"{self.device} @ {self.baudrate}"
        except Exception as exc:                      # noqa: BLE001 - reported, not swallowed
            self.counters.interface_up = False
            self.counters.interface_detail = f"open failed: {exc}"

    def frames(self):
        if self._serial is None:
            return
        while True:
            chunk = self._serial.read_until(TI_SYNC)
            if not chunk:
                continue
            self.counters.note_frame()

            pkt = parse_ti_sniffer_frame(chunk)
            if pkt is None:
                continue
            got = extract_from_bluetooth_ad(pkt.payload)
            if got is None:
                continue

            yield CapturedFrame(
                transport_address=_advertiser_address(pkt.payload),
                payload=got.payload,
                message_counter=got.message_counter,
                rssi_dbm=pkt.rssi_dbm)

    def close(self) -> None:
        if self._serial is not None:
            self._serial.close()
        super().close()


def _advertiser_address(pdu: bytes) -> str:
    """Extract the advertiser address from a BLE advertising PDU.

    The address is the six bytes following the two-byte PDU header, little
    endian. Returns 'unknown' rather than a plausible-looking wrong address
    when the PDU is too short - a fabricated address would silently split or
    merge sessions.
    """
    if len(pdu) < 8:
        return "unknown"
    return ":".join(f"{b:02x}" for b in reversed(pdu[2:8]))
