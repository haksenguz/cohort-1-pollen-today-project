# Conventions

Binding for all three slices. Set by the Tech Lead in Week 0. Changing a rule
here requires all three owners to agree — the point is that nobody has to guess,
and nobody argues about it in review.

If a rule below and the FastAPI documentation disagree, the FastAPI documentation
wins and this file is wrong. Raise it.

---

## 1. File naming

**snake_case for every Python file.** Multi-word names use underscores.
kebab-case applies only to TypeScript in `apps/web`.
One exception: React components stay `PascalCase.tsx` (§9).

```
job_run.py               service, resolver, or DTO
daily_alert.py           similar
risk_level.py            enum or utility
```

The role goes last, as a suffix, so a directory sorts by name and reads by role:

| Python Suffix | What it holds |
| --- | --- |
| `resolver.py` | GraphQL resolvers |
| `service.py` | business logic |
| `dto.py` | Pydantic `BaseModel` read models |
| `schemas/` | Beanie documents — persistence only |
| `.graphql` | Hand-written SDL — the contract |
| `enums.py` | `StrEnum` declarations |
| `errors.py` | `AppError` subclasses |
| `test_*.py` | pytest tests |

TypeScript in `apps/web` keeps kebab-case: `risk-level.service.ts`, `job-run.component.tsx`.

## 2. The DTO template

DTOs are Pydantic `BaseModel` classes, one per entity, in `dto.py`. Named
`<Thing>DTO`. They represent what the GraphQL schema exposes.

```python
# dto.py
class AlertDTO(BaseModel):
    id: str
    region: str
    risk_level: str
```

Inputs come as resolver keyword arguments (snake_case), not separate input classes.
Beanie documents in `schemas/` stay separate from DTOs — they represent the
database shape. They are allowed to diverge, and that freedom is the reason
they are separate.

## 3. Directory structure

```
apps/api/
  schema/                    hand-written GraphQL SDL — the frozen contract
  src/pollen/
    main.py                  FastAPI app factory, lifespan, scheduler
    settings.py              pydantic-settings configuration
    container.py             service wiring — constructed once
    db.py                    MongoDB connection + Beanie init
    graphql_app.py           schema assembly + error formatter
    components/
      registry.py            aggregates every component's resolvers + documents
      forecast/  analytics/  alerts/  jobs/
        resolver.py          thin — args in, service call, DTO out
        service.py           all logic
        dto.py               Pydantic read models
        schemas/             Beanie documents — persistence only
  tests/
    test_*.py                pytest tests, mirroring source structure
  libs/                      shared, feature-agnostic
    enums.py                 hand-written StrEnum declarations
    errors.py                AppError subclasses
```

**`main.py` never imports a feature module.** Features arrive through
`components/registry.py`. This keeps the app root stable.

Nothing in `libs/` may import from `components/`. The dependency arrow points
one way; a violation means the thing belongs in a component.

**Note:** `schema/` holds GraphQL SDL (hand-written contract), while
`components/<feature>/schemas/` holds Beanie persistence models. They are
different things — do not confuse them.

## 4. Components

- One package per feature (a directory in `components/`), and the service is the
  only public surface.
- Export a service only when another component genuinely needs it.
- No circular imports. A circular dependency means the boundary is wrong —
  restructure instead.
- Service wiring happens in `container.py`, never inside a component.

## 5. Resolvers and services

**Resolvers are thin.** Args in, one service call, DTO out. No business logic,
no database access, no conditionals beyond mapping.

Resolver argument names are snake_case (`region_code`, `risk_level`) because
`convert_names_case=True` converts both field and argument names from the
camelCase SDL to snake_case Python.

**Services hold everything else**, and take no GraphQL types as parameters, so
they stay testable without a GraphQL context.

Database access lives in the service. If a service grows past roughly 200 lines,
split it before it splits itself.

## 6. Enums

- **Enums are declared in the SDL**, in `schema/common.graphql`. That is the
  only place a value is written down.
- Python enums are hand-written `StrEnum` classes in `libs/enums.py` because
  Python cannot generate them from SDL.
- **Hand-writing is acceptable only because** `tests/test_enums_match_sdl.py`
  parses the SDL and fails on drift. This test must never be deleted — it is
  what makes hand-writing safe (ADR 0004).
- Beanie validates against them with `enum_values()` — never a literal array
  copied by hand.
