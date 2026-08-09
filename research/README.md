---
status: active
owner: Ismoiljon
review-by: 2026-09-20
---

# research/ — what we learned about the world

Findings about things **outside** our control: the KMA API, the market, users,
regulations, competitors. Durable knowledge that would otherwise live in one
person's head or scroll past in Telegram.

## Why this exists

Three people and AI agents are working on one product. Everyone — human and
agent — needs the same facts, and needs to know which facts are still true. A
number quoted from memory in week 5 that came from a guess in week 1 is how
projects ship the wrong thing confidently.

## The four folders, and what goes where

Keep these separate. Overlap is how documentation rots.

| Folder | Answers | Changes when |
| --- | --- | --- |
| `research/` | *What is true about the world?* | reality changes, or we measure again |
| `headache/` | *What hurt us, and did we fix it?* | we hit a problem, or resolve one |
| `docs/adr/` | *What did we decide, and what lost?* | we make an architectural choice |
| `TASKS.md` | *What are we doing right now?* | daily |

A finding is research. A decision made because of it is an ADR. A problem it
caused is a headache. The work to fix it is a task.

## Rules

**Every file carries frontmatter.** `status`, `owner`, `review-by`. This is the
whole staleness mechanism: "is this still true?" becomes a date comparison
instead of a judgement call, which is the one part of documentation upkeep that
can actually be automated.

```yaml
---
status: active | superseded | archived
owner: <name>
review-by: YYYY-MM-DD
supersedes: 0003-old-thing.md   # when applicable
---
```

**Verified beats cited.** If we ran the request ourselves, say so and paste the
response. If we read it in a PDF, say that instead. A finding that was never
tested is a hypothesis, and must be labelled one.

**One finding per file**, numbered, never renumbered. Files are appended to, not
rewritten — when something turns out wrong, mark it `superseded` and write a new
one that says why. The wrong belief is part of the record.

**Link to the decision it caused.** A finding nobody acted on is either not
important or a task nobody has filed yet.

## Index

| # | Finding | Status | Review by |
| --- | --- | --- | --- |
| [0001](0001-kma-api-capabilities.md) | KMA HealthWthrIdxServiceV3 — what it actually serves | active | 2026-09-01 |
| [0002](0002-user-need-and-market.md) | Who this is for, and the size of the gap | active | 2026-09-20 |
| [0003](0003-korea-historical-pollen-data.md) | Historical pollen data exists — 8 stations, 2007+ — just not on our API | active | 2026-08-23 |
