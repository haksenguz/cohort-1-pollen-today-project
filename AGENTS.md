# AGENTS.md — the contract every agent follows

Any agent working in this repo, in any tool, reads this first. It is short on
purpose. Long instruction files stop being followed once they pass roughly
150–200 rules, so this file stays tight and points to detail instead of inlining
it. Where this file and `CLAUDE.md` disagree, this file wins.

The spec is [`docs/pollen_documentation.md`](docs/pollen_documentation.md). It is
the approved source of truth for what we build. Code serves the spec, not the
other way round.

## CRITICAL — hard rules, a violation blocks the change

1. **The rule engine owns every safety decision.** The LLM extracts and
   converses only. Emergency/moderate/low is decided by
   `backend/app/services/triage.py`, never by a model. See doc §4, §23 and
   [ADR 0001](docs/adr/0001-llm-does-not-decide-safety.md).
2. **Never invent Ismoiljon's facts or a patient's.** No fabricated numbers,
   symptoms, or clinical claims. Sample data is labelled as sample.
3. **Push identity and the repo flow are fixed.** Commit and push as
   **ismoiljon1101** (`ismoiljonedu@gmail.com`). The team repo is `origin` =
   `github.com/haksenguz/cohort-1-pollen-today-project`. Work on a feature
   branch, open a PR into `develop`; `main` is stable and deploy-only. Keep the
   `Ismoiljon1101` fork (`mine`) in sync. Never commit or push as Claude, never
   a `Co-Authored-By` trailer, never force-push `main`.
4. **A change is not done until it builds and its tests pass** on your machine.
   An agent's report is a claim; the running system is the proof. See
   [DEFINITION_OF_DONE](docs/DEFINITION_OF_DONE.md).
5. **Follow the spec, or change the spec first.** Deviating from
   `docs/pollen_documentation.md` needs an [ADR](docs/adr/) that records the
   decision and the rejected alternative. No silent drift.

## IMPORTANT — expected of every change

6. Work on `feat/ismoiljon`, open a PR. Do not push to `main`.
7. Enums and shapes come from one place. Python:
   `backend/app/core/enums.py`. Do not redefine a payload the spec already
   defines.
8. The ERD is `docs/erd/allergy_ai.dmm`. Change it by editing
   `docs/erd/gen_dmm.py` and regenerating (it also emits
   `backend/db/init/01_schema.sql`). Never hand-edit the generated files.
9. Read `TASKS.md` before non-trivial work. Two tasks whose `Touches` overlap do
   not run in parallel.
10. Backend Python uses `uv`. Web uses `pnpm`, never `npm`/`yarn`.
11. Don't hardcode regions, thresholds, URLs, coordinates, or channel names.
    They come from config or the spec.
12. Prose a human reads (docs, PR bodies, UI copy) follows the human-voice rules
    in `CLAUDE.md`. No em dashes, active voice, vary sentence length.

## ADVISORY — do this unless there's a reason not to

13. Small, single-purpose commits. Conventional Commits style.
14. Prefer the smallest change that satisfies the spec. Start narrow.
15. When a task is mechanical and splits cleanly, delegate to cheap subagents,
    then verify their output yourself. Their work is a hypothesis until it
    builds green.

## How the repo is kept (four homes, no overlap)

| Folder | Answers | Changes when |
| --- | --- | --- |
| `docs/pollen_documentation.md` | What are we building? | the approved spec changes |
| `docs/research/` | What is true about the world? | reality changes, or we re-measure |
| `docs/headache/` | What hurt us, did we fix it? | we hit or resolve a problem |
| `docs/adr/` | What did we decide, what lost? | an architectural choice is made |
| `TASKS.md` | What are we doing right now? | daily |

Files in `docs/research/` and `docs/headache/` carry `status`, `owner`, `review-by`
frontmatter so "is this still true?" is a date check, not a guess.

## The gate

Before a PR is green, this must pass locally and in CI:

```bash
cd backend && uv run ruff check . && uv run ruff format --check . && uv run pytest
```

All checks are errors, not warnings. The gate is not advisory.
