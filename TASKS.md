---
status: active
owner: Ismoiljon
review-by: 2026-08-16
---

# TASKS — what we are doing right now

One file. Three people. If work is not here, nobody is doing it.

Updated at the Monday task-out and the Wednesday blocker check. Milestones and
their pass criteria come from the kickoff deck and are not renegotiated here.

## How a task is written

Every task carries four things. The middle two are what stop three people — and
their agents — colliding.

| Field | Why |
| --- | --- |
| **Owner** | Exactly one name. Shared ownership is nobody's. |
| **Touches** | The files/directories this task may modify. |
| **Done when** | An observable condition, not "finished". |
| **Blocks** | Who is stuck until this lands. |

`Touches` is the important one. Two tasks whose `Touches` overlap must not run
in parallel — not by people and not by agents. If two tasks need the same file,
either sequence them or split the file.

`Done when` must be checkable by someone who did not do the work. "Idempotency
works" is not a criterion; "re-running the job posts nothing and the run is
recorded" is.

## Statuses

`todo` · `doing` · `review` (PR open, waiting) · `done` (merged, CI green) ·
`blocked` (name the blocker)

---

## Timeline

| | Week | Dates | Gate |
| --- | --- | --- | --- |
| | W0 | 3–9 Aug | Setup |
| ← | **W1** | **10–16 Aug** | **Contracts freeze Sun 16 Aug** |
| | W2 | 17–23 Aug | **M1** — walking skeleton, deployed |
| | W3 | 24–30 Aug | |
| | W4 | 31 Aug–6 Sep | **M2** — feature complete |
| | W5 | 7–13 Sep | Handoff doc |
| | W6 | 14–20 Sep | **M3** — shippable and defensible |

---

## Blocked on someone else

| Task | Owner | Blocks | Status |
| --- | --- | --- | --- |
| Admin on the GitHub repo for `Ismoiljon1101` | **Mentor** | branch protection, CODEOWNERS enforcement — both Week-0 deliverables | blocked |
| Is there a bulk historical KMA dataset? | **Mentor** | Slice A and Slice B entirely — [headache/0001](headache/0001-kma-serves-one-day-of-history.md) | blocked |
| GitHub usernames for Jamshid and Giyos | **Both** | CODEOWNERS has placeholder handles | blocked |
| Confirm: does the alert describe **tomorrow** or today? | **Mentor** | message wording; currently tomorrow, per deck slide 4 | blocked |
| Approve the Korean alert text before a real channel | **Mentor + Giyos** | M1 test post | blocked |

---

## Slice C — Alerts & Delivery · Ismoiljon

| # | Task | Touches | Done when | Status |
| --- | --- | --- | --- | --- |
| C1 | Repo, CI, PR template, CODEOWNERS | `.github/` | nothing merges to main without review + green CI | **done** |
| C2 | Job framework + instrumentation | `components/jobs/` | every run writes a JobRun; failures reach the ops channel | **done** |
| C3 | 07:00 KST job + job CLI | `components/alerts/jobs/`, `scripts/` | re-running posts nothing; both runs recorded | **done** |
| C4 | Idempotency proven on a real DB | `tests/` | index asserted to exist; duplicate insert rejected | **done** |
| C5 | Register the bot; create the first regional channel | — | the bot posts to it manually | todo · **Tue 11 Aug** |
| C6 | Create the private ops channel | `.env` | a forced job failure lands there | todo · **Tue 11 Aug** |
| C7 | Alert history page | `apps/web/src/pages/` | deployed, reads `alertHistory` | todo · W4 |
| C8 | Status page, red when stale > 26h | `apps/web/src/pages/` | deployed | todo · W3 |
| C9 | Rate limiting + backoff for Telegram | `components/alerts/telegram/` | tested against a forced failure | todo · W5 |
| C10 | Handoff document | `docs/` | someone else can run and fix the alert system from it alone | todo · **Wed 9 Sep** |
| C11 | Review every PR within 24h | — | measured weekly from GitHub | **ongoing** |

## Slice A — Forecast Engine · Jamshid

| # | Task | Touches | Done when | Status |
| --- | --- | --- | --- | --- |
| A1 | **Start daily KMA ingest** | `components/forecast/` | two bulletins a day stored for 16 regions | todo · **urgent** |
| A2 | Persistence baseline | `components/forecast/service.py` | `/forecast` serves 3 days from "tomorrow equals today" | todo · W2 |
| A3 | Find or rule out a historical source | — | answered in [headache/0001](headache/0001-kma-serves-one-day-of-history.md) | todo · **urgent** |
| A4 | Train a model that beats the baseline | `ml/` | per-class recall for HIGH and VERY_HIGH in the README | todo · W4 |
| A5 | `MODEL_CARD.md` | `ml/` | what it does, how well, where it is weak | todo · W4 |

> A1 is the only task on this project where **delay destroys the asset**. The
> API keeps one day. Every day without ingest is a (forecast, outcome) pair that
> cannot be recovered later at any price.

## Slice B — Season Analytics · Giyos

| # | Task | Touches | Done when | Status |
| --- | --- | --- | --- | --- |
| B1 | Deployed environment | infra | the app is reachable at a URL | todo · **Sat 15 Aug** |
| B2 | Korean review of the alert text | `components/alerts/message.py` | approved or corrected | todo · **Thu 20 Aug** |
| B3 | Season timing endpoint | `components/analytics/` | returns real numbers for one pollen type | blocked on A3 |
| B4 | Three dashboard charts | `apps/web/src/pages/` | season calendar, length trend, high-risk day counts | blocked on A3 |
| B5 | Answer: has the Seoul ragweed season got longer? | — | a number, with its method | blocked on A3 |

> B3–B5 have no data source today. If [headache/0001](headache/0001-kma-serves-one-day-of-history.md)
> resolves as "no history exists", this slice needs rescoping, and that decision
> belongs to the mentor — not to us, and not silently.

---

## Weekly measures

From GitHub, not self-reported. Being behind is normal; being quiet is not.

| Measure | Target |
| --- | --- |
| Commits on separate days | 4 / week |
| PRs opened | 2+ / week |
| Reviews given on teammates' PRs | 2+ / week |
| Blocker raised within 24h of getting stuck | every time |
| Weekly check-in before Sunday 20:00 | every week |
