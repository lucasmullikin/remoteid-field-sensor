# Legal posture

This document exists so that a legal reviewer at a component manufacturer can read one
page and make a decision.

## What the device does

It receives radio broadcasts that federal regulation requires to be transmitted
unencrypted, and records what they contain.

Under **14 CFR Part 89**, nearly every drone operating in US airspace must continuously
broadcast Remote ID messages conforming to **ASTM F3411**. The rule mandates that these
messages be unencrypted. The design intent of the standard is that the broadcast be
receivable by the public and by other airspace users.

Receiving an unencrypted broadcast that federal regulation requires to be transmitted in
the clear is not interception of a protected communication.

## What the device does not do

**It does not transmit.** There is no transmitter in the bill of materials. The device is
architecturally incapable of transmitting.

**It does not jam, deny, spoof or interfere.** No GPS denial. No countermeasures. No
command-link interference. Interfering with aircraft or navigation signals is a federal
felony and this project treats that as an absolute line. Several open-source drone
projects distribute jamming or spoofing capability alongside receiving capability. Where
code from such a project is adopted here, those capabilities are removed before adoption
and the removal is recorded in `REMOVED-CAPABILITIES.md` with the commit that performed it.

**It does not decrypt.** Only unencrypted, federally mandated broadcasts are decoded.

**It does not intercept communications content.** No video downlink, no audio, no payload
data. The device records identification and position fields only.

**It does not target individuals.** The subject of the reporting is the operation of
institutional aircraft fleets and the accountability of the published records describing
them. Private and hobbyist operators are not the subject and are not the target of
collection.

## Data handling

Records are identification and position only. Publication policy, retention and any
redaction applied before publication are documented in `docs/DATA-POLICY.md`.

## Why a manufacturer can supply a part to this project

The contributed component performs the same function it performs in any receiver: it
receives. The project is open source, the constraints above are published and auditable
in the repository, and no supplier is asked for, or given, any claim of endorsement.
