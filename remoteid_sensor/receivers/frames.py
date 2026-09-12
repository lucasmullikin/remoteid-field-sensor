"""Extract ASTM F3411 payloads from their Bluetooth and Wi-Fi carriers.

Remote ID rides on three transports, each wrapping the same 25-byte messages
in a different envelope:

  Bluetooth 4 legacy advertising   - Service Data AD, UUID 0xFFFA
  Bluetooth 5 Long Range (Coded)   - same envelope, different PHY
  Wi-Fi Beacon / NAN               - vendor-specific IE, OUI FA:0B:BC

This module handles only the unwrapping, which is pure byte manipulation and
is therefore fully testable on a workstation with no radio attached. Actually
obtaining frames from hardware lives in the receiver modules alongside it and
cannot be verified without the dongles.

Splitting them this way means a parser bug is findable at a desk, and only
genuine radio behaviour is left unproven until hardware exists.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Service UUID assigned to ASTM International for Remote ID, little-endian
#: on the wire.
ASTM_SERVICE_UUID = 0xFFFA
_ASTM_UUID_LE = bytes([0xFA, 0xFF])

#: Organisationally Unique Identifier for ASTM Remote ID in Wi-Fi vendor IEs.
ASTM_OUI = bytes([0xFA, 0x0B, 0xBC])

#: Application code identifying a Remote ID payload within either envelope.
ASTM_APP_CODE = 0x0D

AD_TYPE_SERVICE_DATA_16 = 0x16
IE_ID_VENDOR_SPECIFIC = 0xDD


@dataclass(frozen=True)
class ExtractedPayload:
    """A Remote ID payload lifted out of its transport envelope."""
    payload: bytes
    message_counter: int
    transport: str


def extract_from_bluetooth_ad(ad_data: bytes) -> ExtractedPayload | None:
    """Pull a Remote ID payload out of a Bluetooth advertising PDU.

    Walks the AD structures rather than assuming a fixed offset: transmitters
    put flags, tx power and names ahead of the service data in whatever order
    they like, and a hardcoded offset works on one vendor's aircraft and
    silently fails on the next.
    """
    i = 0
    n = len(ad_data)

    while i < n:
        length = ad_data[i]
        if length == 0:
            break
        if i + 1 + length > n:
            break  # truncated structure; stop rather than read past the end

        ad_type = ad_data[i + 1]
        body = ad_data[i + 2: i + 1 + length]

        if ad_type == AD_TYPE_SERVICE_DATA_16 and body[:2] == _ASTM_UUID_LE:
            rest = body[2:]
            if len(rest) >= 2 and rest[0] == ASTM_APP_CODE:
                return ExtractedPayload(payload=bytes(rest[2:]),
                                        message_counter=rest[1],
                                        transport="bluetooth")
            return None

        i += 1 + length

    return None


def extract_from_wifi_ie(ie_bytes: bytes) -> ExtractedPayload | None:
    """Pull a Remote ID payload out of 802.11 information elements.

    Accepts the IE section of a Beacon or NAN action frame and walks elements
    looking for the ASTM vendor-specific IE.
    """
    i = 0
    n = len(ie_bytes)

    while i + 2 <= n:
        elem_id = ie_bytes[i]
        length = ie_bytes[i + 1]
        if i + 2 + length > n:
            break

        body = ie_bytes[i + 2: i + 2 + length]

        if elem_id == IE_ID_VENDOR_SPECIFIC and body[:3] == ASTM_OUI:
            rest = body[3:]
            if len(rest) >= 2 and rest[0] == ASTM_APP_CODE:
                return ExtractedPayload(payload=bytes(rest[2:]),
                                        message_counter=rest[1],
                                        transport="wifi")
            return None

        i += 2 + length

    return None


def build_bluetooth_ad(payload: bytes, message_counter: int = 0,
                       prefix_structures: bytes = b"") -> bytes:
    """Construct a Bluetooth AD carrying a Remote ID payload. Test helper."""
    body = _ASTM_UUID_LE + bytes([ASTM_APP_CODE, message_counter & 0xFF]) + payload
    return prefix_structures + bytes([len(body) + 1, AD_TYPE_SERVICE_DATA_16]) + body


def build_wifi_ie(payload: bytes, message_counter: int = 0,
                  prefix_elements: bytes = b"") -> bytes:
    """Construct an 802.11 vendor IE carrying a Remote ID payload. Test helper."""
    body = ASTM_OUI + bytes([ASTM_APP_CODE, message_counter & 0xFF]) + payload
    return prefix_elements + bytes([IE_ID_VENDOR_SPECIFIC, len(body)]) + body
