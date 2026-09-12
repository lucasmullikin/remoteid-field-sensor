# Remote ID Field Sensor

An open-source, **receive-only** sensor that independently records the FAA-mandated
Remote ID broadcasts of drones operating in US airspace, so that published flight
records can be verified rather than trusted.

**Status: designed and sourced. Not yet assembled. No field data yet.**
Nothing in this repository should be read as a claim that the system is operational.
Detection ranges given below are expectations to be measured, not results.

---

## Why this exists

Crewed aircraft are publicly accountable in a way drones are not. OpenSky Network and
ADS-B Exchange assemble public flight records from thousands of volunteer receivers, and
journalists use them routinely to establish where an aircraft was and when.

No equivalent public archive appears to exist for Remote ID.

This matters because automated police drone programs have scaled quickly:

- **1,000+** US public safety agencies held FAA waivers to run automated drone programs
  as of February 2026
- The FAA issued **more of those waivers between April 2025 and February 2026 than in the
  previous seven years combined**
- **~300** agencies adopted Drone-as-First-Responder capability during 2025 alone

The Electronic Frontier Foundation warns that normalising police DFR programs
"jeopardizes privacy," noting these aircraft capture backyards, rooftops, and views
through windows. Vendors answer that concern with self-reporting. Flock Safety states its
DFR product activates only on specific calls for service, never general patrol, with
every flight logged to a public transparency dashboard.

**That claim is checkable. Nobody appears to be checking it.**

Every receiver available today is either a standalone device watching one patch of sky, or
a roughly $5,000 commercial appliance sold to the same institutions whose flights the
records would cover. There is no shared archive and no way for one newsroom to check
another's work.

This is one node, built cheaply and documented completely enough that it can become many.

---

## What it receives, and why that is lawful

Under **14 CFR Part 89**, nearly every drone in US airspace must continuously broadcast
Remote ID to the **ASTM F3411** standard over Bluetooth and Wi-Fi, on 2.437 GHz and
5.745 GHz. These broadcasts are **unencrypted by federal mandate and designed to be
received by anyone.**

Each broadcast carries:
- the aircraft serial number (**ANSI/CTA-2063-A** format; the first four characters
  identify the manufacturer)
- the operator's ground-station position, which is the launch site
- the operator's registration ID

This sensor is a receiver for that broadcast and nothing more.

---

## HARD CONSTRAINTS

These are design constraints, not aspirations. They are the reason this project can exist.

| | |
|---|---|
| **RECEIVE ONLY** | No transmitter. The device cannot be made to transmit. |
| **NO JAMMING** | No GPS denial, no countermeasures of any kind. Interfering with aircraft or navigation signals is a federal felony. Some open-source drone projects ship jamming features. Any code adopted here has those features **removed**, and the removal is documented in `docs/REMOVED-CAPABILITIES.md`. |
| **NO DECRYPTION** | Only signals broadcast unencrypted by federal mandate are decoded. |
| **NO CONTENT INTERCEPTION** | Identification and position only. No video, no audio, no payload. |
| **NO TARGETING OF INDIVIDUALS** | The subject is institutional aircraft operation. Not private drone operators. Not individuals. |

See `docs/LEGAL-POSTURE.md` for the full statement.

---

## Prior art

This project does not claim novelty. It stands on:

- **OpenDroneID** — reference ASTM F3411 implementation
- **armasuisse Cyber-Defence Campus, RemoteIDReceiver**
- **alphafox02** — droneid-go, DragonSync, WarDragon
- **BlueMark DroneScout**

Adjacent accountability work: **DeFlock** (ALPR mapping), **SparrowMap**, **EFF Atlas of
Surveillance**.

Precedent for the reporting: **WFPL News** obtained 11+ hours of Kentucky State Police
drone footage; the resulting investigation documented officers using force without prior
instigation from demonstrators.

---

## Bill of materials

Working sensor, bench-ready: **$251**. Complete deployable unit: **$421**.
Full rationale for every part, including why each was chosen over its alternatives, is in
[`hardware/BOM.md`](hardware/BOM.md).

---

## Licence

Code and documentation are released under the licences in `LICENSE`.
No exclusivity, no embargo, no claim of endorsement by any contributor or supplier.

## Contributing hardware

Component manufacturers who supply parts are credited by name in this repository, in the
build documentation, and in the published methodology. The build specifies contributed
parts by name so the build is reproducible and others buy the same component. Measured
field performance is published honestly, including negative results.

Contact: lucasmullikin@gmail.com
