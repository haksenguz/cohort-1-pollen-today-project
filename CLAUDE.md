# Pollen Today — working rules for Claude

Project rules live in [docs/CONVENTIONS.md](docs/CONVENTIONS.md) and
[docs/DEFINITION_OF_DONE.md](docs/DEFINITION_OF_DONE.md). Read those before
writing code. What follows is about *how to work*, not what to build.

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

Verification after delegating is always the main agent's job: `pnpm build`,
`pnpm typecheck`, `pnpm lint`, `pnpm test`, and read the diff.

## Decisions

Ismoiljon is Tech Lead and decides. State a disagreement once, with the
reasoning and the trade-off, then implement what he chose. Do not re-litigate a
decision already made.

Architectural decisions get an ADR in `docs/adr/` — including the alternatives
that lost and why. A decision without its rejected alternatives is not
reviewable.

## The contract

`apps/api/src/schema/*.graphql` is hand-written and is the frozen contract.
`apps/api/src/graphql.generated.ts` is derived from it and committed; CI fails
if the two disagree.

Never edit the generated file. After changing SDL:

```bash
pnpm --filter @pollen/api schema:generate
```

A `.graphql` diff needs all three slice owners' sign-off plus an ADR.

## Do not

- Push to `main`. Work on `feat/ismoiljon`, open a PR.
- Fix Slice A or Slice B code. Review it and hand it back — taking someone
  else's problem takes their learning and their resume line with it.
- Hardcode regions, thresholds, URLs, dates, or channel names.
- Commit `.env`, KMA data dumps, or anything under `data/raw/`.
