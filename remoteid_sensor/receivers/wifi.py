"""Wi-Fi Remote ID receiver (802.11 Beacon and NAN).

STATUS: UNVERIFIED. Never run against hardware. Requires an ALFA AWUS036ACM
(MediaTek MT7612U) in monitor mode. See hardware/BOM.md.

CRITICAL: Skydio aircraft broadcast Remote ID on 5 GHz ONLY. A 2.4 GHz-only
adapter is silently blind to them - it will report a clean, healthy, entirely
empty sky. Channel coverage must include 5 GHz or the sensor produces
confident false negatives.

What is proven: the IE parsing in frames.py, covered by tests.
What is not: monitor-mode setup, channel hopping, and scapy's behaviour on
this driver.
"""

from __future__ import annotations

import subprocess

from ..liveness import ReceiverCounters
from .base import CapturedFrame, Receiver
from .frames import extract_from_wifi_ie

#: 2.4 GHz plus the 5 GHz channels Remote ID is seen on. Omitting 5 GHz is the
#: single easiest way to make this sensor lie.
DEFAULT_CHANNELS = [1, 6, 11, 36, 40, 44, 48, 149, 153, 157, 161, 165]


class WifiReceiver(Receiver):
    UNVERIFIED_AGAINST_HARDWARE = True

    def __init__(self, interface: str, counters: ReceiverCounters,
                 channels: list[int] | None = None, dwell_s: float = 0.5):
        super().__init__(name="wifi", counters=counters)
        self.interface = interface
        self.channels = channels or list(DEFAULT_CHANNELS)
        self.dwell_s = dwell_s

        if not any(c >= 36 for c in self.channels):
            raise ValueError(
                "channel list contains no 5 GHz channels; this receiver would be "
                "silently blind to 5 GHz-only aircraft. Refusing to start.")

    def open(self) -> None:
        try:
            mode = subprocess.run(["iw", "dev", self.interface, "info"],
                                  capture_output=True, text=True, timeout=10)
            up = mode.returncode == 0 and "type monitor" in mode.stdout
            self.counters.interface_up = up
            self.counters.interface_detail = (
                "monitor mode" if up else f"not in monitor mode: {mode.stdout.strip()[:120]}")
        except (OSError, subprocess.SubprocessError) as exc:
            self.counters.interface_up = False
            self.counters.interface_detail = f"iw failed: {exc}"

    def set_channel(self, channel: int) -> bool:
        r = subprocess.run(["iw", "dev", self.interface, "set", "channel", str(channel)],
                           capture_output=True, text=True, timeout=10)
        return r.returncode == 0

    def frames(self):
        """Yield Remote ID frames from monitor-mode capture.

        Imports scapy lazily so the rest of the package - and its whole test
        suite - remains importable on a machine with no capture stack.
        """
        from scapy.all import Dot11, Dot11Beacon, Dot11EltVendorSpecific, sniff  # noqa: F401

        def handle(pkt):
            self.counters.note_frame()

        for pkt in sniff(iface=self.interface, prn=handle, store=False, stop_filter=None):
            frame = self._to_frame(pkt)
            if frame is not None:
                yield frame

    def _to_frame(self, pkt) -> CapturedFrame | None:
        from scapy.all import Dot11

        if not pkt.haslayer(Dot11):
            return None
        ie_bytes = bytes(pkt[Dot11].payload)[12:]  # skip fixed beacon params
        got = extract_from_wifi_ie(ie_bytes)
        if got is None:
            return None
        return CapturedFrame(transport_address=str(pkt[Dot11].addr2 or "unknown"),
                             payload=got.payload,
                             message_counter=got.message_counter,
                             rssi_dbm=getattr(pkt, "dBm_AntSignal", None))
