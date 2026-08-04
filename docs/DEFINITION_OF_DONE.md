# Definition of Done

Applies to **every** task, on every slice, for six weeks. Distinct from
acceptance criteria, which are specific to one piece of work — this list never
changes and is never waived because a deadline is close.

A task is done when all of the following are true.

## Code

- [ ] `pnpm build`, `pnpm typecheck`, `pnpm lint`, `pnpm format:check` all pass
- [ ] `pnpm test` passes; new behaviour has a test, bug fixes have a regression test
- [ ] No hardcoded regions, thresholds, URLs, dates, or secrets. Config or
      `@pollen/contracts` only.
- [ ] No `any` added without a comment explaining why it cannot be typed
- [ ] Data crossing a boundary is **parsed** with a Zod schema, never cast

## Review

- [ ] Opened as a PR from a personal branch — never pushed straight to `main`
- [ ] Reviewed and approved by someone else
- [ ] CI green before merge, not after

## Contract

- [ ] Changes to `packages/contracts` are approved by all three slice owners in
      writing, and recorded as an ADR in `docs/adr/`

## Documentation

- [ ] README updated if setup, env vars, or architecture changed
- [ ] `.env.example` updated if a new env var was introduced

## Deployed

- [ ] Merged to `main` and deployed. Work that only runs on a laptop is not done.
