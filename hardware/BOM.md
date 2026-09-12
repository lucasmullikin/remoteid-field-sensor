# Bill of materials

Working sensor, bench-ready: **~$352**
Complete deployable unit: **~$522**

Prices are indicative and were last checked on **12 September 2026**. Where a price could
not be independently confirmed it is marked **TBC** rather than estimated, and lines
carrying a price that has not been re-verified against a live listing say so.

> **Price warning.** Single-board computer pricing moved sharply in late 2025 and 2026
> because of memory costs driven by AI infrastructure demand; Raspberry Pi has published
> two rounds of memory-driven price rises. The Pi line below was previously budgeted at
> $99 and is now $175–200 for the board alone. Re-check before ordering; these numbers
> will drift again.

---

## Phase 1 core — ~$352

| Part | Cost | Why this part |
|---|---|---|
| Raspberry Pi 5 8GB | **$175** ✅verified | The decoder software targets Ubuntu 24.04 ARM64. Pi 5 is its reference platform. $175 at PiShop.us, $200 at Adafruit (limit 2/customer), both checked 2026-09-12. **Do not buy the 16GB at $305** — this workload is 25-byte messages at low rates and never approaches 8GB. |
| Active Cooler + 27W USB-C PD PSU | ~$25 TBC | Required: the Pi 5 throttles without active cooling. Not re-verified against a live listing. |
| 64GB A2 microSD | $12 TBC | Boot volume and local record store. |
| SONOFF ZBDongle-P (TI CC2652P) | $25 TBC | Receives Bluetooth Long Range Remote ID. Chosen over the cheaper Nordic dongle specifically for its **external antenna connector**, which is the difference between a few hundred metres and a kilometre. |
| ALFA AWUS036ACM (MediaTek MT7612U) | $40 TBC | Dual-band monitor-mode Wi-Fi. **Critical:** Skydio aircraft broadcast Remote ID on **5 GHz only**. A 2.4 GHz-only adapter is silently blind to them. No good substitute is known. |
| 9 dBi dual-band omni + 2.4 GHz SMA omni + low-loss pigtails | $35 | Omnidirectional so an unattended sensor covers every bearing without aiming. This is where usable range is actually won. |
| USB GPS, u-blox chipset (e.g. GlobalSat BU-353N5) | $35 TBC | Records the sensor's own position. Without it a mobile detection documents nothing verifiable. |
| Pi 5 RTC battery | $5 TBC | Honest timestamps with no network. A drifted clock invalidates the record. |

### Bluetooth Long Range: resolved

The Bluetooth range budget rests on receiving BT5 Coded PHY, and that assumption fails
quietly on a lot of hardware — OpenDroneID's receiver documentation records devices that
advertise Long Range support and then never actually receive those signals.

For the CC2652P there is a documented working path: **NCC Group's Sniffle**
(https://github.com/nccgroup/Sniffle) ships a firmware build for this exact dongle
(`sniffle_cc1352p1_cc2652p1.hex`) and exposes long-range sniffing on the primary
advertising channels. The fallback is an nRF52840 dongle running Nordic's nRF Sniffer,
which also supports Coded PHY.

Mitigating fact: US transmitters must broadcast BT4 legacy **and** BT5 simultaneously, so
a receiver that only captures legacy still sees the aircraft — at reduced range, not zero.
A Coded PHY failure must degrade range, never silently empty the results.

### Recommended addition: NVMe storage — ~$50

Not in the original bill of materials, and worth adding.

| Part | Cost | Why |
|---|---|---|
| M.2 HAT taking 2280 drives (Pimoroni NVMe Base or Geekworm X1001) | ~$15 TBC | The official M.2 HAT+ accepts only short 2230/2242 drives. |
| NVMe SSD 256–512GB | ~$30–45 TBC | The record store is an append-only log writing continuously and unattended. Sustained small writes are what kills microSD cards, and a sensor that dies mid-deployment leaves a gap that looks like an empty sky. Storage is a reliability part here, not a speed part. |

## Phase 1 enclosure and field power — $170 (all lines TBC, not re-verified)

| Part | Cost | Why this part |
|---|---|---|
| Pelican Protector 1200 | $60 | Weather-sealed, survives vehicle transport, mounts under an eave. |
| SMA bulkhead connectors and pigtails | $30 | Antennas mount outside the sealed case. |
| Gore PolyVent pressure vent | $10 | Equalises pressure without admitting water. |
| 25,000 mAh USB-C PD bank with **true pass-through** | $50 | 8 to 10 hours untethered. Pass-through matters: most banks cut power when switching sources, which reboots the sensor. |
| 12V to USB-C PD vehicle adapter | $20 | Primary field power. |

---

## Phase 2 and 3 — not yet requested (prices TBC, not re-verified)

Listed for transparency. These are requested separately and only once Phase 1 is proven
with field data.

| Part | Cost | Purpose |
|---|---|---|
| HackRF Pro (Great Scott Gadgets) | $430 | Wideband sweep 100 kHz to 6 GHz. Detects a drone's control or video carrier when Remote ID is switched off under an FAA covert-operations waiver, which agencies can and do obtain. |
| LNAs, band filters, wideband antenna | $80 | Front-end conditioning. Determines whether the wideband layer works at range or not at all. |
| ESP32-S3 dev board | $10 | Independent second scanner, cross-checks the main receiver so one failure cannot produce a false "nothing flew over". |
| AntSDR E200 (MicroPhase via Crowd Supply) | TBC | Decodes DJI's proprietary DroneID beacon, identifying DJI aircraft even with Remote ID disabled. |
| SDRplay RSPduo | $280 | Passive radar. Detects aircraft broadcasting nothing at all, using existing FM and TV transmissions as illumination. |
