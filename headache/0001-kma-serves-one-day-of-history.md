---
status: researching
owner: Jamshid (Slice A) · escalated by Ismoiljon
opened: 2026-08-09
review-by: 2026-08-16
severity: blocker
---

# 0001 — KMA serves one day of history, and no observations

## Symptom

```
resultCode 99 — 최근 1일 간의 자료만 제공합니다
```

Returned for any `time` older than roughly a day. Tested at 2025-09-01 and at
three days prior; both refused.

## Real cause

Not a bug and not a key permission — it is the documented behaviour. Every
operation carries `(최근 발표자료로 제한)`.

The deeper problem, which is easy to miss: **every value this API returns is a
forecast.** `today / tomorrow / dayaftertomorrow / twodaysaftertomorrow` are all
KMA predictions. There is no observed-value series anywhere in the service.

## What this breaks

| Requirement | Source | Status |
| --- | --- | --- |
| "Load 5+ years of KMA pollen index" | Slice A brief | no source |
| "Multi-year analysis, starts day one" | Slice B brief | no source |
| "Beats the persistence baseline, per-class recall" | Deck slide 14 | **nothing to score against** |

The third is the serious one. Measuring a model requires ground truth. With only
forecasts available, a model can at best learn to imitate KMA's forecast, and
cannot be evaluated against what actually happened.

There is also a product question nobody has asked out loud: KMA already
publishes the three-day forecast. Slice A as briefed would predict a thing that
arrives pre-predicted.

## What the research says

Two options, not mutually exclusive.

**A. Find the real historical source.** This API is the *index* service. KMA's
기상자료개방포털 and 국립기상과학원 publish bulk observation datasets on
different services. Unverified — nobody has looked yet, and it is the single
highest-value hour available on this project.

**B. Accumulate our own ground truth, starting immediately.** `today` is KMA's
nowcast — the closest thing to an observation the API has. Storing every
bulletin yields pairs:

> `tomorrow` recorded on day D−1 → `today` recorded on day D

That is (forecast, outcome) for the same date. From it: an honest accuracy
measurement, a real persistence baseline, and training labels.

Six weeks to M3 across 16 regions is ~40 paired days. Thin, but real and
defensible — and infinitely better than a model with no ground truth.

**Option B decays.** Every day without ingest is a pair that cannot be
recovered; the API will not sell it back. It is the only task on this project
where delay destroys the asset rather than postponing it.

## What we did

Nothing yet — this is Slice A's to own, and taking it would take Jamshid's
learning and his resume line with it.

Unblocked on our side: the region enum and `REGION_AREA_NO` are verified
(ADR 0005), the `"0".."3"` mapping is in `libs/enums.py`, and the empty-string
rule is enforced and tested. The ingest job has everything it needs.

## Evidence

See [research/0001](../research/0001-kma-api-capabilities.md) — verified against
the live service on 2026-08-09.

## Still open

- Does a bulk historical dataset exist on another KMA service? **Nobody has looked.**
- Does the mentor already know of one? Not yet asked.
- If not, is Slice A reframed around measuring and delivering KMA's forecast
  rather than replacing it? That is his call, not ours.
- Ingest has not started. The cost is one lost day per day.
