---
status: active
owner: Ismoiljon
review-by: 2026-09-20
verified: partially — see "What is still a hypothesis"
---

# 0002 — Who this is for, and the size of the gap

## The need, in one sentence

A person with seasonal allergies finds out that **tomorrow** will be a
high-pollen day in their region, in time to do something about it.

Everything else is scope. If a feature does not serve that sentence, it does not
get built.

## Why the need exists at all

The data is already public, free, and accurate. It sits inside a government
weather portal that people visit only when they already know to look — by which
time they are looking *because* their eyes are streaming.

Allergy medication works best when it is already in the system before exposure.
The gap is not information scarcity. It is **delivery timing**. That is the
entire product, and it is why the alert job matters more than the model.

## Population (from the kickoff deck, citing KNHANES)

| Figure | Value |
| --- | --- |
| Korean adults with allergic rhinitis | 17.1% |
| School-age children with allergic rhinitis | 27.6% |

Roughly one in six adults and more than one in four school-age children. Not a
niche product.

**Not independently verified.** These come from the mentor's deck citing
KNHANES. Before either number appears in a README, a demo, or a resume bullet,
one of us should trace it to the KNHANES publication and record the year — a
statistic quoted from a slide is a statistic nobody can defend in an interview.

## Delivery channel

Public Telegram channels, one per region. The consequence is worth stating
positively rather than as a limitation: **there is no subscriber table.** No
accounts, no email, no phone numbers, no consent flow to get wrong, no deletion
request we can fail to honour.

Designing the personal data out of the system entirely is a stronger position
than securing it well, and it is a good answer at any Korean company that has
been through a PIPA audit.

## Deliberately not built

Each of these has killed a student project of this size: medical advice,
accounts, GPS precision, a mobile app, an LLM chat layer, forecasts beyond three
days, live oak/pine (off-season during the run), payments, admin panels, roles.

## What is still a hypothesis

Marked honestly, because the difference matters:

- **The KNHANES figures** — cited, not traced.
- **That people will follow a Telegram channel for this.** Assumed. Zero
  evidence. The cheapest possible test is one real channel and a link, which the
  project produces by M2 anyway.
- **That the evening-before / morning-of distinction matters to users.** We
  assume a 07:00 alert about *tomorrow* beats one about today. Reasoned from the
  north-star sentence, never tested.
- **Whether anyone else already does this in Korea.** No competitive scan has
  been run. Worth 30 minutes before the demo, if only so nobody is surprised by
  the question.

## What this implies for build order

The product's value is delivery, and delivery is the part that already works.
The model is the part with no data ([headache/0001](../headache/0001-kma-serves-one-day-of-history.md)).
If time runs out, a service that reliably forwards KMA's own forecast to the
right people at the right hour is still the product described above — the ML is
what makes it defensible in an interview, not what makes it useful.
