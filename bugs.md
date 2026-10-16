# bugs.md

UI/UX and behaviour issues, newest first. Each entry records what was observed
and where, so a fix can be verified against the same surface.

Status: `open` · `in progress` · `fixed` · `wontfix`

---

## B-014 — The agent is a chatbot, and the chat screen discards what the engine already decided

- **Reported:** 2026-10-16 (user-reported: *"it's not an agent but it's just a chatbot"*)
- **Surface:** `backend/app/agents/symptom_agent.py`, `backend/app/api/chat.py`,
  `backend/app/api/hospitals.py`, `frontend/src/chat/allergyChatAdapter.ts`,
  `frontend/src/routes/SettingsPage.tsx`
- **Status:** open — master backlog. Group A is the blocking work; the rest is
  ordered by what unblocks it.

**Observed, part one: it is not an agent.** `LLMClient` is a single
`complete(messages) -> str` (`chat.py:288`). One call in, one string out, no
tools, no loop, no plan, no observation step. A turn is a fixed pipeline —
extract, decide whether more questions are needed, call the rule engine — and
the model never chooses its own next action. That is the definition of a
chatbot. The stage labels the UI shows ("extracting", "assessing") are pipeline
stages this codebase emits, not actions the model decided to take, and B-009
already pinned that distinction with a test.

**Observed, part two: the nearest-hospital capability is unreachable.** The
backend *already* answers "what medical facilities are near me" — `GET
/api/hospitals/nearby` (`hospitals.py:59`) ranks Naver Local Search results by
Haversine distance and returns name, address, distance, specialty, phone. The
agent cannot call it, because it has no tools. There is no schedule or
availability data anywhere in the codebase, and no booking of any kind. The
endpoint also cannot answer "who is open now" — Naver Local Search returns no
opening hours, and `hospitals.py:99-102` documents that the old `open_now` filter
was *removed, not faked*. Capping at 5 results with no pagination is the other
inherited limit.

**Observed, part three: the safety verdict is computed, sent, and thrown away.**
`chat.py:231` puts `triage_level` and `triage_reasons` in the `done` event.
`types.ts:215-217` types them. `allergyChatAdapter.ts:128` then keeps only
`conversation_id` and discards the rest. A frontend-wide grep for `triage`
returns the types, the client, and a test fixture — **no component reads it.** The
deterministic verdict that ADR 0001 makes the app's central safety property
renders as ordinary body text in a chat bubble, with no card, no styling, and no
one-tap `tel:119`.

**Observed, part four: there is no session.** `allergyChatAdapter.ts:30` holds
the conversation id in a module-level `let`. Refresh the page or reopen the
installed PWA and it is `null` — the next message silently starts a new
conversation. Meanwhile `conversations` and `messages` (`models/__init__.py:44`,
`:53`) persist every turn, and no endpoint in `backend/app/api/` can list or
load them.

**The constraint that outranks all of it.** ADR 0001: the LLM does conversation
and extraction; `services/triage.py` owns every safety decision. Giving the model
tools does not move that line. A `find_hospital` tool is an *action*; an
`assess_urgency` tool must never exist. Every tool below is lookup or booking.
The booking confirm step is a hard human gate — the model may propose a slot, the
patient must accept it before any write. Booking without a confirmed slot is not
a booking, and a failed or timed-out write is not a booking.

