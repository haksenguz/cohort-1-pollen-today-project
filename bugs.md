# bugs.md

UI/UX and behaviour issues, newest first. Each entry records what was observed
and where, so a fix can be verified against the same surface.

Status: `open` · `fixed` · `wontfix`

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
- **Status:** fixed

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

**Fix.** Point `OPENAI_BASE_URL` at the issuing provider
(`https://api.minimax.io/v1`), and document the pairing in `.env.example`.
Verified: a 3-turn conversation now extracts `["itchy_eyes", "sneezing"]`,
replies in free text, and the deterministic engine returns
`LOW — severity 3 < 7, no red flags`.

**Why this was hard to see.** `_classify` maps `AuthenticationError` to
`"unavailable"`, the same bucket as a genuine outage. A wrong host and a dead
provider are indistinguishable in the logs.

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

**Fix.** `.stage` padding reduced to 12px, Settings-scoped card gap to 10px
(`--card-spacing: 0.75rem`), and the manual coordinate entry is now behind a
closed `<details>` disclosure (see B-004), which removes most of the height the
complaint was about.

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
PM2.5 and PM10 (birch, oak, alder, willow, poplar, Japanese cedar, peach,
olive, timothy, cocksfoot, zoysia, Bermuda grass, ragweed, mugwort,
cocklebur, beggar ticks, lamb's quarters, dock, alternaria, cladosporium,
house dust mite, cockroach). Legacy coarse values stay valid and are resolved by
category, so `risk.py` scores BIRCH the same as TREE_POLLEN and existing rows
keep working. `user_allergies.allergen` is a bare `VARCHAR(30)` with no CHECK
constraint, so this is **no DDL and no alembic revision**.

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
gone; `.agentbar` is layout-only.

---

## B-010 — Alerts only exist when you open the Alerts tab

- **Reported:** 2026-10-14 (self-identified, while answering "how do
  notifications work?")
- **Surface:** `/alerts`
- **Status:** open

**Observed.** The alert pipeline works but has no delivery mechanism. There is:

- **No web push.** No `PushManager`, no `pywebpush`, no service-worker push
  handler anywhere in the codebase.
- **No polling.** `AlertsPage.tsx` calls `listAlerts()` once on mount. Nothing
  re-fetches while the app sits open in the background.

So a high-pollen alert is generated server-side but reaches nobody until the
user happens to tap the Alerts tab.

**Why it matters here.** This is an allergy app. The entire value of an alert
is that it arrives *when the risk changes* — an hour-long APScheduler tick
(`CHECK_INTERVAL_MINUTES = 60`) that nobody is listening to is not an alert.
The conditions it fires on (pollen spike, air quality) are exactly the ones
where a user is outdoors and not looking at the app.

**Options, cheapest first.** (a) poll `/api/alerts` every few minutes while the
app is open — a few lines, no new permissions, no service worker. (b) Web Push
with a service worker — real background delivery, needs VAPID keys and an
opt-in prompt. (c) Email. (a) is a stopgap that still only works with the app
open; (b) is the actual fix.

Not built yet — it changes the permission story and needs a decision.

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
- **Status:** open — awaiting a decision

**Observed.** "Settings" renders at 10.5px in a 25%-width tab. At 375px viewport
that is roughly 24px of usable text width and the label reads cramped next to
the shorter "Chat" / "Today" / "Alerts".

**Options.** (a) drop to 10px, (b) rename to "More", (c) leave it. Cosmetic
only — no functional impact.