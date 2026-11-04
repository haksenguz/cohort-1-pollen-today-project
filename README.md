# Allergy AI Companion 🌿🤖

AI-powered web app that monitors environmental allergy risk, runs a structured
AI symptom conversation, applies **rule-based safety triage**, and finds nearby
healthcare facilities.

> Information and healthcare-navigation tool. Not a medical diagnosis and not a
> replacement for professional care.

Full product spec: [`docs/pollen_documentation.md`](docs/pollen_documentation.md).

## Architecture

```
Phone browser  ──HTTPS──▶  edge (Caddy)  ──▶  web (nginx + PWA)
                                                    │
                                          /api/*    ▼
                                               api (FastAPI)
                                                    │
                                      ┌─────────────┼─────────────┐
                                Environmental    LangGraph      Hospital
                                   service       AI agents       service
                                                    │
                                                 Postgres / Redis
```

The frontend is a phone-first **PWA** built with Vite, React and Tailwind v4
(ADR 0002, ADR 0003). It ships as static files behind nginx, which proxies
`/api` to the backend, so the browser talks to one origin.

The core design rule: the **LLM does conversation + extraction only**; a
**deterministic rule engine** owns every safety decision
([`backend/app/services/triage.py`](backend/app/services/triage.py)).

## Database

- ERD (open in **Luna Modeler**): [`docs/erd/allergy_ai.dmm`](docs/erd/allergy_ai.dmm)
- Viewable diagram + notes: [`docs/erd/ERD.md`](docs/erd/ERD.md)
- DDL: [`backend/db/init/01_schema.sql`](backend/db/init/01_schema.sql) (also
  runs on first `docker compose up` via `backend/db/init/`)
- Regenerate both from one spec: `python docs/erd/gen_dmm.py`
- Migrations: Alembic, applied on every API container boot

## Run

The whole stack, in the shape it takes in production:

```bash
cp .env.example .env         # fill in the values it asks for
docker compose up -d --build
```

The site comes up on `http://localhost`. A real deployment uses
`https://your-domain` and Caddy obtains the certificate on its own.

Backend on its own, for development:

```bash
cd backend
uv run fastapi dev app/main.py   # API on :8000, OpenAPI at /docs
uv run pytest                    # safety-critical: triage + risk
```

Frontend on its own:

```bash
cd frontend
pnpm install
pnpm dev                        # Vite on :5173
```

Deploying to a host, upgrading it, backups and the failure modes are all in
[`docs/DEPLOY.md`](docs/DEPLOY.md).

## Layout

```
backend/    FastAPI + SQLModel + rule engines + agents, plus db/init DDL
frontend/   phone-first PWA, Vite + React + Tailwind v4 (ADR 0002, ADR 0003)
deploy/     Caddyfile for the TLS edge
docs/       spec, ERD (.dmm, generator), ADRs, research/, headache/, governance
```

## Roadmap

Phases 1–7 in `docs/pollen_documentation.md` §21. Shipped: ERD and migrations,
auth, deterministic risk scoring, rule-based triage, the LangGraph symptom
agent over SSE, the real pollen, air quality, weather and hospital providers,
the agent tool loop, chat history, privacy export and deletion, consent
records, and the deployment stack.

Open work is tracked in [`TASKS.md`](TASKS.md) and [`bugs.md`](bugs.md). The
biggest gap between the code and a finished product is that alert delivery
does not exist yet: the pipeline generates and stores alerts and sends
nothing.
