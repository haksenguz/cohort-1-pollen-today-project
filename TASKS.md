# TASKS — who owns what

Updated: 2026-10-28. One person, one lane.

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
      normal gate. Re-verified 2026-10-15: all ten pass, and every safety
      invariant holds — a red flag stated by the user is surfaced on the
      first turn in every language.
      **Not deterministic, though.** The provider is sampled, so two cases
      drift between runs: an English case sometimes reports severity 7 where
      3–6 is expected, and the Uzbek "boshim og'riyapti" case occasionally
      omits `headache`. A run is green end to end; do not read a single
      deviation as a regression, and re-run before investigating one.
      Two annotations were corrected in the same pass, both of which had
      been asserting the wrong thing rather than catching a defect:
      `airway_swelling` is a boolean safety flag in the extraction schema,
      not a symptom name, and the Uzbek "yug'uraman" means the eyes
      watering, not sneezing.
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
      `docs/research/pollen-providers.md`. KMA's index. **Live and verified —
      see I3.**
- [x] **I3. API keys + live test.** Done. All three keys are in place and every
      one has been exercised against its real provider.
      - [x] Naver: `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`. Live since
            2026-10-02; `/api/hospitals/nearby` returns real hospitals.
      - [x] Pollen: `POLLEN_API_KEY`. Live and verified 2026-10-15 with
            `backend/scripts/verify_live_pollen.py` (exit code gates the
            release check the same way `verify_live_chat.py` does).
            Getting there meant fixing the integration: the endpoint the code
            called, `HealthWeatherIdxServiceV3/getPlrsIdxTodyList`, does not
            exist, and data.go.kr answers HTTP 400
            `NO_OPENAPI_SERVICE_ERROR` (code 12, "check the call URL for a
            typo") — which reads like an auth failure. The real service is
            `HealthWthrIdxServiceV3`, split into `getOakPollenRiskIdxV3`,
            `getPinePollenRiskIdxV3` and `getWeedsPollenRiskndxV3`, taking a
            10-digit station code and a `time` announcement stamp rather than
            an `areaNo`/`date` pair. Full contract, including the two
            ways it returns "nothing" (out-of-season `resultCode 99`, and a
            blank `today`), is in `docs/research/pollen-providers.md`.
            Seoul on 2026-10-15 reads `weed=LOW`, tree withheld as correct for
            October.
            **Known limit:** KMA publishes no station for Gwangju, Gangwon,
            Jeonbuk and Jeonnam. Those provinces show "no data" rather than a
            neighbour's reading. Closing it needs KMA's named station list, not
            another key.
      - [x] OpenAI: `OPENAI_API_KEY` via `OPENAI_BASE_URL` and `OPENAI_MODEL`.
            Verified end to end, see J2. The key is a MiniMax key, so the base
            URL must be the MiniMax endpoint — see B-007 for what happens when
            a key is paired with the wrong host.
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
- [x] **I9. Abuse protection on the chat endpoint.** Done. Every turn of the
      symptom conversation is a real model call, so an unbounded endpoint is a
      direct billing risk and authentication alone does not bound a signed-up
      client. `POST /api/chat` now enforces a per-user sliding window
      (default 20/min, `CHAT_RATE_LIMIT_PER_MINUTE`, 0 disables). The refusal is
      a real `429` with `Retry-After`, raised *before* the SSE stream opens —
      inside the generator the 200 would already be sent and the refusal
      unreachable. Standard `X-RateLimit-*` headers ride along on both
      outcomes. No new table and no schema change: state is a per-process
      in-memory deque, so the ERD and generated SQL are untouched. The
      concurrency case is tested — without the lock, ten simultaneous requests
      each read "one slot left" and all ten get in.
- [x] **I10. Dead config removed.** `WEATHER_API_KEY` / `weather_api_key` is
      gone from `Settings` and `.env.example`. Open-Meteo is keyless, so
      nothing ever read it; leaving it in the config invited someone to go
      looking for a key that does nothing. The spec's own env-var list (§20) is
      left as written, since that is the historical document it is.

## R1. Deployment readiness

- [x] **R1. The stack starts with a real configuration.** The Compose file
      requires `JWT_SECRET`, `POSTGRES_*` and `PUBLIC_ORIGIN`, and
      `.env.example` is the template that supplies all of them. A test parses
      the Compose file for every `${VAR:?...}` and fails when the template
      misses one, so the two cannot drift apart again. `CORS_ORIGINS` is
      optional: the API adds `PUBLIC_ORIGIN` to the allowlist by itself, so a
      wrong value cannot break a working deployment.
- [x] **R2. An unsafe configuration stops the boot.** `ENVIRONMENT=production`
      makes the API refuse to start on a weak or example signing secret, with
      the dev credential route on, or with demo mode on. The check runs before
      the database is touched.
- [x] **R3. TLS in front of the app.** `deploy/Caddyfile` terminates TLS and
      forwards to nginx, which still serves the PWA and proxies `/api`. A PWA
      service worker only registers on a secure origin, so without this the
      install prompt never fires outside `localhost`.
- [x] **R4. The build context is the repo, not the developer's machine.**
      `.dockerignore` for both images keeps `node_modules`, `.venv` and the
      local `.env` out of the image.
- [x] **R5. A runbook.** `docs/DEPLOY.md`: first deploy, verification against
      the live instance, upgrades, backups, restore, rollback, secret
      rotation, troubleshooting, and the limits that are still true (one
      instance, one database volume, no alert delivery).
- [ ] **R6. The live deploy.** Needs a host and a domain, which are not
      things the repository can supply. The stack, the template and the
      runbook are ready for both.

## S1. Product gaps closed before the handoff

Worked in parallel by three workers on 2026-10-28, then integrated and
re-gated. The bugs.md entries are the record of each one.

- [x] **S1. The chat is a chat, not a transcript.** Real token streaming from
      the provider (C1), markdown rendering (C2), regenerate (C3), copy (C4),
      timestamps (C5), jump-to-latest (C7) and an offline state that refuses
      the send instead of faking it (C10). The frontend worker also shipped
      the history search field that C7's sibling B7 needed.
- [x] **S2. The history list is usable.** Conversations are named from the
      user's first message (B5), `updated_at` is written on every turn
      (B-015a), and `GET /api/conversations?q=` searches the title and the
      messages (B7).
- [x] **S3. 민감정보 is consented to, not just described.** The gate refuses
      the 민감정보 write paths with a 403 the frontend can act on, the chat
      asks too, and the consent screen stands in front of the app (B-020d).
      Reads, export and delete stay open so 제35조 and 제36조 survive a
      withdrawal.
- [x] **S4. The privacy rights are real.** The settings rows that said the
      server had no delete endpoint now open a screen that exports a file and
      deletes the account behind a two-step confirmation.
- [x] **S5. The operator can be named.** `OPERATOR_NAME` and
      `OPERATOR_REGISTRATION_NUMBER` reach the policy, and the emergency
      contact has a screen (E8).
- [x] **S6. The interface stopped making claims the backend does not back.**
      The audit of the demo path is recorded as B-022: a sampled pollen level
      no longer scores, a day with no measurement no longer reads as "Low",
      the alert copy says what actually happens, a missing location has a
      button, and a dead environment provider no longer takes the nearby-care
      list with it.

## Blocking the demo

Nothing in code and nothing in configuration. All three provider keys are
issued and verified live, and the deployment path is ready to run
(`docs/DEPLOY.md`). What remains is a host, a domain, and two decisions
rather than a build:

- **B-010, alert delivery.** The pipeline generates and stores alerts and
  sends nothing. The app picks them up while it is open, so a high-pollen
  alert reaches the user only while the app is running. A delivery channel
  (SMTP, a webhook, push) is a decision about infrastructure and credentials.
- **B-020e, the operator.** The privacy policy needs a 사업자 name and a
  사업자등록번호 before it can be published, and a lawyer has to sign off on
  the text. `requires_legal_review` stays `true` until a human says so.

## Verified working

Against real Postgres and live providers, 2026-10-15: register, login, the full
chat graph over SSE in Korean reaching EMERGENCY with a verdict matching the
rule engine, the ten-phrasing extraction eval across three languages, the Today
screen rendering real air quality, weather and nearby hospitals, and real KMA
pollen (`weed=LOW` for Seoul, tree correctly withheld out of season). Earlier,
on 2026-10-03: the same chat and eval results plus triage persistence; earlier
still, on 2026-09-09: allergy CRUD, environment for Seoul, triage both mild and
emergency with rows persisted, alerts and preferences, and frontend login.

## Parking lot

- **ML personalization (spec Phase 7).** Deliberately not built. The spec says
  the system "can *eventually* provide personalized insights" — it is a
  roadmap phase, not a release gate, and its data substrate is already in
  place: `EnvironmentSnapshot` rows are written hourly by the notification
  scheduler and `SymptomEvent` rows carry symptoms, severity and trigger per
  conversation. What does not exist is anything that *reads* that history to
  find correlations. That is a real feature with a real design question
  (how many observations before a correlation is meaningful), so it wants its
  own brief rather than being quietly appended to a release.
- **Rate limiting beyond the chat endpoint.** `POST /api/chat` is now limited
  (see the parking-lot resolution below). The other endpoints are read-only or
  cheap; if the hospital or environment providers ever get keys with quotas
  worth protecting, they want the same treatment.
- **Multi-instance rate limiting.** The chat limiter is per-process and in
  memory, so N workers would each allow the limit and a restart clears it. Fine
  for the single-instance deployment this is; a shared store (the Redis already
  in `Settings`) is the upgrade path when it stops being fine.
