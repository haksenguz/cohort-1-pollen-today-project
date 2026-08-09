# Pollen Today — working rules for Claude

Project rules live in [docs/CONVENTIONS.md](docs/CONVENTIONS.md) and
[docs/DEFINITION_OF_DONE.md](docs/DEFINITION_OF_DONE.md). Read those before
writing code. What follows is about *how to work*, not what to build.

## Where things live

Four places, no overlap. Putting a thing in the wrong one is how documentation
rots.

| Folder | Answers | Changes when |
| --- | --- | --- |
| `research/` | What is true about the world? | reality changes, or we measure again |
| `headache/` | What hurt us, and did we fix it? | we hit or resolve a problem |
| `docs/adr/` | What did we decide, and what lost? | an architectural choice is made |
| `TASKS.md` | What are we doing right now? | daily |

Every file in `research/` and `headache/` carries frontmatter with `status`,
`owner` and `review-by`. That is the staleness mechanism — "is this still true?"
becomes a date comparison rather than a judgement call.

Before starting non-trivial work: read `TASKS.md` for the task's `Touches`
boundary, and check `headache/` for whether the problem is already known. Two
tasks whose `Touches` overlap must not run in parallel.

## Delegate the manual work

When a task is mechanical, well-specified, and splits into independent pieces,
spawn cheap subagents (haiku) in parallel rather than grinding through it
serially. Then verify their output yourself before it lands — the review is not
optional, and the agents' work is not trusted until it builds and passes.

Good candidates:

- Applying one rename or import rewrite across many files
- Updating several documentation files for the same decision
- Writing tests for several independent modules
- Filling in boilerplate from an established template

Do NOT delegate when:

- The files import each other. Parallel writers on coupled files produce
  conflicts, not throughput, and reconciling costs more than writing.
- The task needs a judgement call that has not been made yet.
- It is fewer than about three files. Spawn overhead exceeds the saving.

Verification after delegating is always the main agent's job. For the API:
`uv run ruff check . && uv run ruff format --check . && uv run pytest`. For the
web: `pnpm build && pnpm typecheck && pnpm lint`. Then read the diff.

**An agent's report is a hypothesis until the running system agrees with it.**
This has already cost us twice, once concealing a crash that would have hit
production — see [headache/0003](headache/0003-agent-diagnoses-are-confidently-wrong.md).
Reproduce the failure yourself before accepting a diagnosis, and check the
reasoning, not just whether the tests went green.

## Decisions

Ismoiljon is Tech Lead and decides. State a disagreement once, with the
reasoning and the trade-off, then implement what he chose. Do not re-litigate a
decision already made.

Architectural decisions get an ADR in `docs/adr/` — including the alternatives
that lost and why. A decision without its rejected alternatives is not
reviewable.

## The contract

`apps/api/schema/*.graphql` is hand-written and is the frozen contract. It has
two consumers:

- the Python API loads it directly at runtime (Ariadne, schema-first)
- `packages/contracts/src/graphql.ts` is generated from it for the web app and
  committed; CI fails if the two disagree

Never edit the generated file. After changing SDL:

```bash
pnpm --filter @pollen/contracts generate
```

Python enums in `apps/api/src/pollen/libs/enums.py` are hand-written because
Python cannot generate them from SDL. `tests/test_enums_match_sdl.py` fails on
drift — that test is what makes hand-writing acceptable. Never delete it.

A `.graphql` diff needs all three slice owners' sign-off plus an ADR.

## Where enums and types come from — READ THIS BEFORE WRITING FRONTEND CODE

Applies to `apps/web` only. The Python API imports from
`pollen.libs.enums` instead — same values, different language, kept in step by
`tests/test_enums_match_sdl.py`.

**One import path for the web app: `@pollen/contracts`.**

```ts
import {
  Region, PollenType, RiskLevel, JobStatus,   // enums — real TS enums
  Forecast, Alert, PaginatedAlert, JobRun,    // response types
  ALL_REGIONS, riskAtLeast,                   // helpers
} from "@pollen/contracts";
```

All of it is generated from the SDL, so the API and the web app cannot disagree
about a field name, a type, or what counts as a valid region.

**Never do these:**

| Don't | Do |
| --- | --- |
| Write `interface Forecast { … }` in `apps/web` | Import `Forecast` from `@pollen/contracts` |
| Write `type Region = "SEOUL" \| "BUSAN"` | Import the `Region` enum |
| Write `const REGIONS = ["SEOUL", …]` | Use `ALL_REGIONS` |
| Pass `"WEEDS"` as a string literal | Pass `PollenType.WEEDS` |
| Import from `apps/api/**` | Import from `@pollen/contracts` |
| Edit `packages/contracts/src/graphql.ts` | Edit the `.graphql` file, regenerate |

These are **enums, not string unions** — `RiskLevel.HIGH`, not `"HIGH"`. A bare
string will not typecheck, and that is deliberate: it is what stops a typo in a
region name reaching a real Telegram channel.

On the Python side the same rule holds with Pydantic: parse **untrusted input
only** — KMA responses, the ML artifact, env config. Do not write a second
definition of a payload the SDL already defines; it drifts (ADR 0004).

Frontend query documents go in `apps/web/src/lib/queries.ts`. Write the query
string and its `Vars` interface there; take the result type from
`@pollen/contracts`.

## Do not

- Push to `main`. Work on `feat/ismoiljon`, open a PR.
- Fix Slice A or Slice B code. Review it and hand it back — taking someone
  else's problem takes their learning and their resume line with it.
- Hardcode regions, thresholds, URLs, dates, or channel names.
- Commit `.env`, KMA data dumps, or anything under `data/raw/`.
