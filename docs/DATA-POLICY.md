# Data policy

## What is recorded

Fields present in the ASTM F3411 Remote ID broadcast only:
- aircraft serial (ANSI/CTA-2063-A)
- operator ground-station position
- operator registration ID
- message timestamp and the sensor's own GNSS position and time

Nothing else. No video, no audio, no payload, no command-link content.

## What is published

Aggregate and institutional records. The subject is the operation of institutional
aircraft fleets and whether published flight records match observed activity.

Records that appear to correspond to private or hobbyist operators are not the subject of
this project and are not published.

## Retention

**Raw records expire 30 days after they are written.** Records promoted to `published`
are the evidentiary basis of a public claim and are never expired by a timer; retracting
one is a deliberate human act.

Expiry is performed by **redaction, not deletion**. The record store is a hash chain, and
deleting a record would break the integrity proof for everything recorded after it. On
expiry the content is replaced by a tombstone while the original hash is preserved, so:

- the chain still verifies end to end
- the record still proves that something was received, and when
- the content is no longer disclosed
- if the original content is ever produced from elsewhere, it can be checked against the
  retained hash

Nothing about a redaction is silent. Each tombstone records when and why it happened.

Enforcement is `remoteid-sensor retention`, and `remoteid-sensor verify` confirms the
chain still holds afterwards. The behaviour is covered by tests in
`tests/test_retention.py`.

## Corrections

Errors in published records are corrected in the repository with the correction recorded
rather than silently amended.
