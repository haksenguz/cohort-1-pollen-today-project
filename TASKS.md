# TASKS — what we're doing right now

Updated: 2026-09-08. Owner decides priority: Ismoiljon (Tech Lead).

Each task names a `Touches` boundary. Two tasks whose `Touches` overlap don't run
in parallel. Phases map to the roadmap in `docs/pollen_documentation.md` §21.

## Done

- [x] Reset repo to Allergy AI Companion, archive spec → `docs/pollen_documentation.md`
- [x] ERD in Luna Modeler (`docs/erd/allergy_ai.dmm`) + `schema.sql` + generator
- [x] Backend scaffold: FastAPI + SQLModel, config, db, models (10 tables)
- [x] Deterministic risk scoring (§14) + rule-based triage (§4), 10 tests green
- [x] `/health`, `/api/environment/current`, `/api/triage` endpoints
- [x] docker-compose (postgres auto-loads schema, redis, api)
- [x] Phone-first chat prototype (`frontend/prototype.html`)
- [x] Governance: AGENTS.md, GOVERNANCE, DEFINITION_OF_DONE, ADR 0001/0002, CI

## In progress

- [ ] Nothing claimed. Pick from Next.

## Next — backend, follows the spec (no FE, that's a separate track)

- [ ] **Phase 1 — real environmental providers.** Replace the stub in
      `api/environment.py` with pollen + AQI + weather clients.
      `Touches`: `backend/app/services/{pollen,air_quality,weather}_service.py`,
      `api/environment.py`. Depends on: API keys in `.env`.
- [ ] **Phase 2 — auth + allergy profile.** Register/login (JWT), user CRUD,
      allergy CRUD, personalize risk with `user_allergies`.
      `Touches`: `backend/app/api/{auth,users,allergies}.py`, `core/security.py`.
- [ ] **Phase 3 — LangGraph symptom agent.** Conversation state, symptom +
      severity extraction, safety questions, structured output feeding the rule
      engine. `Touches`: `backend/app/agents/symptom_agent.py`, `api/chat.py`.
- [ ] **Phase 4 — triage flow wiring.** Persist `symptom_events` +
      `triage_results`, emergency short-circuit end to end.
      `Touches`: `backend/app/api/triage.py`, `models`, `services/triage.py`.
- [ ] **Phase 5 — hospital finder.** Places API client, specialty filter,
      distance rank, opening status. `Touches`:
      `backend/app/services/hospital_service.py`, `api/hospitals.py`.
- [ ] **Phase 6 — notifications.** Scheduled env checks, alert generation,
      user preferences. `Touches`: `backend/app/services/notification_service.py`,
      scheduler.
- [ ] **Migrations.** Add Alembic before the schema moves again.
      `Touches`: `backend/alembic/`.

## Parking lot

- Frontend PWA build (Vite) — waits on the design. Tracked in ADR 0002.
- ML personalization (Phase 7).
