# ADR 0003 — Alert idempotency lives in a unique index

Date: 2026-08-04
Status: Accepted
Decider: Ismoiljon (Tech Lead), Slice C

## Context

The alert job runs daily at 07:00 KST. A re-run, a scheduler restart, a retry
after a partial failure, or two instances racing must never post the same alert
twice to a public channel.

## Decision

A unique compound index on `{channel, region, pollenType, targetDate}` in the
`alerts` collection. The job inserts unconditionally; a duplicate fails with
Mongo error `E11000` and is treated as "already sent" — a normal outcome, not
an error.

## Why

The alternative is an application-level check: read whether it was sent, then
send if not. That is a check-then-act race — two workers can both read "not
sent" before either writes. Correctness would depend on there only ever being
one process, which is an assumption nobody can enforce.

A unique index makes the database refuse the duplicate regardless of how many
processes race. Correctness stops depending on our code being careful.

`targetDate` is the day the alert is *about*, not the day it was sent, so a job
that runs late still cannot double-post for the same day.

## Consequences

- Idempotency is provable by re-running the job live, which is exactly what
  Milestone 2 requires.
- The insert path must distinguish `E11000` from other write errors; anything
  else still throws.
- Changing the channel-per-region scheme changes the index, and therefore needs
  a migration.
