# Pollen Today

Korea pollen forecast and morning alerts. KMA publishes a daily pollen risk
index; this tells people the day before, when medication still has time to work.

HaksengUz Cohort 1 · 6-week team build · Aug–Sep 2026

## Team and slices

| Slice | Owner | Also |
| --- | --- | --- |
| A — Forecast Engine | Jamshid Ganiev | Contract Owner |
| B — Season Analytics | Egamov Giyos | Release Owner |
| C — Alerts & Delivery | Ismoiljon Masharipov | Repo Owner, Tech Lead |

Each slice runs data → API → UI end to end. Nobody waits on anybody.

## Stack

- **Python 3.12 + FastAPI** — the API. See
  [ADR 0006](docs/adr/0006-python-fastapi-api.md).
- **Ariadne** — schema-first GraphQL. The hand-written SDL in
  `apps/api/schema/*.graphql` is the frozen contract and is loaded directly.
- **MongoDB + Beanie** — persistence. Documents live in `schemas/`, separate
  from the DTOs the API exposes.
- **APScheduler** — the 07:00 KST alert job.
- **React + Vite** — the web app, in TypeScript.
- **`@pollen/contracts`** — generates the web app's TypeScript types from the
  same SDL with graphql-codegen. CI fails if they drift.

Model training lives in `ml/` and runs on a laptop, never in production
([ADR 0002](docs/adr/0002-model-runs-as-an-offline-artifact.md)).

## Setup

```bash
cp .env.example .env
```

Start MongoDB however you like — Docker, a local install, or Atlas — and point
`MONGODB_URI` at it.

API:

```bash
cd apps/api && uv venv && uv pip install -e ".[dev]"
```

```bash
cd apps/api && uv run uvicorn pollen.main:app --reload --port 8000
```

Web:

```bash
pnpm install && pnpm --filter @pollen/web dev
```

GraphQL at `http://localhost:8000/graphql`, health at `/api/health`, and `/`
serves a status page. Web on `:5173` with `/graphql` proxied.

> If `uv` fails with `invalid peer certificate: UnknownIssuer`, add
> `--native-tls` — there is a corporate certificate in the chain on some
> networks.

## Verify like CI does

```bash
cd apps/api && uv run ruff check . && uv run ruff format --check . && uv run pytest
```

```bash
pnpm build && pnpm typecheck && pnpm lint && pnpm format:check
```

Integration tests need a real MongoDB at `MONGODB_TEST_URI`; they skip cleanly
without one. They are not mocked on purpose — the idempotency guarantee is that
the *database* refuses a duplicate, and a mock that accepts two identical
inserts would pass while proving nothing.

## Running a job by hand

```bash
cd apps/api && uv run pollen-job daily-alert
```

Goes through the same `JobRunner` the scheduler uses, so a manual run is
recorded identically. Run it twice — the second run posts nothing. That is
Milestone 2's idempotency criterion, demonstrated rather than asserted.

## Layout

```
apps/api/schema/*.graphql     hand-written SDL — the contract
apps/api/src/pollen/
  main.py                     app factory, lifespan, scheduler
  container.py                wiring
  graphql_app.py              schema assembly + error formatter
  components/registry.py      aggregates every component
  components/<feature>/       resolver.py · service.py · dto.py · schemas/
  libs/                       enums, errors, KST dates
apps/api/tests/               pytest
apps/web/                     React + Vite
packages/contracts/           TypeScript types generated from the SDL, for web
ml/                           offline training, not deployed
```

Adding a component means one entry in `components/registry.py` — `main.py` is
not touched, which keeps the file three people are most likely to conflict on
stable.

## Working agreement

- Branch per person: `feat/ismoiljon`, `feat/jamshid`, `feat/giyos`
- Nothing merges to `main` without a review and green CI
- Every PR reviewed within 24 hours
- A diff in any `.graphql` file is a contract change: all three owners agree in
  writing, plus an ADR
- See [docs/CONVENTIONS.md](docs/CONVENTIONS.md) and
  [docs/DEFINITION_OF_DONE.md](docs/DEFINITION_OF_DONE.md)

## Status

Week 0–1. Slice C runs end to end: the scheduler triggers the job, the job reads
a forecast, claims the delivery in MongoDB and posts to Telegram (dry-run
without a bot token). Forecast and analytics are stubs owned by their slices.

**Known blocker.** The KMA API serves **one day** of data —
`최근 1일 간의 자료만 제공합니다`. Slice A's "5+ years of history" and Slice B's
multi-year analysis have no source from this endpoint, and every day without
ingest is data permanently lost. Tracked in
[OPEN_QUESTIONS.md](OPEN_QUESTIONS.md).

## Privacy

No accounts, no email, no phone numbers, no subscriber table. Delivery is to
public Telegram channels, so there are no personal identifiers to store. This is
a design decision, not a to-do.
