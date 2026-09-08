# Definition of Done

A change is done when every box holds. Not when the agent says so — when the
system agrees. Acceptance criteria use EARS ("when X, the system shall Y") so a
human and a model read them the same way.

## Every change

- [ ] It traces to the spec (`docs/pollen_documentation.md`) or to an ADR that
      changed the spec. No feature exists that nobody decided on.
- [ ] Backend gate passes locally:
      `cd backend && uv run ruff check . && uv run ruff format --check . && uv run pytest`
- [ ] CI is green on the PR.
- [ ] Branch is `feat/ismoiljon`, opened as a PR, commit author is
      **ismoiljon1101**, no `Co-Authored-By`.
- [ ] No hardcoded regions, thresholds, coordinates, URLs, or secrets.
- [ ] Enums/types come from `backend/app/core/enums.py`, not redefined inline.
- [ ] Prose follows the human-voice rules. UI copy says what the control does.

## Safety-critical code (triage, risk, anything gating a health message)

- [ ] The decision is deterministic and lives in a rule engine, not a prompt.
- [ ] When a red-flag symptom or breathing/swelling is present, the system shall
      return `EMERGENCY` and halt the normal recommendation flow (doc §4).
- [ ] Every branch has a test. When severity ≥ 7 and no red flag, the system
      shall return `MODERATE`; otherwise `LOW`.
- [ ] The rule version is recorded with each result so a decision is auditable.
- [ ] Tests reproduce the failure/branch, not just assert a happy path.

## New endpoint

- [ ] Request and response are typed (Pydantic / SQLModel), untrusted input is
      validated.
- [ ] When input is out of range, the system shall reject it with a 4xx and a
      message that says how to fix it.
- [ ] External API keys stay server-side. The frontend never sees them.
- [ ] It appears in `/docs` (OpenAPI) with a sensible tag.

## Data model change

- [ ] Edited `docs/erd/gen_dmm.py`, regenerated `allergy_ai.dmm` and
      `backend/db/init/01_schema.sql`. Generated files were not hand-edited.
- [ ] The SQLModel tables in `backend/app/models` still match the ERD.

## Before you call it done

Reproduce the behaviour yourself. Read the diff. If a test went green, check it
tests the thing you think it tests. An agent's diagnosis is a hypothesis until
you have seen the system do the right thing.
