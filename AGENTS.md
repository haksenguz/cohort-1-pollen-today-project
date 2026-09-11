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
   `github.com/haksenguz/cohort-1-pollen-today-project`. Ismoiljon works on
   `feat/ismoiljon`, Jack works on `feat/jack`, both merge into `main`. Keep
   the `Ismoiljon1101` fork (`mine`) in sync. Never commit or push as Claude,
   never a `Co-Authored-By` trailer, never force-push `main`.
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

## Frontend styling — Tailwind v4 (CSS-first), NOT v3

The FE ships on Tailwind v4. The styling decision is recorded in
[ADR 0003](docs/adr/0003-tailwind-v4-frontend-styling.md). Raw design
tokens (colors, fonts, spacing) live in `:root` inside `frontend/src/styles/theme.css`;
a non-inline `@theme` block maps them to Tailwind utilities. Dark mode
runtime toggle (`data-theme="dark"`) keeps working because tokens are
raw CSS vars, not `@theme inline`.

When writing Tailwind in this repo, **never**:

- Create or reference `tailwind.config.js`. v4 is CSS-first; the file
  does not exist and v4 ignores it if it does.
- Use `@tailwind base;` / `@tailwind components;` / `@tailwind utilities;`.
  The single import is `@import "tailwindcss";` at the top of `theme.css`.
- Use `@apply`. Deprecated in v4; use utilities directly in JSX.
- Use `bg-gradient-to-r` — the v4 name is `bg-linear-to-r`.
- Use `bg-opacity-50` — the v4 syntax is `bg-black/50` (slash opacity).
- Use `dark:bg-foo` to swap a token for its dark value. The
  `@custom-variant dark` already wires tokens automatically; just write
  `bg-foo` and dark-mode switching follows the CSS var override in
  `:root[data-theme="dark"]`.

When writing Tailwind in this repo, **always**:

- Read `frontend/src/styles/theme.css` before adding a new token. Append
  to `:root` first, then to `@theme`. Never define a `--color-*` token
  inline in a JSX className (`bg-[#2f7d57]` is forbidden — token-only).
- Reuse `riskClass()`, `formatRisk()`, `formatPollen()` from
  `frontend/src/utils/format.ts` for risk-level / pollen-level class
  names and labels. Never invent color or label logic in a component.
- Keep `theme.css` append-only for new rules during migration; never
  reformat existing sections.
- When a JSX element ends up with more than five utility classes that
  describe one logical thing (e.g. a card), extract a `@utility` block
  in `theme.css` or a small React component instead of repeating the
  utility chain everywhere.

The `ofershap/tailwind-best-practices` skill is installed locally to
catch v3 anti-patterns AI agents produce by default. If your output
includes any v3 syntax, the build or a follow-up pass will flag it.

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
