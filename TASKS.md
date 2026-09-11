# TASKS — who owns what

Updated: 2026-09-11. Two people, two lanes.

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

- [x] **I1. Phase 4, triage persistence.** Done. `POST /api/triage` now needs
      a token, writes both rows, and returns their ids. Emergency verified
      against real Postgres.
- [x] **I2. Real pollen provider.** Code done, see
      `docs/research/pollen-providers.md`. KMA's index. **Still returns the
      flagged sample until a key exists — see I3.**
- [ ] **I3. API keys + live test.** Nothing here is code. Get the keys, put
      them in `backend/.env`, confirm real data comes back.
      - [ ] Naver: `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`. Without them
            `/api/hospitals/nearby` answers `provider_available: false`.
      - [ ] Pollen: `POLLEN_API_KEY` from data.go.kr. Without it pollen is a
            flagged sample, which is the one thing a reviewer will notice.
      - [ ] OpenAI: `OPENAI_API_KEY`. Without it chat asks its safety question
            but extracts nothing, so it never reaches a verdict. Jack needs
            this for J2.
      `Touches`: `.env` only.
- [x] **I4. Phase 6, notifications.** Done. APScheduler, alert generation,
      preferences with quiet hours. Generates and stores only, sends nothing.
- [x] **I5. Frontend shell.** Done. Vite, React, TypeScript, PWA, auth screens,
      typed API client. Login verified end to end against the live backend.
- [ ] **I6. Risk + hospital screens.** The Today and Alerts tabs are
      placeholders today. The shell and the typed client are ready.
      `Touches`: `frontend/src/` except `frontend/src/chat/`.
- [x] **I7. Postgres in CI.** Done. `conftest.py` picks its engine from
      `TEST_DATABASE_URL`: sqlite by default (fast, no infra), full Postgres
      in CI (catches dialect bugs like the TIMESTAMPTZ one). Workflow now
      spins up `postgres:17` and points the test job at it. Locally verified
      135/135 on both backends.
- [ ] **I8. Build the frontend in CI.** Nothing checks it today.
      `Touches`: `.github/workflows/ci.yml`.

## Blocking the demo

Three keys, none of them code: pollen, Naver, OpenAI. That is **I3**. Until the
pollen key exists the app reports invented pollen numbers, which is the first
thing a reviewer will ask about.

## Verified working

Run against real Postgres and live providers on 2026-09-09: register, login,
allergy CRUD, environment for Seoul with real weather and air quality, triage
both mild and emergency with rows persisted, chat streaming and stored, alerts
and preferences, and frontend login.

## Parking lot

- ML personalization (Phase 7)
- Rate limiting and abuse protection on the chat endpoint
- `WEATHER_API_KEY` is dead config, nothing reads it
