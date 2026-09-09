# TASKS — who owns what

Updated: 2026-09-09. Two people, two lanes.

- **Ismoiljon** (tech lead) works on `feat/ismoiljon`.
- **Jack** (AI engineer) works on `feat/jack`.
- Both merge into `main` when a lane is ready. `main` must stay green.

The API contract between the lanes is [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md).
Change it only by agreement, because the other lane builds against it.

## The boundary

Jack owns the conversation vertical end to end: the agent graph, the chat
endpoint, and the chat screen. Ismoiljon owns everything else.

The line is the one already written in
[ADR 0001](docs/adr/0001-llm-does-not-decide-safety.md): the LLM does
conversation and extraction, the deterministic engine decides safety.

- Jack never edits `backend/app/services/triage.py` or `risk.py`.
- Ismoiljon never edits `backend/app/agents/`.

Two files collide no matter how we split. **Ismoiljon owns
`backend/app/main.py` and `backend/pyproject.toml`.** Jack asks for additions
instead of editing them.

## Already done (on `main`, do not rebuild)

Read this before planning anything. Most of the backend exists.

- ERD, generator, `backend/db/init/01_schema.sql`, async Alembic migrations
- Deterministic risk scoring and rule-based triage
- Auth: register, login, JWT, allergy CRUD
- Environment: weather + air quality live on Open-Meteo, graceful degradation
- Hospitals: Naver Local Search, distance ranking
- Symptom agent: LangGraph graph, SSE chat endpoint, conversation persistence
- 82 tests green

## Jack — `feat/jack`

- [ ] **J1. Review the merged agent.** Read `backend/app/agents/symptom_agent.py`
      and `api/chat.py`. You own them now. `Touches`: nothing, this is reading.
- [ ] **J2. Prove it against a real LLM.** Everything so far is tested with a
      scripted fake. Run it with a real key, fix what breaks.
      `Touches`: `backend/app/agents/symptom_agent.py`.
- [ ] **J3. Prompt + extraction quality.** Symptom, severity, duration, trigger.
      Build a small eval set of real phrasings, including Uzbek and Korean input.
      `Touches`: `backend/app/agents/`, `backend/tests/test_symptom_agent.py`.
- [ ] **J4. Failure behaviour.** Timeout, rate limit, malformed JSON, empty
      reply. The endpoint must degrade, never 500.
      `Touches`: `backend/app/agents/`, `backend/app/api/chat.py`.
- [ ] **J5. Chat screen.** The frontend chat UI against the SSE contract.
      `Touches`: `frontend/src/chat/`.
- [ ] **J6. Cost + latency guard.** Token caps, model choice, a timeout budget.
      `Touches`: `backend/app/agents/`.

## Ismoiljon — `feat/ismoiljon`

- [ ] **I1. Phase 4, triage persistence.** Persist `symptom_events` and
      `triage_results`, emergency short-circuit end to end.
      `Touches`: `backend/app/api/triage.py`, `services/triage.py`, `models`.
- [ ] **I2. Real pollen provider.** Currently a flagged sample, not real data.
      Pick a provider that covers Korea, note rate limits, then implement.
      `Touches`: `docs/research/`, `backend/app/services/pollen_service.py`.
- [ ] **I3. Naver credentials + live test.** Code is done, keys are not wired.
      `Touches`: `.env`, `backend/app/services/hospital_service.py`.
- [ ] **I4. Phase 6, notifications.** Scheduled environment checks, alerts,
      user preferences. `Touches`:
      `backend/app/services/notification_service.py`, scheduler.
- [ ] **I5. Frontend shell.** Vite + React + PWA scaffold, routing, auth screens,
      API client. Jack builds the chat screen inside this shell.
      `Touches`: `frontend/` except `frontend/src/chat/`.
- [ ] **I6. Risk + hospital screens.** `Touches`: `frontend/src/`.

## Blocking the demo

Pollen readings are invented. Everything else can ship around it; this one is
the first thing a reviewer will ask about. That is **I2**.

## Parking lot

- ML personalization (Phase 7)
- Rate limiting and abuse protection on the chat endpoint
- Real Postgres in CI — tests currently run on in-memory SQLite
