# TASKS — who owns what

Updated: 2026-10-02. One person, one lane.

- **Ismoiljon** (tech lead) owns `feat/ismoiljon` and the whole repo. The
  two-lane split with Jack ended 2026-10-02: `origin/feat/jack` never got
  past docs, so Ismoiljon took the conversation vertical too.
- `main` must stay green. Merge a lane when it is ready.

The API contract is [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md).

## The boundary

The line that still matters is not a people split, it is the safety split
already written in
[ADR 0001](docs/adr/0001-llm-does-not-decide-safety.md): the LLM does
conversation and extraction, the deterministic engine decides safety.

- `backend/app/services/triage.py` and `risk.py` stay a rule engine. Never
  move a safety decision into a prompt, no matter who edits the agents.

Ismoiljon now owns everything, including `backend/app/agents/` and
`backend/app/main.py`. The old per-person restrictions are gone.

## Already done (on `main`, do not rebuild)

Read this before planning anything. Most of the backend exists.

- ERD, generator, `backend/db/init/01_schema.sql`, async Alembic migrations
- Deterministic risk scoring and rule-based triage
- Auth: register, login, JWT, allergy CRUD
- Environment: weather + air quality live on Open-Meteo, graceful degradation
- Hospitals: Naver Local Search, distance ranking
- Symptom agent: LangGraph graph, SSE chat endpoint, conversation persistence
- 82 tests green

## The conversation vertical — `feat/ismoiljon`

Jack never started these. They are the critical path to release, so they
moved to Ismoiljon's list on 2026-10-02.

- [ ] **J2. Prove it against a real LLM.** The client factory is now verified
      against a real provider: `app/core/openai_client.py` through OpenRouter,
      Korean input, JSON out (commit `5a420f2`). Still open: the full
      `symptom_agent` graph over the SSE endpoint with the real key.
      `Touches`: `backend/app/agents/symptom_agent.py`.
- [ ] **J3. Prompt + extraction quality.** Symptom, severity, duration, trigger.
      Build a small eval set of real phrasings, including Uzbek and Korean input.
      `Touches`: `backend/app/agents/`, `backend/tests/test_symptom_agent.py`.
- [ ] **J4. Failure behaviour.** Timeout, rate limit, malformed JSON, empty
      reply. The endpoint must degrade, never 500.
      `Touches`: `backend/app/agents/`, `backend/app/api/chat.py`.
- [ ] **J5. Chat screen.** The frontend chat UI against the SSE contract. This
      is the only surface a reviewer can hold, and it does not exist yet.
      `Touches`: `frontend/src/chat/`.
- [ ] **J6. Cost + latency guard.** Token caps, model choice, a timeout budget.
      `Touches`: `backend/app/agents/`.
- [ ] **J7. Collapse the duplicate client.** `OpenAIChatClient` exists in both
      `app/core/openai_client.py` and `app/agents/symptom_agent.py`. Merge them
      so there is one boundary with the model.
      `Touches`: `backend/app/agents/`, `backend/app/core/openai_client.py`.

## Ismoiljon — `feat/ismoiljon`

- [x] **I1. Phase 4, triage persistence.** Done. `POST /api/triage` now needs
      a token, writes both rows, and returns their ids. Emergency verified
      against real Postgres.
- [x] **I2. Real pollen provider.** Code done, see
      `docs/research/pollen-providers.md`. KMA's index. **Still returns the
      flagged sample until a key exists — see I3.**
- [ ] **I3. API keys + live test.** Code side is done: every provider
      already degrades gracefully when its key is blank (pollen falls
      back to the flagged sample, hospitals answer
      `provider_available: false`, chat returns a stream error), and
      `backend/.env.example` documents where to get each key. The
      remaining work is non-code: get the keys, put them in
      `backend/.env`, confirm real data comes back.
      - [x] Naver: `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`. Both live as of
            2026-10-02, so `/api/hospitals/nearby` returns real hospitals.
      - [ ] Pollen: `POLLEN_API_KEY` from data.go.kr. Still empty. Without it
            pollen is a flagged sample, which is the one thing a reviewer will
            notice. This is the only remaining key and it is the P0.
      - [x] OpenAI: `OPENAI_API_KEY` live as of 2026-10-02, pointed at an
            OpenRouter base URL via `OPENAI_BASE_URL` and `OPENAI_MODEL`.
            Verified end to end, see J2.
      `Touches`: `backend/.env` only (gitignored).
- [x] **I4. Phase 6, notifications.** Done. APScheduler, alert generation,
      preferences with quiet hours. Generates and stores only, sends nothing.
- [x] **I5. Frontend shell.** Done. Vite, React, TypeScript, PWA, auth screens,
      typed API client. Login verified end to end against the live backend.
- [x] **I6. Risk + hospital screens.** Done. `TodayPage` now reads the
      user's saved lat/lon, calls `/api/environment/current` and
      `/api/hospitals/nearby` in parallel, and renders a risk chip, a
      metric list (pollen, PM2.5/PM10, temperature, humidity, wind), and
      a list of nearby hospitals with name, address, specialty, phone,
      distance. `AlertsPage` lists stored alerts, supports an "Unread
      only" filter, and marks an alert read on click. Both pages
      degrade cleanly when the user has no saved location, when the
      environment endpoint fails, or when the hospital provider is
      unkeyed. Vitest + Testing Library added; 35 tests cover the API
      client, formatters, and both screens.
- [x] **I7. Postgres in CI.** Done. `conftest.py` picks its engine from
      `TEST_DATABASE_URL`: sqlite by default (fast, no infra), full Postgres
      in CI (catches dialect bugs like the TIMESTAMPTZ one). Workflow now
      spins up `postgres:17` and points the test job at it. Locally verified
      135/135 on both backends.
- [x] **I8. Build the frontend in CI.** Done. New `frontend` job on the
      same workflow: pnpm install (frozen lockfile), oxlint, `pnpm build`
      (`tsc -b && vite build`). A broken import or type error now blocks
      a PR instead of waiting for a local reviewer.

## Blocking the demo

One key, and it is not code: `POLLEN_API_KEY` from data.go.kr. Naver and
OpenAI are live. Until the pollen key exists the app reports invented pollen
numbers, which is the first thing a reviewer will ask about. The escape hatch
if the key does not land in time: make the fallback state explicit in the UI
so the app says "pollen unavailable" rather than showing a sample that reads
like a real reading.

## Verified working

Run against real Postgres and live providers on 2026-09-09: register, login,
allergy CRUD, environment for Seoul with real weather and air quality, triage
both mild and emergency with rows persisted, chat streaming and stored, alerts
and preferences, and frontend login.

## Parking lot

- ML personalization (Phase 7)
- Rate limiting and abuse protection on the chat endpoint
- `WEATHER_API_KEY` is dead config, nothing reads it
