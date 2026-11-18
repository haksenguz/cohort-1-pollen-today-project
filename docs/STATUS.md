# Status

Updated: 2026-11-18. Branch `feat/ismoiljon`. Read with [`TASKS.md`](../TASKS.md)
for the task log and [`bugs.md`](../bugs.md) for the defect record.

## What is done

### Backend
- Auth: register and login with JWT. Register and login rate-limited per IP.
- Chat endpoint rate-limited per user (`CHAT_RATE_LIMIT_PER_MINUTE`, in memory).
- Consent: 민감정보 consent recorded, enforced on write paths, withdrawable.
- Privacy rights: summary, export, account deletion, health note.
- Conversations: list with search (`?q=`), detail, titles from the first message.
- Environment: Open-Meteo weather and air quality, graceful degradation.
- Pollen: KMA index, live and verified for Seoul.
- Hospitals: Naver Local Search, distance ranking, radius widens when empty.
- Alerts: generated hourly, stored, read and unread state, quiet-hour preferences.
- Emergency contact: read, save and clear.
- Web push: VAPID key endpoint, subscribe and unsubscribe, prune of dead endpoints.
- Bring-your-own LLM key per user: encrypted at rest, provider allowlist
  (groq, openai, openrouter), key never returned (hint only), no fallback to
  the server key when a user key is rejected.

### Agent and safety
- Triage rule engine (`triage.py`, `risk.py`) owns every safety verdict.
- Red-flag text scan in English and Korean (`red_flag_text.py`), with aliases.
- Negation guard: "no breathing difficulty" stays LOW.
- LangGraph symptom agent over SSE, with `status` and `tool` events.
- Bounded read-only tools: nearby clinics (Naver) and today's environment.
- Forced clinic lookup on every EMERGENCY verdict.
- Safety verdict runs without the model. A model outage does not block triage.

### Frontend
- Today screen with stale-while-revalidate cache: shows the last reading at once.
- Naver Map links for each clinic.
- Chat history, alerts inbox, settings redesign.
- Floating header and tab bar.
- Web push: service worker, Settings toggle.

### Deploy and quality
- Compose stack, Caddy TLS edge, nginx PWA, runbook (`docs/DEPLOY.md`).
- Config guard: production refuses to boot on weak secrets.
- CI: ruff, pytest on Postgres 17, pnpm lint, test and build.

## What is missing

### Backend
- Shared rate-limit store. Limits are per process, so N workers each allow the limit.
- Per-user chat limit has no shared store across instances (see above).
- Alert-creation push hook has no direct test. `send_push` is tested on its own.

### Agent and safety
- Agent turns take 4 to 8 seconds.
- Face and lip swelling has no red flag. It needs an ADR before code.
- Pollen and air context is not in the question prompt. The tool exists.
- The live eval drifts on two cases (severity 7 in English, `headache` in Uzbek).

### Frontend
- One 1 MB JS chunk. No route is lazy-loaded.
- Push is untested in a real browser and on iOS.
- Floating header and tab bar not yet checked on iOS Safari.
- 24 raw `font-size` px values in `theme.css`. Dead `.alert-*` rules remain.

### Deploy
- Live deploy never run on a host. No VPS, no domain.
- CI does not boot the Docker Compose stack on Postgres (the schema crash-loop slipped through once).
- Production secrets not yet set: `JWT_SECRET`, `LLM_KEY_SECRET`, VAPID keys, provider keys.
- One instance and one database volume only.

### Security and legal
- Privacy policy: operator name and registration number missing (B-020e).
- A lawyer has not signed off the policy text. `requires_legal_review` stays true.
- Alert delivery is push only, and it works only where push works.
