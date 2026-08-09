---
status: applied
owner: Ismoiljon
opened: 2026-08-09
review-by: 2026-09-06
severity: medium
---

# 0003 — Agent diagnoses were confidently wrong twice, and both cost time

## Symptom

Two delegated tasks came back with a confident, plausible, wrong conclusion. In
both cases the work looked finished.

**Case 1 — "the tests cannot run on this architecture."** An agent reported the
MongoDB integration tests were blocked because MongoDB ships no Windows aarch64
binary, and presented it as the primary blocker.

**Case 2 — "enum members needed a post-processing script."** An agent made
graphql-codegen emit SCREAMING_SNAKE enum members by adding a Node script that
regex-replaced them, with one hardcoded rule per region.

## Real cause

**Case 1: the diagnosis was of the second error, not the first.** The suite died
before Mongo was ever contacted, on schema construction:

```
Invalid schema configuration: `SEOUL` is not a valid type at path `SEOUL`
```

A TypeScript enum is a value as well as a type, so the emitted `design:type`
metadata was the enum *object*, which Mongoose read as a nested schema. The fix
was `type: String` on the property. **That bug would have crashed the API at
startup in production** — it was not a test-only problem, and the architecture
theory hid it.

The architecture claim was also only half true: MongoDB genuinely ships no
Windows aarch64 build, but Windows runs x64 binaries under emulation. Forcing
`{ arch: "x64" }` made the download work.

**Case 2: the wrong layer.** graphql-codegen has
`namingConvention: { enumValues: "keep" }`. The script was unnecessary, and
would have broken silently the first time someone added a region — producing
`Region.Gyeonggi` where every call site expects `Region.GYEONGGI`.

## What the research says

The failure mode is documented: agents optimise locally and produce plausible
fixes for misdiagnosed causes at speed. The countermeasures that hold up are
(a) the human verifies against the running system rather than the agent's
report, and (b) the agent's *reasoning* is checked, not just whether the tests
went green.

Note that in Case 1, accepting the report would have left a production crash in
place while believing the problem was a laptop. The report was not lazy — it was
detailed and confident. Detail is not evidence.

## What we did

- Reproduced both failures directly instead of accepting the summaries.
- Case 1: added `type: String` to every enum-typed property, and forced the x64
  binary in the test setup with a comment explaining why.
- Case 2: deleted the script; used the native `namingConvention` option.
- Wrote the rule into `CLAUDE.md`: delegation is fine, but verification is
  always the main agent's job — `build`, `typecheck`, `lint`, `test`, and read
  the diff.

## Evidence

```
20 passed in 0.38s          # apps/api, against a real mongod
All checks passed!          # ruff
```

Enum output after removing the script:

```ts
export enum Region { BUSAN = 'BUSAN', CHUNGBUK = 'CHUNGBUK', ... }
```

Both fixes are in `cdd97d8`.

## Still open

Nothing on these two. The general lesson is standing: **an agent's report is a
hypothesis until the running system agrees with it.** Case 1 is the one to
retell — the confident wrong answer concealed a production crash.
