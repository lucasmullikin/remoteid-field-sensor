# How to put this repo live, start to finish

> **Status: steps 1 to 4 are complete.** The repository is live at
> https://github.com/lucasmullikin/remoteid-field-sensor — public, MIT/CC BY 4.0,
> description and topics set, with continuous integration running the test suite.
> This file is kept as the record of how it was published, and because **step 5, the
> Great Scott Gadgets application, is still the live next action.**


Ten minutes. Great Scott Gadgets judge on "community impact and clarity of project
description," so a live repo with real documentation is the thing that makes that
application work.

## 1. Create the repository

On GitHub, create a **public** repository. Suggested name: `remoteid-field-sensor`.
Do not initialise with a README, this package already has one.

## 2. Push this package

```bash
cd remoteid-sensor
git init
git add .
git commit -m "Initial: project rationale, legal posture, bill of materials"
git branch -M main
git remote add origin https://github.com/YOURUSERNAME/remoteid-field-sensor.git
git push -u origin main
```

## 3. Set the repository description

> Open-source, receive-only sensor that independently records FAA-mandated Remote ID
> broadcasts, so published drone flight records can be verified rather than trusted.

Topics: `remote-id`, `astm-f3411`, `sdr`, `journalism`, `accountability`,
`open-source-hardware`, `raspberry-pi`

## 4. Fill in the two blanks

- `LICENSE` — add your name after "Copyright (c) 2026"
- `README.md` — the contact line at the bottom

## 5. Then, and only then, apply to Great Scott Gadgets

https://greatscottgadgets.com/freestuff/ , form at https://forms.gle/HeujR1anNhG2c3wq8

Rolling. One recipient chosen per month from everything received in the previous twelve
months, so an application stays in the pool for a year. They require the project be open
source. Focus the form on **one specific project** and be detailed.

Note: **HackRF is a general-purpose SDR.** Remote ID itself is Bluetooth and Wi-Fi, so be
explicit in the form that the HackRF is for the Phase 2 wideband layer, detecting a
drone's control or video carrier when Remote ID is switched off under a covert-operations
waiver. Do not let them think you have misunderstood what their hardware does.

## What NOT to put in the repo

- No police agency named as a target. The subject is a category of technology and its
  public accountability.
- No claim the system is operational. It is designed and sourced, not built.
- No detection range presented as achieved. They are expectations to be measured.
