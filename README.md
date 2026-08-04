# Pollen Today

Korea pollen forecast and morning alerts. KMA publishes a daily pollen risk index;
this tells people the day before, when medication still has time to work.

HaksengUz Cohort 1 · 6-week team build · Aug–Sep 2026

## Team and slices

| Slice | Owner | Also |
| --- | --- | --- |
| A — Forecast Engine | Jamshid Ganiev | Contract Owner |
| B — Season Analytics | Egamov Giyos | Release Owner |
| C — Alerts & Delivery | Ismoiljon Masharipov | Repo Owner, Tech Lead |

Each slice runs data → API → UI end to end. Nobody waits on anybody.

## Stack

- **pnpm workspaces** — one repo, three packages
- **NestJS + GraphQL (schema-first, Apollo)** — one module per slice. Hand-written
  SDL in `apps/api/src/schema/` is the frozen contract; TypeScript types are
  generated from it. CI fails if generated types drift from what is committed.
- **MongoDB + Mongoose** (`@nestjs/mongoose`). Persistence models in `schemas/`
  stay separate from GraphQL models in `models/`.
- **`@pollen/contracts`** — shared enums, plus Zod schemas for *untrusted*
  boundaries only: KMA responses, the ML artifact, env config. See
  [ADR 0004](docs/adr/0004-graphql-code-first-and-where-zod-lives.md).
- **React + Vite** — web
- **`@nestjs/schedule`** — the 07:00 KST alert job

Model training lives in `ml/` and runs on a laptop, never in production. It
exports a versioned JSON artifact that the API loads. No Python is deployed.

## Setup

```bash
pnpm install
```

```bash
cp .env.example .env
```

```bash
docker compose up -d mongo
```

```bash
pnpm dev
```

API on `:8000` (GraphQL at `/graphql`, health at `/api/health`), web on `:5173`
with `/graphql` proxied.

After changing any `.graphql` file, regenerate and commit the types:

```bash
pnpm --filter @pollen/api schema:generate
```

## Verify like CI does

```bash
pnpm build && pnpm typecheck && pnpm lint && pnpm format:check && pnpm test
```

## Layout

```
packages/contracts/            shared enums + Zod for external boundaries
apps/api/src/schema/           hand-written GraphQL SDL — the frozen contract
apps/api/src/graphql.generated.ts  generated types from SDL, committed + CI diff-checked
apps/api/src/app.module.ts     infrastructure only
apps/api/src/components/       every feature module, aggregated by
  components.module.ts           ComponentsModule — AppModule imports only this
  forecast/                    slice A · analytics/ slice B · alerts/ slice C
    dto/<name>.dto.ts            re-exports the generated GraphQL type
    dto/<name>Input.dto.ts       input args from SDL
    dto/<name>Update.dto.ts      update input — added when mutations are
    schemas/                     Mongoose persistence, kept separate from dto
    *.resolver.ts                thin — args in, service call, dto out
    *.service.ts                 all logic, testable without GraphQL
apps/api/src/libs/             errors, ObjectId scalar, generic types, KST dates
apps/web/                      React + Vite
ml/                            offline training, not deployed
```

Adding a component means one line in `components.module.ts` — `app.module.ts`
is not touched, which keeps the file three people are most likely to conflict on
stable.

## Working agreement

- Branch per person: `feat/ismoiljon`, `feat/jamshid`, `feat/giyos`
- Nothing merges to `main` without a review and green CI
- Every PR reviewed within 24 hours
- Contract changes need all three owners to agree in writing — see `docs/adr/`
- See [docs/DEFINITION_OF_DONE.md](docs/DEFINITION_OF_DONE.md)

## Status

Week 0. Walking skeleton only — the forecast and analytics endpoints are stubs
owned by their slice owners, and the Telegram send path is not built yet.

Blocked items are tracked in [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md); the process
gaps we are asking the mentor to close are in [PROCESS.md](PROCESS.md).

## Privacy

No accounts, no email, no phone numbers, no subscriber table. Delivery is to
public Telegram channels, so there are no personal identifiers to store. This is
a design decision, not a to-do.
