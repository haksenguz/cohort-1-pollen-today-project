---
status: active
owner: Ismoiljon
review-by: 2026-09-20
---

# headache/ — what hurt, and whether we fixed it

Problems that cost real time. Each one records what happened, what the research
said the right answer was, what we actually did, and whether it is verified in
the running system.

## Why this exists

A problem solved and not written down gets solved again by the next person, or
worse, gets re-broken. And the specific failure mode with AI agents is
confident wrongness at speed — an agent will produce a plausible fix for a
misdiagnosed cause in seconds. Writing down *the real cause* is what stops the
same wrong fix returning.

Two of these already exist because an agent's diagnosis was wrong and the fix
only worked once someone checked.

## Lifecycle

Every headache has exactly one status. Move it, never delete it.

| Status | Means |
| --- | --- |
| `researching` | We know it hurts. We do not yet know the right fix. |
| `implementing` | We know the fix. It is not finished or not verified. |
| `applied` | Fixed **and proven in the running system**, with the evidence quoted. |
| `accepted` | We are living with it on purpose, and the reason is written down. |
| `superseded` | Overtaken by a bigger change. Links to what replaced it. |

`applied` requires evidence — a command's output, a test name, a log line. "It
should work now" is `implementing`.

## Template

```markdown
---
status: researching | implementing | applied | accepted | superseded
owner: <name>
opened: YYYY-MM-DD
review-by: YYYY-MM-DD
severity: blocker | high | medium | low
---

# NNNN — <one line, the symptom not the cause>

## Symptom
What we saw. Exact error text.

## Real cause
What it actually was — often not the first theory. Say what the first theory
was and why it was wrong; that is the part that saves the next person.

## What the research says
Best practice, with sources.

## What we did
The change, and where it lives.

## Evidence
The output that proves it. Not a claim.

## Still open
Anything unresolved.
```

## Index

| # | Headache | Status | Severity |
| --- | --- | --- | --- |
| [0001](0001-kma-serves-one-day-of-history.md) | KMA serves one day of history, and no observations | researching | blocker |
| [0002](0002-cannot-test-the-high-risk-path.md) | The whole alert path is untestable while the index is LOW | implementing | high |
| [0003](0003-agent-diagnoses-are-confidently-wrong.md) | Agent diagnoses were wrong twice; both cost real time | applied | medium |