Standards for each item are cited in the original review; the agent-loop and
healthcare-scheduling items follow the ReAct pattern (reason → act → observe)
and the reference healthcare-agent architecture in
[group D](#d-agent-harness--the-actual-fix).

### A. Safety-critical — do these before anything else

- [ ] **A1. Render the triage verdict.** Attach `triage_level` + `triage_reasons`
      to the assistant message (assistant-ui data parts) and render a verdict
      card. EMERGENCY gets a persistent, high-contrast banner.
- [ ] **A2. One-tap `tel:119`** on the EMERGENCY card. The disclaimer at
      `ChatScreen.tsx:109` is static footer text; the call button must be
      attached to the verdict, at the moment the verdict exists.
- [ ] **A3. Surface the post-triage next action.** `hospitals.py` exists and the
      chat never calls it. A verdict should lead to "find care near you".
- [ ] **A4. Never let a tool change a safety verdict.** Pin with a test that no
      tool schema can return a `triage_level`, so ADR 0001 cannot be eroded
      quietly by a future tool.

### B. Chat sessions — nothing survives a reload

- [ ] **B1.** `GET /api/conversations` — list, newest first, per user.
- [ ] **B2.** `GET /api/conversations/{id}` — full message history, resumable.
- [ ] **B3.** Move the id out of the module variable into the URL: `/chat/:id`,
      plus `/chat` meaning "start a new one".
- [ ] **B4.** History drawer / screen: title, relative timestamp, one-line preview.
- [ ] **B5.** Auto-generate a conversation title from the first user message
      (needs a `title` column — the model has none).
- [ ] **B6.** New Chat button.
- [ ] **B7.** Search across conversations (required by ~30 conversations, per
      Android's settings guidance; expected sooner here since they accumulate fast).
- [ ] **B8.** Resume an in-flight turn after reload — snapshot + SSE replay with
      `Last-Event-ID`, so a dropped stream is not a lost answer.

### C. Chat experience

- [ ] **C1. Real token streaming.** `chat.py:220` sends the whole reply in one
      `message` event. Stream deltas; target first token under ~800ms.
- [ ] **C2. Markdown rendering** to semantic HTML — the model already emits
      `**bold**` and lists, currently rendered literally.
- [ ] **C3. Retry / regenerate** the last response without retyping.
- [ ] **C4. Copy message.**
- [ ] **C5. Timestamps** on messages.
- [ ] **C6. Suggested prompts / quick replies** on the empty state — today it is
      prose only, so a new conversation opens on a blank field.
- [ ] **C7. Jump-to-latest** button when the user scrolls up (auto-scroll exists,
      the escape hatch does not).
- [ ] **C8. Feedback** thumbs up/down per assistant message.
- [ ] **C9. Voice input** — the user is short of breath or on the bus; typing is
      the wrong input for this app.
- [ ] **C10. Offline state for chat** — queued send / clear "you're offline"
      inside the chat screen, not just the global banner.
- [ ] **C11. Citations / confidence** so the output feels reviewable.

### D. Agent harness — the actual fix

Sources: [ReAct / core concepts](https://cloud.google.com/resources/core-concepts-ai-agents) ·
[agent vs chatbot](https://redis.io/blog/ai-agent-vs-chatbot/) ·
[5-layer agent stack](https://www.taskade.com/blog/ai-agent-stack) ·
[JetBrains agent guide](https://www.jetbrains.com/pages/ai-agents/what-are-ai-agents/) ·
[healthcare agent architecture](https://www.appther.com/blogs/build-healthcare-ai-agent) ·
[scheduling workflow stages](https://thoughtly.com/blog/ai-agents-healthcare-appointment-scheduling-intake)

- [ ] **D1. Tool-calling loop.** The model receives typed tool schemas and
      chooses which to call, with what arguments, in what order. `LLMClient`
      grows a `bind_tools` / function-call path instead of returning a bare string.
- [ ] **D2. ReAct loop.** Reason → act → observe → repeat, with a hard step and
      cost cap. Bounded and observable, never an open-ended while-loop.
- [ ] **D3. `search_nearby_care`** tool → wraps `find_nearby_hospitals`. First
      argument: the user's stored location, not a re-typed coordinate.
- [ ] **D4. `check_availability`** tool. **Blocked upstream:** Naver Local Search
      returns no hours. Resolve a real source (hospital booking APIs / 지역 health
      centre data) before writing this tool. Do not let the model infer or guess
      availability from static text — an invented clinic hour is exactly the kind
      of confident wrong answer that makes this dangerous.
- [ ] **D5. `book_appointment`** — writes only after explicit patient
      confirmation, atomically, so two users cannot take the same slot.
- [ ] **D6. `reschedule` / `cancel`** the same slot.
- [ ] **D7. Multi-step without a flowchart.** "Soonest opening across 5 doctors"
      should make the agent call availability five times and compare, with nobody
      coding that branch. This is the acceptance test that it is genuinely agentic.
- [ ] **D8. Working memory** across a turn — tool results feed the next reason
      step. Today there is no place to put them.
- [ ] **D9. Long-term memory** across sessions: known allergies, severity, past
      episodes, preferred hospital, language.
- [ ] **D10. Grounding / RAG layer** over approved content — self-care guidance,
      what the triage levels mean, what to do before an appointment.
- [ ] **D11. Human escalation path** — hand off to a person when the request
      leaves the approved workflow.
- [ ] **D12. Audit log of every tool call**, for a medical app that books
      appointments.
- [ ] **D13. Explicit autonomy level per tool** — read-only tools vs
      write-actions requiring confirmation. Every failure and every exception must
      land in an owned state, not a dead end.
- [ ] **D14. Timeouts and retries per tool**, with honest failure copy. A
      scheduling API that is slow must degrade to a list, never to silence.
- [ ] **D15. Appointment model + tables** — provider, location, service type,
      duration, slot, booking, status. None of this exists in the ERD yet.
- [ ] **D16. Confirmation + reminder** delivery (ties into B-010).

### E. Settings page

- [ ] **E1. Sign out button.** `AuthContext.tsx:82` exports `logout` and *no
      component ever calls it* — there is no way to log out of this app.
- [ ] **E2. Restructure to an overview list.** Label + current value per row,
      each opening a subscreen, instead of three fully-expanded cards.
- [ ] **E3. Show live values as subtext** (Android: show status under the title).
- [ ] **E4. "Restore defaults"** for preferences.
- [ ] **E5. Destructive section at the bottom**, visually separated: delete
      account, delete my data.
- [ ] **E6. Move the dev LLM key card behind "Advanced"** (≥3 items justifies the
      subsection; it should not sit in the consumer list).
- [ ] **E7. Drop the System/Light/Dark cycle button** from the header. Apple HIG:
      respect system settings, do not duplicate them in-app. Honour
      `prefers-color-scheme`.
- [ ] **E8. Emergency contact** — the highest-value missing setting for an allergy
      app; every OS ships its own version.
- [ ] **E9. Privacy & data** — what is stored (location, messages, symptom
      events), export, delete. None of it is currently viewable.
- [ ] **E10. Language** — the composer says "any language"; the UI is
      English-only.
- [ ] **E11. Units** — °C/°F, pollen concentration. Absent from the API too.
- [ ] **E12. Chat preferences** — agent language, voice on/off, keep-history.
      Depends on group B.
- [ ] **E13. Notification quiet hours + a link to the OS permission state.**

### F. Accessibility

- [ ] **F1. `role="log"` + `aria-atomic="false"` + `aria-busy` on the transcript.**
- [ ] **F2. Announce the finished message once**, never every token.
- [ ] **F3. Keyboard contract** — Enter sends, Shift+Enter newline, Escape
      cancels, ↑↓ recalls history.
- [ ] **F4. Text size control**, 200% without loss of content (WCAG 2.2).
- [ ] **F5. `prefers-reduced-motion`** guard on the activity pulse
      (`ChatScreen.tsx:42`).
- [ ] **F6. 44×44px tap targets** on the new controls.

**Suggested order.** A1–A4 → B1–B3 → D1–D4 → B4–B8 → C1–C2 → E1–E7. A group A
is a safety hole in an app whose central claim is that a deterministic engine
decides urgency, and it is a small diff. Group D is the difference between a
chatbot and an agent, and D4 is blocked on a data source rather than on code —
worth starting that search now, in parallel with A.

---

## B-013 — `App.tsx` still documented a demo session that no longer exists

- **Reported:** 2026-10-16 (self-identified, while reconciling this file after the rebuild)
- **Surface:** `frontend/src/App.tsx`, `frontend/src/auth/AuthContext.tsx`
- **Status:** open — stale comment only, no runtime effect

**Observed.** `App.tsx` routes still carry the demo-mode comment:

> *"AuthProvider boots straight into the demo session so RequireAuth always
> passes."*

That stopped being true in `9ed4012`. `AuthContext.tsx` now documents the
opposite in a docstring of its own — *"No demo session"* — and no longer boots
to a hardcoded `DEMO_USER`. With no token it sets `status: "unauthenticated"`
and `RequireAuth` redirects to `/login`.

**Why it matters.** The comment is the only surviving statement in the frontend
that the fake session is still a supported mode. Someone reading `App.tsx`
would conclude a fresh install authenticates itself, which is precisely the
belief that produced `9ed4012`. The behaviour is correct today; only the
description is wrong.

**Fix.** Delete the comment. `/login` and `/register` are still routable for
manual testing, and the `/profile` → `/settings` redirect below it is accurate,
so nothing else in that block needs to change.

---

## B-012 — A commit shipped tests for code it did not ship

- **Reported:** 2026-10-15 (found by a clean checkout of `feat/ismoiljon`)
- **Surface:** `frontend/src/components/InstallPrompt.test.tsx`, `AppShell.tsx`
- **Status:** fixed

**Observed.** `92a4934` is titled *"settings screen, sonner toasts and
screen-space fixes"* and ships `sonner.tsx` plus `InstallPrompt.test.tsx` — but
not the code that test asserts on. At that commit `AppShell` mounts no
`<Toaster />`, `InstallPrompt` still rendered `div.pwa-toast` twice, and the new
test asserted `querySelector(".pwa-toast") is null`. **A clean checkout of the
branch could not pass its own frontend suite.** The work had been committed from
a dirty working tree, and only the files that happened to be staged went with it.

**Why the suite looked green.** The assertion was written so it could pass
against either implementation: it queried for `.pwa-toast` on a render where no
install prompt was visible, so it passed whether or not the fix had landed. A
test that cannot fail is worse than no test — it converted a half-landed commit
into a passing build.

**Fix.** `b28a3a6` lands what was left in the working tree: `AppShell` mounts
the single `<Toaster />`, `InstallPrompt` / `UpdatePrompt` / `OfflineBanner` fire
toasts and return `null`, and `.pwa-toast` / `.pwa-offline` are deleted from
`theme.css`. The test now fires the event *first* and asserts after, so it
actually exercises the behaviour it describes.

**Lesson, recorded because the rebuild will produce this again.** The lesson is
not "add more tests" — `InstallPrompt.test.tsx` already existed. It is that a
commit message must describe what the commit contains, and the suite must be
verified from a clean checkout rather than from a working tree that holds the
missing files.

---

## B-011 — Pollen integration called an endpoint that does not exist

- **Reported:** 2026-10-15 (self-identified, while closing I3 with the key in place)
- **Surface:** `/api/environment/current`, `backend/app/services/pollen_service.py`
- **Status:** fixed

**Observed.** With `POLLEN_API_KEY` finally filled in, pollen still showed
"Unavailable". Every request returned:

```
HTTP 400
{"OpenAPI_ServiceResponse": {"cmmMsgHeader": {
   "errMsg": "NO_OPENAPI_SERVICE_ERROR",
   "returnAuthMsg": "해당 오픈API 서비스가 없거나 폐기됨",
   "returnReasonCode": "12"}}}
```

**Root cause.** The service had been written from data.go.kr's platform-wide
conventions rather than from KMA's actual API, and its own docstring said the
operation and field names were unconfirmed. Four separate guesses were wrong:

- **Service name.** `HealthWeatherIdxServiceV3` does not exist. It is
  `HealthWthrIdxServiceV3` — "HealthWthr", not "HealthWeather".
- **Operation.** `getPlrsIdxTodyList` does not exist. There are three
  operations, one per species: `getOakPollenRiskIdxV3`,
  `getPinePollenRiskIdxV3`, `getWeedsPollenRiskndxV3`.
- **`areaNo`.** A 2-digit 시도 code like `"11"`. It is a 10-digit station code;
  Seoul is `1100000000`. The 2-digit code returned "service does not exist" too.
- **Params.** `date=YYYYMMDD` is not a parameter. The required set is
  `serviceKey`, `numOfRows`, `pageNo`, `dataType`, `areaNo`, `time`, where
  `time` is the 발표시간 stamp (YYYYMMDDHH).

**Why it was invisible.** The parser degraded to empty data on every failure,
by design, and empty pollen renders as "Pollen: Unavailable" — the same screen
as "no key configured". So the one thing the feature could not do, return real
data, looked exactly like the state it was shipped in. A 400 from
data.go.kr also reads as an auth problem: reason code 12 means *the call URL is
wrong*, while a bad key gives a different code. I spent the first pass
chasing the key, not the URL.

**Fix.** Rewrote the client against the confirmed contract (all six
provider answers above, captured live 2026-10-15 and written up in
`docs/research/pollen-providers.md`). Added
`backend/scripts/verify_live_pollen.py`, which prints what the provider
actually answered and exits non-zero when the parse yields nothing — so the
next silent mismatch fails a command instead of a screenshot. 15 tests in
`tests/test_pollen_service.py` pin the two ways the provider says "no data":
out-of-season `resultCode: "99"` with no body, and a blank `today` for an
unpublished hour. Both were `LOW` before.

**Also fixed while in there.** `_fetch_kma` logged with `exc_info=True`, and
httpx exception text embeds the full request URL — `serviceKey` included — so
the degrade path wrote the key to the log. Now it logs the operation name,
area and stamp without the exception.

**Known limit, not fixable with this key.** KMA publishes no station for
Gwangju, Gangwon, Jeonbuk and Jeonnam — verified by pulling all 3851 stations
with an empty `areaNo`, nothing under prefixes 29/42/45/46. Those provinces
return "no data" rather than the nearest served province's reading, because
for an allergy app a neighbouring region's pollen is worse than an empty row.

---

## B-007 — Chat agent silently answered with hardcoded text

- **Reported:** 2026-10-13 (self-identified)
- **Surface:** `/chat`
- **Status:** fixed locally, but reproduces on a clean checkout — the
  `.env.example` half never landed

**Observed.** Every turn replied *"Are you having any difficulty breathing, or
swelling of your lips, tongue, or throat?"* — that string is `SAFETY_QUESTION`,
a constant in `symptom_agent.py`, not model output. Extraction returned `[]` and
the stream ended with an `error` event carrying `kind: "unavailable"`.

**Root cause.** `OPENAI_BASE_URL` was set to `https://openrouter.ai/api/v1` while
`OPENAI_API_KEY` was a **MiniMax** key (`sk-cp-…`, 125 chars). Every call
401'd with `{"message": "Missing Authentication header"}` — a misleading
provider message: the SDK *was* sending `Authorization: Bearer …` (verified,
132-char header). A key is only valid against the host that issued it.

The failure was invisible in the UI because `make_ask_question_node` falls back
to `SAFETY_QUESTION` whenever `breathing_difficulty`/`airway_swelling` are
unanswered, and the first turn always leaves both `None`. The app degraded to
canned text and looked alive.

**Fix.** `OPENAI_BASE_URL` was repointed at the issuing provider
(`https://api.minimax.io/v1`). Verified: a 3-turn conversation now extracts
`["itchy_eyes", "sneezing"]`, replies in free text, and the deterministic engine
returns `LOW — severity 3 < 7, no red flags`.

**Partially landed — the documented half never made it in.** This entry
previously claimed the pairing was documented in `.env.example`. It is not.
`.env.example` lists `OPENAI_API_KEY=` (line 7) and nothing else for the LLM:
no `OPENAI_BASE_URL`, no `OPENAI_MODEL`, and no note that a key is only valid
against the host that issued it — which is the entire root cause of this bug.

The live environment is correct because the fix went into the gitignored local
`.env`, where it works and where nothing preserves it. A fresh clone has
`OPENAI_API_KEY` and an unset base URL, which defaults to the OpenAI host, and
a non-OpenAI key 401s against it. **This bug reproduces on a clean checkout.**

Fix is one comment and one line in `.env.example`, ideally:
`OPENAI_BASE_URL=https://api.minimax.io/v1` with a comment stating it must match
the provider that issued `OPENAI_API_KEY`.

**Why this was hard to see.** `_classify` maps `AuthenticationError` to
`"unavailable"`, the same bucket as a genuine outage — verified in
`openai_client.py`, where a rejected key, a wrong host, and a network blip all
return `unavailable`. A wrong host and a dead provider are indistinguishable in
the logs.

---

## B-001 — Install hint is a hand-rolled panel, not a toast

- **Reported:** 2026-10-13
- **Surface:** any screen, bottom of viewport (`/login` and `/profile` both showed it)
- **Status:** fixed

**Observed.** A white bubble reading "On iPhone: tap Share then Add to Home
Screen." sat over page content, overlapping the "Save key" button on `/login`.
It was a raw `div.pwa-toast` with a hand-written close button — no auto-dismiss,
no stacking, no portal.

**Fix.** Adopted `sonner` (the shadcn default). One `<Toaster />` mounts at the
app root in `AppShell.tsx`; `InstallPrompt`, `UpdatePrompt` and `OfflineBanner`
all route through it and now render `null`. The iOS hint auto-dismisses at 8s.
`.pwa-toast*` and `.pwa-offline` are deleted from `theme.css`. Covered by
`InstallPrompt.test.tsx` (4 tests).

---

## B-002 — Login screen wastes vertical space

- **Reported:** 2026-10-13
- **Surface:** `/login`
- **Status:** fixed

**Observed.** `.auth-screen` centred its content with `gap: 18px` and
`padding: 28px 22px`. On a 375×812 viewport the sign-in form plus the dev key
card overflowed the fold.

**Fix.** `.auth-screen` is now top-aligned (`justify-content: flex-start`) with
`padding: 20px 20px 28px` and `gap: 12px`; `.auth-form` gap 10px, `.field` gap
5px. The sign-in form fits without scrolling.

*Still open:* the dev key card is not a collapsed disclosure as originally
scoped — it renders expanded on `/login`. Worth revisiting alongside the
UI/UX pass.

---

## B-003 — Settings page wastes vertical space

- **Reported:** 2026-10-13
- **Surface:** `/settings` (was `/profile`)
- **Status:** fixed

**Observed.** Every card carried a description paragraph plus large internal
padding; `Location` took ~300px for two inputs and a button.

**Fix.** The page wrapper is now `<div className="stage flex flex-col gap-4">`
with each card's body at `flex flex-col gap-3`/`gap-4`. But the bulk of the
reclaimed height came from one change, not from padding: the manual coordinate
entry moved behind a closed `<details>` disclosure, so `Location` shows a single
"Use my current location" button instead of two inputs and a Save button by
default. That is what actually removed the ~300px.

**Corrected against the shipped CSS.** An earlier version of this entry claimed
`.stage` padding was reduced to `12px` and that Settings used
`--card-spacing: 0.75rem`. Neither is true of the current code. `.stage` in
`theme.css` is `padding: 16px`, unchanged, and `--card-spacing` is the shadcn
`Card` component's own default (`--spacing(4)`) from `components/ui/card.tsx` —
there is no Settings-scoped override of it. The fix is the disclosure, not the
spacing.

---

## B-004 — Location is entered as raw latitude/longitude

- **Reported:** 2026-10-13
- **Surface:** `/settings` → Location
- **Status:** fixed

**Observed.** The user was asked to type `37.5665` / `126.9780` by hand — a
developer affordance in a consumer health app.

**Fix.** The primary action is now "Use my current location" calling
`navigator.geolocation.getCurrentPosition`. Manual entry sits behind an
"Enter coordinates manually" disclosure, opened automatically on any failure.
GPS and manual paths share one `persist()` function, so there is a single
validation and write path. Denied / unavailable / timeout / unsupported are
each named explicitly rather than failing silently. 7 tests.

*Follow-up fixed in the same pass:* the clear-location branch of `persist()`
called `updateCurrentUser` outside any `try`/`catch` and never raised `saving`,
so a rejected clear produced an unhandled rejection, no message on screen, and
a still-enabled Save button. Both paths now share one guarded write; two
regression tests cover it.

---

## B-005 — Allergen list is generic, not real

- **Reported:** 2026-10-13
- **Surface:** `/settings` → Allergies
- **Status:** fixed

**Observed.** The picker offered `Tree pollen`, `Grass pollen`, `Weed pollen`,
`PM2.5`, `PM10`, `Dust`, `Mold`, `Other`. "Tree pollen" is not something a
person with hay fever can say they are allergic to.

**Fix.** 26 named allergens across Tree / Grass / Weed / Mould / indoor plus
PM2.5 and PM10 (8 tree — birch, oak, alder, willow, poplar, Japanese cedar,
peach, olive; 6 grass — timothy, cocksfoot, zoysia, Bermuda grass, silver grass,
weeping grass; 6 weed — ragweed, mugwort, cocklebur, beggar ticks, lamb's
quarters, dock; 2 mould — alternaria, cladosporium; 2 indoor — house dust mite,
cockroach; 2 particulates — PM2.5, PM10). Legacy coarse values stay valid and
are resolved by category, so `risk.py` scores BIRCH the same as TREE_POLLEN and
existing rows keep working. `user_allergies.allergen` is a bare `VARCHAR(30)`
with no CHECK constraint, so this is **no DDL and no alembic revision**.

**Corrected against `enums.py`.** The original text named 22 of the 26 and
omitted silver grass and weeping grass. It also described PM2.5 and PM10 as
sitting alongside the mould/indoor group; in `ALLERGEN_CATEGORY` they resolve to
their own `AIR_QUALITY` category, not to either. Scoring matches on
`AllergenCategory`, never on the exact species.

*Still open:* the species list came from established clinical classification,
not from a confirmed Korean source — KDCA / JASA / AAAAI-Korea were all
unreachable during the build. Confirm before treating the list as authoritative.

---

## B-006 — `ChatAgentStatus` bypasses the design system

- **Reported:** 2026-10-13 (self-identified)
- **Surface:** `/chat`
- **Status:** fixed

**Observed.** `DevLlmSettingsCard` uses the shadcn primitives (`Card`, `Field`,
`Input`). `ChatAgentStatus`, written alongside it, was raw `div`s styled by
hand-rolled `.agentbar*` classes. Two notification systems on one screen, with
colours picked by eye and never contrast-checked.

**Fix.** Rebuilt on shadcn `Alert` / `AlertTitle` / `AlertDescription` with
`TriangleAlert` / `CircleCheck` icons, so colour comes from theme tokens per
ADR 0004. `.agentbar-warn` and the guessed `--warn-soft` / `--text` values are
gone.

**Corrected against `theme.css`.** This entry previously claimed "`.agentbar` is
layout-only". It is not — there is **no `.agentbar` rule in `theme.css` at all**.
`ChatAgentStatus.tsx` still emits three class names that match nothing:
`agentbar` (the wrapper `<div>`, twice), `agentbar-link` (the "Add your API
key" link), and `agentbar-dim` (the model name in the ready state). They render
as unstyled elements, which happens to look acceptable today because the
`Alert` inside supplies all the visible styling.

The one place it shows: `agentbar-dim` is named for the dimmed `--ink-soft` the
model name is supposed to use, and with no rule it inherits full `--ink` — the
ready line reads at the same weight as the status text beside it. Either add the
two rules or drop the class names; do not leave a class that promises a colour
it does not deliver.

---

## B-010 — Alerts only exist when you open the Alerts tab

- **Reported:** 2026-10-14 (self-identified, while answering "how do
  notifications work?")
- **Surface:** `/alerts`
- **Status:** in progress — fix under active development

**Observed.** The alert pipeline works but has no delivery mechanism. As of
this entry, the codebase still contains:

- **No web push.** No `PushManager`, no `pywebpush`, no service-worker push
  handler anywhere in the frontend or backend.
- **No polling.** `AlertsPage.tsx` calls `listAlerts()` once in a `useEffect`
  keyed on `[unreadOnly]`. There is no interval, no visibility listener, and no
  refetch on focus — nothing re-fetches while the app sits open in the
  background. The only way to move the list is to toggle the "Unread only"
  filter or leave and re-enter the route.

So a high-pollen alert is generated server-side but reaches nobody until the
user happens to tap the Alerts tab.

**What does exist today.** Generation is real and server-side:
`notification_service.py` exposes `start_scheduler()`, an in-process APScheduler
`AsyncIOScheduler` wired into the FastAPI lifespan in `main.py`, running
`run_environmental_checks` for every user with a stored location on
`CHECK_INTERVAL_MINUTES = 60`. Alerts persist to the `alerts` table and are
readable at `GET /api/alerts`. The break is strictly in the last mile —
server produces, client never asks again.

**Why it matters here.** This is an allergy app. The entire value of an alert
is that it arrives *when the risk changes* — an hour-long scheduler tick that
nobody is listening to is not an alert. The conditions it fires on (pollen
spike, air quality) are exactly the ones where a user is outdoors and not
looking at the app.

**Options, cheapest first.** (a) poll `/api/alerts` every few minutes while the
app is open — a few lines, no new permissions, no service worker. (b) Web Push
with a service worker — real background delivery, needs VAPID keys and an
opt-in prompt. (c) Email. (a) is a stopgap that still only works with the app
open; (b) is the actual fix.

**Not built yet — it changes the permission story and needs a decision.** A fix
is in flight; this entry stays open until it lands and the behaviour above is
no longer true.

---

## B-009 — Chat went silent for the whole turn

- **Reported:** 2026-10-14 (user-reported)
- **Surface:** `/chat`
- **Status:** fixed

**Observed.** "When the agent is doing something it should say or do
something — thinking… using tool… and so on."

A turn is two sequential model calls plus the rule engine. Measured live, that
is **1.3–7 seconds** of a composer doing nothing and an empty message list.
That reads as broken: users resend, or conclude the agent died.

**Fix.** The graph now reports its own progress through a `progress` callback
(`symptom_agent.py`), and `chat.py` turns that into `status` SSE events. The
turn runs on a worker thread while the generator drains a queue, so stages
arrive as they happen rather than batched at the end. The frontend renders them
in `chat/activity.ts` above the composer, with a pulsing dot and
`prefers-reduced-motion` respected.

Measured stream:

```
turn 1  starting (+0.02s) -> extracting (+0.04s) -> saving (+0.97s)
turn 2  starting (+0.01s) -> extracting (+0.04s) -> asking (+1.35s) -> saving (+2.04s)
turn 3  starting (+0.01s) -> extracting (+0.04s) -> assessing (+1.25s) -> saving (+1.25s)
```

**These are pipeline stages, not tool calls.** This agent has no tools and does
no function-calling — `LLMClient` is a single `complete(messages) -> str`. A
test (`test_progress_only_ever_emits_known_stages`) pins the allowed stage names
so nobody can quietly introduce a fake "using tool X" label. `assessing` reads
"Applying the safety rules" because that verdict comes from `triage.py`, not
the model, and showing it is the clearest possible statement of ADR 0001.

`ChatAgentStatus` was also re-mounted on `/chat` — a `git reset --hard` had
reverted `ChatScreen.tsx` and silently orphaned it.

---

## B-008 — Bottom-nav label is tight at 25% width

- **Reported:** 2026-10-13 (self-identified)
- **Surface:** `/settings` → bottom nav
- **Status:** fixed — the original measurement was wrong, and the number never
  described the shipped CSS

**Originally observed.** "Settings" was reported as cramped in its tab, at
"roughly 24px of usable text width" on a 375px phone. That figure does not
correspond to any layout the app has ever shipped, so the entry is corrected
below against the real CSS.

**Re-measured.** `.nav a` in `theme.css` is `flex: 1` with `padding: 9px 0
11px` — **zero horizontal padding** — at `font-size: 10.5px`,
`font-weight: 600`. `BottomNav.tsx` renders four tabs (`Chat`, `Today`,
`Alerts`, `Settings`), so `flex: 1` splits the row evenly:

| viewport | shell width | tab width | "Settings" at 10.5px/600 | headroom |
| --- | --- | --- | --- | --- |
| 375px | 375px | 93.75px | ~38–40px | ~2.3× |
| 412px (`max-width`) | 412px | 103px | ~38–40px | ~2.6× |

"Settings" is eight characters at 10.5px semi-bold in Hanken Grotesk, which is
roughly 3.6em of advance width — about 38px against 93.75px of content box. The
label occupies under half the tab. There is no wrap, no clip, and no
collision with the icon above it, and `.nav a` sets no `max-width` that could
cause either.

**What actually changed.** Settings became a bottom-nav tab rather than a
header gear, so the row went from three tabs to four. That is the real change
here, and it is the one worth keeping an eye on: each tab lost a quarter of its
width, from 125px to 93.75px at a 375px viewport. "Settings" survives that
comfortably because it is the longest label *and* the available space is more
than double it.

**If it ever does get tight**, the real levers are the label and the font size,
in that order — a 7-character "Settings" at 10.5px is not the binding
constraint, and neither is the tab width. Renaming to "More" would cost
clarity to solve a problem that is not currently occurring.