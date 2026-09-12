# Contributing

This project exists so that other journalists and researchers can run it, check it, and
disagree with it. Contributions are welcome, including ones that show a finding was wrong.

## You do not need hardware

The decode and record path, and its entire test suite, run on any machine with no radio
attached. That is deliberate: the parser is the instrument, and an instrument that can
only be checked in the field is an instrument nobody checks.

```bash
git clone https://github.com/lucasmullikin/remoteid-field-sensor.git
cd remoteid-field-sensor
pip install -e ".[dev]"
python -m pytest
```

All tests should pass. If they do not, that is a bug report worth filing on its own.

```bash
# exercise the recording path with synthetic messages, no radio needed
remoteid-sensor selftest --store /tmp/s.jsonl
remoteid-sensor verify   --store /tmp/s.jsonl
remoteid-sensor stats    --store /tmp/s.jsonl
```

Capture dependencies are optional and only needed to talk to real radios:

```bash
pip install -e ".[capture]"   # scapy, pyserial
```

## What is proven and what is not

Please read this before assuming something works.

| Area | Status |
|---|---|
| `astm/messages.py`, `astm/cta2063a.py`, `receivers/frames.py`, `correlate.py`, `store/`, `liveness.py`, `pipeline.py` | Tested. CI runs the suite on every push. |
| `receivers/wifi.py`, `receivers/bluetooth_lr.py` | **UNVERIFIED.** Never run against hardware, because no hardware has been built. |

Two things in `receivers/bluetooth_lr.py` are explicitly marked TBC and need confirming
against a real device: whether the CC2652P sniffer firmware captures BT5 Coded PHY
(Long Range) advertising rather than only 1M PHY legacy, and the exact TI sniffer frame
offsets. **If you have this hardware, confirming or correcting either of those is the
single most useful contribution available right now.**

## Principles the code follows

These are not style preferences. Each exists because violating it would let the sensor
produce a confident falsehood.

- **Silence is never a negative result.** A "nothing flew over" claim requires heartbeats
  proving each receiver was up *and* hearing traffic across the whole window. A receiver
  that is up but has heard nothing at all is reported DEGRADED, not HEALTHY.
- **Never discard what was received.** Payloads that fail to decode are recorded with
  their raw bytes. A validator that drops input it disagrees with is indistinguishable
  from a validator that is simply wrong.
- **Never collapse the two clocks.** The sensor's receive time and the transmitter's
  claimed time stay separate fields. Their disagreement is a finding.
- **Never break the chain.** Records are hash-linked. Retention is enforced by redaction,
  not deletion. Anything that would make the store silently rewritable is a defect.
- **Fail loudly at the boundary.** `WifiReceiver` refuses to start on a 2.4 GHz-only
  channel list rather than reporting a confident empty sky, because some aircraft
  broadcast on 5 GHz only.

## Hard constraints

This project is receive-only. No transmitter, no jamming, no GPS denial, no decryption,
no interception of communications content. Only signals broadcast unencrypted by federal
mandate are decoded. Contributions adding offensive capability will not be merged. See
`docs/LEGAL-POSTURE.md` and `docs/REMOVED-CAPABILITIES.md`.

## Tests

New behaviour needs a test. Tests that assert a string exists somewhere are not
sufficient — assert the effect. Several tests in this suite exist specifically to prove
a failure mode is caught, and those are the ones worth imitating.
