# AGENTS.md — how agents contribute to this repo

Read by Claude Code, Cursor, Copilot, Codex and anything else that honours the
convention. If you are an AI agent working in this repository, this file is
binding. If you are a human, this is what your agent has been told.

`CLAUDE.md` carries the same rules for Claude Code specifically. When the two
disagree, this file wins and `CLAUDE.md` is out of date — say so.

---

## The one rule everything else follows from

**Your report is a hypothesis until the running system agrees with it.**

This has already cost this project twice. Once an agent reported the test suite
was blocked by the machine's CPU architecture; the real failure was a schema
crash that would also have taken down production, and the confident report hid
it. See [headache/0003](headache/0003-agent-diagnoses-are-confidently-wrong.md).

Detail is not evidence. A long explanation of why something works is not the
same as having run it.

---

## Before you touch anything

1. **Read [TASKS.md](TASKS.md).** Find your task. If it is not there, it does
   not exist — say so rather than inventing it.
2. **Check its `Touches` boundary.** That is the list of files you may modify.
   Not a suggestion: it is how three people and their agents avoid writing over
   each other.
3. **Search [headache/](headache/).** If the problem is already known, the fix,
   the failed first attempt, and the current status are recorded. Do not
   rediscover it.
4. **Check [research/](research/)** for facts about the outside world — the KMA
   API, the data, the users. Do not guess a field name that is written down.
5. **Read the relevant [ADR](docs/adr/).** Decisions include the alternatives
   that lost. Re-proposing a rejected alternative without addressing why it lost
   wastes a review cycle.

## While you work

**Stay inside `Touches`.** If the task genuinely needs a file outside it, stop
and say so. Do not quietly widen the scope — that is precisely the collision the
boundary exists to prevent.

**One task at a time.** Two tasks whose `Touches` overlap must never run in
parallel, whether by people or by agents.

**Never invent a number.** Statistics, recall figures, response times and dates
either come from something you ran or from a cited source. If it is an estimate,
write "estimate".

**Prefer the smallest change that satisfies `Done when`.** Refactors that were
not asked for are someone else's merge conflict.

## Before you claim it is done

Run these. Not "these should pass" — run them and paste what happened.

```bash
cd apps/api && uv run ruff check . && uv run ruff format --check . && uv run pytest
```

```bash
pnpm build && pnpm typecheck && pnpm lint && pnpm format:check
```

Then **read your own diff**. Most bad changes are obvious on a second look and
invisible while writing.

## How to report

Say what you **verified**, not what you did.

- "22 tests pass, including the new one that asserts the unique index exists" —
  useful.
- "Implemented idempotency" — not useful. Idempotency is a claim; the test is
  the evidence.

**Say what you did not check.** An honest gap is worth more than a confident
summary, and it is the thing a reviewer needs most. If you could not run
something, say which command and what stopped you.

If you were wrong earlier in the task, say so plainly and move on.

## When you learn something, write it down

| You found | Goes in | Notes |
| --- | --- | --- |
| A fact about the outside world | `research/NNNN-*.md` | Say whether you verified it or read it |
| A problem that cost real time | `headache/NNNN-*.md` | Record the wrong first theory too |
| An architectural decision | `docs/adr/NNNN-*.md` | Include the alternatives that lost |
| Work to be done | `TASKS.md` | With Owner, Touches, Done when |

Every `research/` and `headache/` file needs frontmatter: `status`, `owner`,
`review-by`. That date is the whole staleness mechanism — it turns "is this
still true?" into a comparison instead of a judgement call.

Four folders, no overlap. Putting a thing in the wrong one is how documentation
rots.

## Hard limits

- **Never push to `main`.** Personal branch, then a pull request.
- **Never edit `packages/contracts/src/graphql.ts`** — generated. Edit the SDL
  and regenerate.
- **Never edit another slice's directory.** Slice ownership is in `TASKS.md`.
  Reviewing someone's code and handing it back is the job; fixing it for them
  takes their learning and their resume line.
- **Never change `apps/api/schema/*.graphql`** without all three owners' written
  agreement plus an ADR. That is the Week-1 contract freeze.
- **Never commit** `.env`, API keys, KMA data dumps, or anything under
  `data/raw/`.
- **Never hardcode** regions, thresholds, URLs, dates or channel names. Config
  or `libs/enums.py`.
- **A human merges.** An agent may review; it never signs off.

## Traps this codebase has already hit

Recorded because each one looked correct and was not.

- **A lambda registered with APScheduler never runs.** The scheduler inspects
  the callable — a coroutine *function* is awaited, anything else is called and
  discarded. `lambda: f()` is not `async def f()`.
  [headache/0004](headache/0004-scheduled-job-never-fires.md)
- **An empty string from KMA is not zero.** `""` means "not published". Reading
  it as `0` publishes a false all-clear, which is the one bug here that could
  actually mislead a person.
  [research/0001](research/0001-kma-api-capabilities.md)
- **The KMA manual has two errors.** The working weeds endpoint is the one whose
  name contains a typo, and the oak season is March, not April. Trust the
  service over the document.
- **The pollen observation network covers 8 cities; our regions are 16 시/도.**
  They do not align. Mixing them yields a chart that is wrong invisibly.
  [research/0003](research/0003-korea-historical-pollen-data.md)

## What agents are good at here, and what they are not

Delegate freely: mechanical renames, applying one decision across many docs,
boilerplate from an established template, tests for independent modules.

Do not delegate: anything where the files import each other (parallel writers
produce conflicts, not throughput), anything needing a judgement call nobody has
made yet, or anything under about three files — spawn overhead exceeds the
saving.

Whoever delegated verifies. That is not optional, and it is the entire reason
this workflow is faster rather than merely noisier.
