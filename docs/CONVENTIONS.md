# Conventions

Binding for all three slices. Set by the Tech Lead in Week 0. Changing a rule
here requires all three owners to agree — the point is that nobody has to guess,
and nobody argues about it in review.

If a rule below and the NestJS documentation disagree, the NestJS documentation
wins and this file is wrong. Raise it.

---

## 1. File naming

**kebab-case for every file.** Multi-word names use hyphens, never camelCase,
never snake_case, never PascalCase — with one exception, React components (§9).

```
risk-level.enum.ts        not riskLevel.enum.ts, not risk_level.enum.ts
job-run.schema.ts         not jobRun.schema.ts
graphql-exception.filter.ts
```

The role goes last, as a suffix, so a directory sorts by name and reads by role:

| Suffix | What it holds |
| --- | --- |
| `.module.ts` | `@Module` |
| `.resolver.ts` | `@Resolver` |
| `.service.ts` | `@Injectable` business logic |
| `.dto.ts` | Re-exports the generated GraphQL type |
| `-input.dto.ts` | Re-exports the generated input type |
| `-update.dto.ts` | Input for a mutation that updates |
| `.graphql` | Hand-written SDL — the contract |
| `.schema.ts` | Mongoose `@Schema` — persistence only |
| `.enum.ts` | One enum |
| `.scalar.ts` | Custom GraphQL scalar |
| `.filter.ts` / `.guard.ts` / `.interceptor.ts` / `.pipe.ts` | Nest lifecycle classes |
| `.spec.ts` | Tests |

## 2. The DTO template

Every entity gets up to three DTOs. Build the ones the entity actually needs —
an unused `-update.dto.ts` for a read-only entity is dead code, so it lands when
the mutation lands, not before.

```
dto/alert.dto.ts          read   — @ObjectType, what queries return
dto/alert-input.dto.ts    input  — @ArgsType/@InputType, what we accept
dto/alert-update.dto.ts   update — input for the update mutation
```

**DTOs are never Mongoose documents and never leak `_id`.** The persistence
shape lives in `schemas/`; the exposed shape lives in `dto/`. They are allowed
to diverge, and that freedom is the reason they are separate.

## 3. Directory structure

```
src/
  app.module.ts              infrastructure only — GraphQL, Mongo, config, schedule
  schema/                    hand-written GraphQL SDL — the frozen contract
  graphql.generated.ts       generated types from SDL, committed + CI diff-checked
  components/
    components.module.ts     imports + exports every feature module
    <feature>/
      <feature>.module.ts
      <feature>.resolver.ts
      <feature>.service.ts
      dto/
      schemas/               Mongoose persistence — kept separate from GraphQL
  libs/                      shared, feature-agnostic
    enums/
    errors/
    scalars/
    types/
```

**`app.module.ts` never imports a feature module.** Features arrive through
`ComponentsModule`. Adding a component is one line in `components.module.ts` —
which keeps the file three people are most likely to conflict on stable.

Nothing in `libs/` may import from `components/`. The dependency arrow points
one way; a violation means the thing belongs in a component.

**Note:** `src/schema/` holds GraphQL SDL (hand-written contract), while
`components/<feature>/schemas/` holds Mongoose persistence models. They are
different things — do not confuse them.

## 4. Modules

- One module per feature, and the module is the only public surface.
- Export a service only when another component genuinely needs it.
- No `forwardRef()`. A circular dependency means the boundary is wrong —
  restructure instead.
- Providers are registered in their own module, never in `AppModule`.

## 5. Resolvers and services

**Resolvers are thin.** Args in, one service call, DTO out. No business logic,
no database access, no conditionals beyond mapping.

**Services hold everything else**, and take no GraphQL types as parameters, so
they stay testable without a GraphQL context.

Database access lives in the service. If a service grows past roughly 200 lines,
split it before it splits itself.

## 6. Enums

- **Enums are declared in the SDL**, in `src/schema/common.graphql`. That is the
  only place a value is written down.
- The generator emits real TypeScript enums into `graphql.generated.ts`.
  Import them from `libs/enums`, which is a re-export barrel plus the small
  helpers that need ordering (`riskAtLeast`).
- **Never hand-write a TypeScript `enum`** for anything that appears in the
  schema. A second declaration of the same values is exactly the drift
  schema-first exists to prevent (ADR 0004).
- Mongoose validates against them with `Object.values(Region)` — never a
  literal array copied by hand.
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

- `strict` is on and stays on.
- **Parse, do not cast.** Data from outside the system — KMA, the ML artifact,
  env config — goes through a Zod schema from `@pollen/contracts`. `as` on
  external data is banned.
- `any` requires a comment saying why it cannot be typed. `unknown` plus a
  narrowing check is almost always the answer instead.
- No non-null assertions (`!`) on anything that came from the network or the
  database.
- Generic parameters are `T`, `TData`, `TVars` — descriptive when there is more
  than one.

## 9. Naming inside code

| Thing | Case | Example |
| --- | --- | --- |
| Class, type, interface | `PascalCase` | `AlertsService` |
| Method, property, variable | `camelCase` | `recordDelivery` |
| Module-level constant | `SCREAMING_SNAKE` | `STALE_AFTER_MS` |
| Enum value | `SCREAMING_SNAKE` | `VERY_HIGH` |
| GraphQL field | `camelCase` | `riskLevel` |
| GraphQL type / enum | `PascalCase` | `RiskLevel` |
| Mongo collection | `snake_case` plural | `job_runs` |
| React component file | `PascalCase.tsx` | `PollenToday.tsx` |

Interfaces get no `I` prefix. Booleans read as assertions: `isStale`, `hasMore`.

## 10. The contract

Hand-written SDL in `apps/api/src/schema/*.graphql` is the frozen contract.

**A diff in any `.graphql` file is a contract change** and needs all three owners'
written agreement plus an ADR in `docs/adr/`. This is the Week-1 freeze.

TypeScript types are generated from SDL into `apps/api/src/graphql.generated.ts`,
which is committed. CI regenerates it and fails if it drifts — that is what
enforces the freeze, not memory.

After changing any `.graphql` file:

```bash
pnpm --filter @pollen/api schema:generate
```

## 11. Configuration

- No hardcoded regions, thresholds, URLs, dates, channel names, or secrets.
  Everything comes from env via `ConfigService`, or from `@pollen/contracts`.
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

- `*.spec.ts` under `apps/api/test/`, mirroring the source path.
- Test behaviour, not implementation. A test that breaks on a rename but not on
  a logic change is testing the wrong thing.
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
