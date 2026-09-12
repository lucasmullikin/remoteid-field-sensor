# Bill of materials

Working sensor, bench-ready: **$251**
Complete deployable unit: **$421**

Prices are indicative and current as of September 2026. Where a price or capability could
not be independently confirmed it is marked **TBC** rather than estimated.

---

## Phase 1 core — $251

| Part | Cost | Why this part |
|---|---|---|
| Raspberry Pi 5 8GB + Active Cooler + 27W USB-C PSU | $99 | The decoder software targets Ubuntu 24.04 ARM64. Pi 5 is its reference platform. |
| 64GB A2 microSD | $12 | Boot volume and local record store. |
| SONOFF ZBDongle-P (TI CC2652P) | $25 | Receives Bluetooth Long Range Remote ID. Chosen over the cheaper Nordic dongle specifically for its **external antenna connector**, which is the difference between a few hundred metres and a kilometre. |
| ALFA AWUS036ACM (MediaTek MT7612U) | $40 | Dual-band monitor-mode Wi-Fi. **Critical:** Skydio aircraft broadcast Remote ID on **5 GHz only**. A 2.4 GHz-only adapter is silently blind to them. No good substitute is known. |
| 9 dBi dual-band omni + 2.4 GHz SMA omni + low-loss pigtails | $35 | Omnidirectional so an unattended sensor covers every bearing without aiming. This is where usable range is actually won. |
| USB GPS, u-blox chipset (e.g. GlobalSat BU-353N5) | $35 | Records the sensor's own position. Without it a mobile detection documents nothing verifiable. |
| Pi 5 RTC battery | $5 | Honest timestamps with no network. A drifted clock invalidates the record. |

## Phase 1 enclosure and field power — $170

| Part | Cost | Why this part |
|---|---|---|
| Pelican Protector 1200 | $60 | Weather-sealed, survives vehicle transport, mounts under an eave. |
| SMA bulkhead connectors and pigtails | $30 | Antennas mount outside the sealed case. |
| Gore PolyVent pressure vent | $10 | Equalises pressure without admitting water. |
| 25,000 mAh USB-C PD bank with **true pass-through** | $50 | 8 to 10 hours untethered. Pass-through matters: most banks cut power when switching sources, which reboots the sensor. |
| 12V to USB-C PD vehicle adapter | $20 | Primary field power. |

---

## Phase 2 and 3 — not yet requested

Listed for transparency. These are requested separately and only once Phase 1 is proven
with field data.

| Part | Cost | Purpose |
|---|---|---|
| HackRF Pro (Great Scott Gadgets) | $430 | Wideband sweep 100 kHz to 6 GHz. Detects a drone's control or video carrier when Remote ID is switched off under an FAA covert-operations waiver, which agencies can and do obtain. |
| LNAs, band filters, wideband antenna | $80 | Front-end conditioning. Determines whether the wideband layer works at range or not at all. |
| ESP32-S3 dev board | $10 | Independent second scanner, cross-checks the main receiver so one failure cannot produce a false "nothing flew over". |
| AntSDR E200 (MicroPhase via Crowd Supply) | TBC | Decodes DJI's proprietary DroneID beacon, identifying DJI aircraft even with Remote ID disabled. |
| SDRplay RSPduo | $280 | Passive radar. Detects aircraft broadcasting nothing at all, using existing FM and TV transmissions as illumination. |
