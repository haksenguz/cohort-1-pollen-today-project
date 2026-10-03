# TASKS — who owns what

Updated: 2026-10-03. One person, one lane.

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
- The engine matches red flags by **alias**, not exact string. The model
  paraphrases (`throat_closing`, not `throat_swelling`), and an exact match
  scored those LOW. See "Safety bugs found by the eval" below. If you add a
  red flag, add its aliases to `RED_FLAG_ALIASES` in the same commit.

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
- 215 tests green

## The conversation vertical — `feat/ismoiljon`

- [x] **J2. Prove it against a real LLM.** Done. The full `symptom_agent`
      graph over the SSE endpoint, against real Postgres and a real key, in
      Korean: two turns, EMERGENCY, and the stream's verdict matches a direct
      `triage.assess` call on the same fields. Repeatable via
      `backend/scripts/verify_live_chat.py` (exit code gates a release check).
- [x] **J3. Prompt + extraction quality.** Done. Ten real phrasings across
      English, Korean and Uzbek in `backend/tests/test_eval_phrasings.py`.
      The live cases are opt-in (`RUN_LLM_EVAL=1`) because they spend real
      tokens; the scoring logic and the safety invariants run offline in the
      normal gate. All ten extract as annotated against the live model.
- [x] **J4. Failure behaviour.** Done. Every provider failure is normalized
      into `LLMCallError` with a `kind` (`timeout` / `rate_limit` /
      `unavailable` / `malformed`) at the single client boundary. The endpoint
      reports it as an SSE `error` event and never 500s. The `error` is
      emitted *after* `done`, and only when the rule engine did not reach a
      verdict, so a flaky provider can never swallow an EMERGENCY
      recommendation.
- [x] **J5. Chat screen.** Done in `1e33b0c` + `3cc5de3` (assistant-ui over
      the SSE contract, plus the blank-page fix).
- [x] **J6. Cost + latency guard.** Done. `max_tokens` (512) and a 20s
      per-call timeout are enforced on the client, overridable via
      `OPENAI_MAX_TOKENS` / `OPENAI_TIMEOUT_SECONDS`.
- [x] **J7. Collapse the duplicate client.** Done. `OpenAIChatClient` now
      exists once, in `backend/app/core/openai_client.py`. The agent defines a
      structural `LLMClient` Protocol and imports no concrete SDK, so its
      offline tests still run against a scripted fake.

## Safety bugs found by the eval (both fixed 2026-10-03)

Running the real model over the real phrasings (J3) found two defects that no
fake-model test could have, because both are about what the model *actually*
returns. Both are covered by regression tests now.

1. **Red-flag synonyms scored LOW.** The model answers "my throat feels like
   closing up" with `throat_closing`, not `throat_swelling`. The red-flag gate
   matched exact strings, so `throat_closing`, `chest_tight` and
   `anaphylactic_reaction` all scored **LOW** — the app told a user whose
   throat was closing that their symptoms looked mild. Fixed with a static
   alias table plus a negation guard (`no_breathing_difficulty` stays LOW) in
   `triage.py`. `RULE_VERSION` moved to `triage-2026-10-03`; the old version is
   no longer accurate for stored results.
2. **A confirmed red flag did not short-circuit intake.** `_route_after_extract`
   only triaged when symptoms *and* severity *and* both safety flags were
   present. The model correctly set both flags for "숨쉬기 힘들고 목이 부어서
   부풀었어요" but returned no severity, so the app replied "when did these
   symptoms start?" to a user who had just said they could not breathe. A
   confirmed `True` flag now routes straight to `triage_node` — the level is
   still produced only by the rule engine, so ADR 0001 is unchanged.

## Ismoiljon — `feat/ismoiljon`

- [x] **I1. Phase 4, triage persistence.** Done. `POST /api/triage` now needs
      a token, writes both rows, and returns their ids. Emergency verified
      against real Postgres.
- [x] **I2. Real pollen provider.** Code done, see
      `docs/research/pollen-providers.md`. KMA's index. **Still returns the
      flagged sample until a key exists — see I3.**
- [ ] **I3. API keys + live test.** Naver and OpenAI are live. The one
      remaining key is `POLLEN_API_KEY` from data.go.kr, and it is the only
      thing left that is not code.
      - [x] Naver: `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`. Live since
            2026-10-02; `/api/hospitals/nearby` returns real hospitals.
      - [ ] Pollen: `POLLEN_API_KEY`. Still empty. **The escape hatch is
            built**, so this no longer blocks a demo: when the key is absent
            the Today screen now shows a single `Pollen: Unavailable` row and
            an explanatory note, instead of rendering the flagged sample as
            "Tree pollen: High". The same applies when the provider is keyed
            but returns nothing (off season / outage) — all-null means "no
            data", not "low". Adding the key turns the real values back on
            with no code change.
      - [x] OpenAI: `OPENAI_API_KEY` via `OPENAI_BASE_URL` (OpenRouter) and
            `OPENAI_MODEL`. Verified end to end, see J2.
      `Touches`: `backend/.env` only (gitignored).
- [x] **I4. Phase 6, notifications.** Done. APScheduler, alert generation,
      preferences with quiet hours. Generates and stores only, sends nothing.
- [x] **I5. Frontend shell.** Done. Vite, React, TypeScript, PWA, auth screens,
      typed API client. Login verified end to end against the live backend.
- [x] **I6. Risk + hospital screens.** Done. `TodayPage` reads the user's
      saved lat/lon, calls `/api/environment/current` and
      `/api/hospitals/nearby` in parallel, and renders a risk chip, a metric
      list, and nearby hospitals. `AlertsPage` lists stored alerts with an
      "Unread only" filter and marks one read on click. Both degrade cleanly
      with no saved location, a failed environment call, or an unkeyed
      hospital provider. 62 tests.
- [x] **I7. Postgres in CI.** Done. `conftest.py` picks its engine from
      `TEST_DATABASE_URL`: sqlite by default, full Postgres in CI. Workflow
      spins up `postgres:17`.
- [x] **I8. Build the frontend in CI.** Done. `pnpm install --frozen-lockfile`,
      oxlint, `pnpm build` (`tsc -b && vite build`).

## Blocking the demo

Nothing in code. The single remaining item is `POLLEN_API_KEY` from
data.go.kr, and the app is honest about its absence rather than inventing
numbers, so a demo can go ahead without it.

## Verified working

Against real Postgres and live providers, 2026-10-03: register, login, the
full chat graph over SSE in Korean reaching EMERGENCY with a verdict matching
the rule engine, the ten-phrasing extraction eval across three languages, and
the Today screen rendering real air quality, weather and nearby hospitals with
pollen correctly withheld. Earlier, on 2026-09-09: allergy CRUD, environment
for Seoul, triage both mild and emergency with rows persisted, alerts and
preferences, and frontend login.

## Parking lot

- ML personalization (Phase 7)
- Rate limiting and abuse protection on the chat endpoint
- `WEATHER_API_KEY` is dead config, nothing reads it
