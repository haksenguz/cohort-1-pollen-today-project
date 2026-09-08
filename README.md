# Allergy AI Companion 🌿🤖

AI-powered web app that monitors environmental allergy risk, runs a structured
AI symptom conversation, applies **rule-based safety triage**, and finds nearby
healthcare facilities.

> Information and healthcare-navigation tool. Not a medical diagnosis and not a
> replacement for professional care.

Full product spec: [`docs/pollen_documentation.md`](docs/pollen_documentation.md).

## Architecture

```
Mobile PWA (frontend)  ──HTTPS──▶  FastAPI (backend)  ──▶  Postgres / Redis
                                        │
                          ┌─────────────┼─────────────┐
                    Environmental    LangGraph      Hospital
                       service       AI agents       service
```

Frontend is a phone-first **PWA**, designed separately (Ismoiljon). This repo is
the backend + data model; the API is the contract the PWA consumes.

The core design rule: the **LLM does conversation + extraction only**; a
**deterministic rule engine** owns every safety decision
([`backend/app/services/triage.py`](backend/app/services/triage.py)).

## Database

- ERD (open in **Luna Modeler**): [`docs/erd/allergy_ai.dmm`](docs/erd/allergy_ai.dmm)
- Viewable diagram + notes: [`docs/erd/ERD.md`](docs/erd/ERD.md)
- DDL: [`backend/db/init/01_schema.sql`](backend/db/init/01_schema.sql) (also
  runs on first `docker compose up` via `backend/db/init/`)
- Regenerate both from one spec: `python docs/erd/gen_dmm.py`

## Run

```bash
cp .env.example .env         # fill in API keys
docker compose up            # postgres + redis + api on :8000
```

API docs at http://localhost:8000/docs.

Frontend (mobile PWA) is designed and built separately; it talks to this API.

## Backend dev

```bash
cd backend
uv run fastapi dev app/main.py
uv run pytest                 # safety-critical: triage + risk
```

## Layout

```
backend/    FastAPI + SQLModel + rule engines + agents, plus db/init DDL
frontend/   phone-first PWA — HTML prototype now, Vite + React later (ADR 0002)
docs/       spec, ERD (.dmm, generator), ADRs, research/, headache/, governance
```

## Roadmap

Phases 1–7 in `docs/pollen_documentation.md` §21. Done so far: ERD, backend
scaffold, deterministic risk scoring, rule-based triage, environment endpoint.
Next: real pollen/AQI/weather providers, auth, LangGraph symptom agent, hospital
finder.