- Values are `SCREAMING_SNAKE_CASE`: `VERY_HIGH`, not `VeryHigh`.
- An enum used only inside one component, and never exposed in the schema, may
  live in that component. Everything in the SDL is shared by definition.

## 7. Errors

- Throw an `AppError` subclass from `libs/errors/`. Never a bare `Error`, never
  a string.
- Every domain error carries a stable `code`. Clients switch on the code; the
  message is for humans and may change.
- Anything that is not an `AppError` is a bug: the filter logs it in full and
  returns an opaque `INTERNAL_ERROR`. Stack traces never reach a client.
- Never `catch` to swallow. Catch to translate, or let it propagate.

## 8. Types

- Use type hints everywhere: `def fetch_alerts(region: str) -> list[AlertDTO]:`.
- Add `from __future__ import annotations` at the top of every module.
- **Parse, do not cast.** Data from outside the system — KMA, the ML artifact,
  env config — goes through a Pydantic validator from `libs/validators.py` or
  `@pollen/contracts`. Casting external data is banned.
- `Any` requires a comment saying why it cannot be typed. `Unknown` or a union
  type plus a type guard is almost always the answer instead.
- Never use an unchecked `dict` for something with structure — use a Pydantic
  model and `.model_validate()`.
- Generic parameters are `T`, `TData` — descriptive when there is more than one.

## 9. Naming inside code

| Thing | Case | Example |
| --- | --- | --- |
| Python class | `PascalCase` | `AlertsService` |
| Python method, property, variable | `snake_case` | `record_delivery` |
| TypeScript class / interface | `PascalCase` | `AlertsService` |
| TypeScript method, property, variable | `camelCase` | `recordDelivery` |
| Module-level constant | `SCREAMING_SNAKE` | `STALE_AFTER_MS` |
| Enum value | `SCREAMING_SNAKE` | `VERY_HIGH` |
| GraphQL field | `camelCase` | `riskLevel` |
| GraphQL type / enum | `PascalCase` | `RiskLevel` |
| Database collection | `snake_case` plural | `job_runs` |
| React component file | `PascalCase.tsx` | `PollenToday.tsx` |

Booleans read as assertions: `is_stale`, `has_more` (Python) or `isStale`, `hasMore` (TypeScript).

## 10. The contract

Hand-written SDL in `apps/api/schema/*.graphql` is the frozen contract.

**A diff in any `.graphql` file is a contract change** and needs all three owners'
written agreement plus an ADR in `docs/adr/`. This is the Week-1 freeze.

Two consumers of the SDL:
- **Ariadne** reads it directly at runtime in the Python API.
- **graphql-codegen** generates TypeScript types for the web into
  `packages/contracts/src/graphql.ts`, which is committed. CI regenerates it
  and fails if it drifts — that is what enforces the freeze, not memory.

After changing any `.graphql` file:

```bash
pnpm --filter @pollen/contracts generate
```

## 11. Configuration

- No hardcoded regions, thresholds, URLs, dates, channel names, or secrets.
  Everything comes from env via `settings.py` (pydantic-settings), or from
  `@pollen/contracts`.
- Every new env var goes in `.env.example` in the same commit.
- `.env` is never committed.

## 12. Git

- Branch per person: `feat/ismoiljon`, `feat/jamshid`, `feat/giyos`.
- Never push to `main`. Everything goes through a PR.
- Conventional Commits: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`.
  Subject in the imperative, 50 characters or fewer.
- Commit on at least four separate days a week — the history is graded on being
  incremental, not on one final dump.

## 13. Tests

- `test_*.py` under `apps/api/tests/`, mirroring the source structure.
- Test behaviour, not implementation. A test that breaks on a rename but not on
  a logic change is testing the wrong thing.
- Integration tests need a real MongoDB (`MONGODB_TEST_URI`), never a mock,
  because the idempotency guarantee is enforced by the database.
- Every bug fix ships with the regression test that would have caught it.

## 14. Review

- Every PR needs one approval and green CI before merge.
- Review within 24 hours — measured, and the highest-leverage thing the tech
  lead does.
- **Reviewers do not fix the code.** Ask a question, point at the concept, hand
  it back. Fixing someone's PR takes the learning and the resume line away from
  them.

---

See also: [DEFINITION_OF_DONE.md](DEFINITION_OF_DONE.md) and [adr/](adr/).
