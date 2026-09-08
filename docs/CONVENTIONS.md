# Conventions

Detail behind [`AGENTS.md`](../AGENTS.md). Small and specific on purpose.

## Backend (Python)

- Python 3.11, package manager `uv`. Add deps to `backend/pyproject.toml`.
- Format and lint with `ruff` (line length 100). Both run in CI as errors.
- FastAPI: `Annotated[..., Depends(...)]` for params and deps; return-type
  annotations over `response_model` unless the public shape differs; one HTTP
  operation per function; router-level `prefix`/`tags`.
- Data: SQLModel tables in `backend/app/models`, 1:1 with the ERD. Parse
  untrusted input (KMA/pollen/AQI responses, env config) with Pydantic; don't
  redefine a shape the ERD already owns.
- Enums live once in `backend/app/core/enums.py` as `StrEnum`. Pass
  `RiskLevel.HIGH`, never the string `"HIGH"`.
- Services hold logic; API modules stay thin. Safety logic is deterministic and
  lives in `services/`, never in a prompt or an endpoint body.

## Naming

- Files and functions: `snake_case`. Classes: `PascalCase`. Tables: plural
  `snake_case` matching the ERD (`symptom_events`, `triage_results`).
- Enum values: `UPPER_SNAKE`, matching the spec's allowed values.

## Tests

- `pytest`, tests next to intent in `backend/tests/`. Safety branches
  (triage, risk) get full coverage. A test reproduces the branch it names.

## Git

- Feature branch, PR into `develop`. `main` is stable and deploy-only.
  Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`). Author
  **ismoiljon1101**, no `Co-Authored-By`.

## Config and secrets

- Everything environment-specific comes from `.env` via
  `backend/app/core/config.py`. `.env` is never committed; `.env.example`
  documents the keys. API keys stay server-side.

## Documentation prose

- Follow the human-voice rules in `CLAUDE.md`. No em dashes, active voice, vary
  sentence length, lead with the concrete.
