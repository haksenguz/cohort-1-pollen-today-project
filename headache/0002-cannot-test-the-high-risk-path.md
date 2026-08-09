---
status: implementing
owner: Ismoiljon (Slice C)
opened: 2026-08-09
review-by: 2026-08-22
severity: high
---

# 0002 — The alert path cannot be exercised while the index is LOW

## Symptom

Live KMA data returned `0` (LOW) for all 16 regions on 2026-08-09. The alert
job's threshold is `HIGH`, so a correct run sends nothing — which is
indistinguishable from a broken run that sends nothing.

## Real cause

Ragweed season is Aug–Oct but the index has not ramped. There is no way to know
in advance when the first HIGH day arrives, and M1 (Sun 23 Aug) requires "the
bot posts a correctly formatted test alert to one channel, triggered by the
scheduler and not by hand".

Waiting for real data to prove the send path is a plan with no completion date.

## What the research says

Standard practice is that the trigger condition and the delivery mechanism are
tested independently. Delivery correctness must not depend on upstream data
happening to be interesting on demo day. Options, in descending order of honesty:

1. **Lower the threshold via config for the test.** `ALERT_MIN_RISK_LEVEL=LOW`
   already exists as an env var, so no code changes and nothing to remove
   afterwards. The message is real, the channel is real, the scheduler is real —
   only the cutoff differs, and the diff is one line of config.
2. **Seed a forecast row.** Truthful message content, but requires a seam that
   exists only for tests.
3. **Wait for a real HIGH day.** Correct but unschedulable, and it fails M1 if
   the season is late.

Option 1 is what we use. It is also honest to describe in the demo: "the
threshold is configuration; here it is set to LOW so you can watch the path
work."

## What we did

Ran the full job twice with `ALERT_MIN_RISK_LEVEL=LOW` against a real MongoDB:

```
Run 1: daily-alert: ok, 2 rows
Run 2: duplicate suppressed: SEOUL/WEEDS/2026-08-10
       duplicate suppressed: BUSAN/WEEDS/2026-08-10
       daily-alert: ok, 0 rows
```

This also discharges M2's idempotency criterion early — "proved by re-running
the job live, demonstrated rather than asserted".

## Evidence

Above, plus `tests/test_alert_idempotency.py` (5 tests against a real mongod,
including an assertion that the `uniq_alert_delivery` index exists — without
that check the other tests would pass vacuously).

## Still open

- Not yet run against a **real Telegram channel**; the sender is in dry-run
  because there is no bot token. That is Week 1's task (Tue 11 Aug).
- Threshold must be returned to `HIGH` before any real channel goes live.
  Nothing enforces that today — a checklist item, not a mechanism.
- The message text is a DRAFT. Needs Giyos's Korean review (Thu 20 Aug) and the
  mentor's approval before it reaches a real person.
