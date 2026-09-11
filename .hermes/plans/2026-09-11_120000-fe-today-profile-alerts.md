# Plan: FE — Today redesign, Profile screen, Alerts redesign

Date: 2026-09-11
Branch: `feat/ismoiljon`
Author: Ismoiljon (via Hermes plan mode)
Visual reference: `frontend/prototype.html` (read-only, kept in place)
Contract: `docs/API_CONTRACT.md` (source of truth for the wire shape)
Spec: `docs/pollen_documentation.md` (source of truth for behavior)

## Goal

Bring the `/today` and `/alerts` screens up to the prototype's visual standard and add a missing `/profile` screen so the user can manage their location, allergies, and notification preferences end-to-end. All work uses the existing typed client in `frontend/src/api/client.ts`; no new endpoints are required.

## Current context

- FE stack: Vite 8 + React 19 + TS + `react-router-dom` 7 + `vite-plugin-pwa`. Tests: Vitest 5 + jsdom + Testing Library. Lint: oxlint. Package manager: pnpm.
- Existing pages: `LoginPage`, `RegisterPage`, `TodayPage` (I6), `AlertsPage` (I6), `ChatPlaceholderPage`. Routes wired in `App.tsx`; auth gated by `RequireAuth` + `AuthContext`.
- The typed client (`client.ts`) already exposes **all** the calls we need for this plan: `getCurrentUser`, `updateCurrentUser`, `listAllergies`, `createAllergy`, `deleteAllergy`, `readPreferences`, `updatePreferences`, `listAlerts`, `markAlertRead`, plus the existing env/hospitals/chat ones.
- `frontend/src/api/types.ts` already has `UserResponse`, `UserUpdateRequest`, `AllergyResponse`, `AllergyCreateRequest`, `PreferenceResponse`, `PreferenceUpdateRequest`, `AlertResponse`, plus the enums `Allergen` (8 values) and `AllergySeverity` (3 values) and `RiskLevel` (4 values).
- `frontend/src/utils/format.ts` already has `formatRisk`, `riskClass`, `formatPollen`, `formatDistance`, `formatPoints`, `formatRelativeTime`. New formatters needed: `formatTemperature`, `formatAllergyLabel` (allergen enum → "Tree pollen"), `formatSeverityLabel`, `formatAlertType` (POLLEN → "pollen"). All pure, all unit-testable.
- `frontend/src/components/icons.tsx` has 6 icons; we'll add a small set for Profile and the new Today hero.
- `frontend/src/styles/theme.css` (587 lines) already has tokens, the app shell, BottomNav, TopHeader, risk dots, metric/list styles, alert rows, hospital rows, note block. **No hardcoded colors** — every color must reference a CSS variable already in `theme.css` (or extend `theme.css` to add the var).
- **Styling framework: Tailwind v4** (per [ADR 0003](../docs/adr/0003-tailwind-v4-frontend-styling.md), adopted 2026-09-11). The pure-CSS approach in this plan is superseded for new code; the migration of existing pages to Tailwind utilities is a prerequisite for the three verticals. `theme.css` shrinks to: token `:root` block (kept as source of truth) + non-inline `@theme` block (maps tokens to utilities) + `@custom-variant dark` + `@import "tailwindcss"`. Existing `.X { ... }` rules migrate to utility classes in JSX or are deleted.
- `docs/API_CONTRACT.md` documents 12 endpoints; the client uses 15. The 3 undocumented ones (`/api/alerts`, `/api/alerts/{id}/read`, `/api/notifications/preferences` GET/PUT) are part of this plan's surface. **Drift fix**: open a separate docs PR after the feature lands (out of scope for this plan — only flag in the commit body).
- Tests today: `format.test.ts` (8 cases), `client.test.ts` (8 cases), `TodayPage.test.tsx` (8 cases), `AlertsPage.test.tsx` (9 cases), `smoke.test.ts`. Plan adds ~12 new test cases across new formatters + the new Profile page + the redesigned pages.
- Standing rules from `AGENTS.md` / `CLAUDE.md` / `CONVENTIONS.md` / `DEFINITION_OF_DONE.md`:
  - Branch `feat/ismoiljon`, commit author **ismoiljon1101** (`ismoiljonedu@gmail.com`), no `Co-Authored-By`, never force-push `main`. CI gate: ruff + format + pytest (backend) + `pnpm install --frozen-lockfile && oxlint && pnpm build` (frontend). All checks are errors, not warnings.
  - No hardcoded regions, thresholds, coordinates, URLs, or channel names. Enums from one place. Pure functions get unit tests; React components get RTL tests; the rule engine (triage, risk) is **out of scope** and stays untouched.
  - PR green means: gate passes locally + CI green + AC met + DoD checklist walked through.
  - Prose: no em dashes, active voice, vary sentence length.

## Assumptions

- **Hard-coded data is acceptable for visual scaffolding.** Per the standing direction in this conversation, the new Profile screen and the redesigned Today/Alerts may render with sample data (`pollen_is_sample: true`) for the demo. **Do not** ship a "demo" tag in the UI — the existing `pollen_is_sample` note in `TodayPage` already handles the flag. Hard-coded allergy rows for new users are fine for the demo; they will be replaced when the user edits their profile.
- The prototype is the **visual reference**, not the implementation. We're free to make the React version better: a11y, keyboard, real focus rings, real form validation, real loading states, real error states. The prototype's `<script>`-driven imperative chat flow is **out of scope** (Jack's lane).
- Auth is already done; do not change `AuthContext`, `RequireAuth`, or `token.ts`. The Profile page reads the user from `useAuth()` exactly like `TodayPage` and `AlertsPage`.
- Backend keeps returning `pollen_is_sample: true` until the POLLEN_API_KEY lands. This is **not a blocker** for this plan — the UI handles it.
- We will **not** introduce new dependencies. Everything is possible with React 19 + the existing icons. The prototype's hand-rolled chip rows become real `<button>` elements with proper focus rings.

## Architecture / proposed approach

The plan is **three independent verticals** that can ship in any order. Each vertical follows the same shape: **typed wrapper around the contract → pure formatter helpers → small UI subcomponents → page composition → RTL tests**. This shape is the one an AI agent can build without guessing: every page is a thin layer over already-typed endpoints, and every helper is a pure function. No business logic in components.

**Design pattern chosen (per the user's request "best for AI agents"):** a **hooks + pure functions + presentational components** split, sometimes called "Container/Presentational" or "Lifting state up." Pages compose hooks (`useAuth`, custom data hooks) and pass plain data to small presentational components. State that is derived from props is derived during render, not stored in `useState`. Custom hooks for repeated fetch-and-reset patterns (we have two `oxlint-disable react/set-state-in-effect` sites in `TodayPage` and `AlertsPage`; the new code does not add more).

**Commit strategy:** small, single-purpose, conventional-commit-prefixed commits. One vertical per PR is too coarse — we'll commit per task. Each commit must leave the gate green (`pnpm install --frozen-lockfile && oxlint && pnpm build && pnpm test`).

## Step-by-step tasks

Tasks are grouped into **Foundations** (shared helpers used by ≥2 verticals) and the three verticals.

### F0 — Verify environment (1 minute)

**Why:** every task below assumes the toolchain is green. Verify once, then go.

```bash
cd frontend
pnpm install --frozen-lockfile
pnpm lint       # oxlint
pnpm build      # tsc -b && vite build
pnpm test       # vitest run
```

**Expected output:** all four exit `0`. If `pnpm build` fails because of pre-existing drift (e.g. on the working tree, `M backend/.env.example` and `M backend/app/agents/symptom_agent.py` per `git status`), that is fine for the FE side. Run `pnpm build` and `pnpm test` from `frontend/` only.

---

### Foundations (do these first; both verticals use them)

### F1 — Add pure formatter helpers in `frontend/src/utils/format.ts`

These are used by both the redesigned `Today` and the new `Profile`.

1. **`formatTemperature`** — accept `number | null`, return `"18°C"` / `"—"` (already-existing pattern from `formatDistance`).
3. **`formatAllergyLabel`** — accept `Allergen`, return the human label used in the UI. Map: `TREE_POLLEN → "Tree pollen"`, `GRASS_POLLEN → "Grass pollen"`, `WEED_POLLEN → "Weed pollen"`, `PM25 → "PM2.5"`, `PM10 → "PM10"`, `DUST → "Dust"`, `MOLD → "Mold"`, `OTHER → "Other"`. Pure data map at module top, identical shape to the existing `RISK_LABEL` map. Fall back to the raw value for unknown.
4. **`formatSeverityLabel`** — accept `AllergySeverity`, return `"Mild" | "Moderate" | "Severe"`. Same pattern.
5. **`formatAlertType`** — accept `AlertType` (`"POLLEN" | "AIR_QUALITY" | "WEATHER" | "GENERAL"`). Return lowercase ("pollen", "air quality", "weather", "general"). This is a **new enum we need to expose** — see step F1.1.

**F1.1 — Add `AlertType` to `frontend/src/api/types.ts`.** The contract's `AlertType` enum (`POLLEN`, `AIR_QUALITY`, `WEATHER`, `GENERAL`) is internal-only. The client receives `AlertResponse.alert_type` as `string` today. To get TS-checked formatters without `as never` casts, add:

```ts
export type AlertType = "POLLEN" | "AIR_QUALITY" | "WEATHER" | "GENERAL";

export interface AlertResponse {
  // ...existing fields...
  alert_type: AlertType;  // was: string
}
```

This is a typed tightening, not a wire change — the backend already returns these four values. If a future server-side value slips in, the `alert_type` `string` constraint catches it at build time instead of breaking the UI at runtime.

**Add 6 new tests** to `frontend/src/utils/format.test.ts` covering each new formatter + null/unknown fallback. TDD order: write tests, run `pnpm test src/utils/format.test.ts` to see them fail, implement, run again to see green.

**Verification commands:**

```bash
cd frontend
pnpm test -- src/utils/format.test.ts
pnpm tsc --noEmit -p tsconfig.app.json
```

**Expected:** tests pass, tsc clean. Commit: `feat(frontend): add alert/allergy label formatters`.

---

### F2 — Add icons used by the new Profile and the redesigned Today

Add three icons to `frontend/src/components/icons.tsx`. Keep the same hand-rolled inline pattern (no icon package).

1. `UserIcon` — for Profile nav and profile form header.
2. `PinIcon` — for "Location" form field.
3. `PlusIcon` — for "Add allergy" CTA.
4. `TrashIcon` — for "Remove allergy" button.
5. `LeafBigIcon` — bigger version of `LeafIcon` for the Today hero card.
6. `CheckIcon` — for selected allergy chips.

All six follow the existing 24-line `viewBox`, `currentColor`, `strokeWidth="2"`, `strokeLinecap="round"`, `strokeLinejoin="round"` pattern. Lift stroke `d=""` paths from prototype.html where they already exist (the prototype uses the same paths), or from Lucide/Feather (which is the visual source for the prototype's icons).

**No tests for icons** — they're pure JSX with no logic.

**Verification commands:**

```bash
cd frontend
pnpm tsc --noEmit -p tsconfig.app.json
pnpm lint
```

**Expected:** both clean. Commit: `feat(frontend): add icons for profile and redesigned today`.

---

### F3 — Add CSS for the Today hero card and the Profile form

Extend `frontend/src/styles/theme.css`. **Append** at the bottom; do not reformat existing sections.

Add:

- `.hero` block — lifted from prototype (lines 167–186), but using CSS variables already in the token set (`var(--high)`, `var(--moderate)`, `var(--brand)`, etc.). Use `linear-gradient(150deg, var(--high), var(--moderate))` for the hero. Eyebrow, word, where, score styles.
- `.metrics` + `.metric` blocks — same as prototype (lines 178–183). Reused for Pollen + Air/Weather grids on Today.
- `.note` block — already present? Verify with `grep -c "\\.note" frontend/src/styles/theme.css`. The Today page already uses `<div className="note">`, so the rule exists. If it doesn't, add it from the prototype.
- `.field` block — for the Profile form input rows. Lifted from a minimal style that pairs with the existing auth form. Don't copy the prototype's `auth-form` styles verbatim; align with `LoginPage` / `RegisterPage` patterns already in `theme.css`.
- `.chip-row` — for the "select allergens" picker on the Profile page. Matches the visual rhythm of `BottomNav`'s nav links.

**Hard rules (per `CONVENTIONS.md`):** every color, radius, and font comes from a CSS variable in `:root`. **No** `#fff`, `#2f7d57`, etc. inline. **No** hardcoded thresholds in styles (the rule already exists from the prototype).

**Verification:** no JS change, only CSS. Test: `pnpm build`. Visual smoke check is manual (browser, dev server). Commit: `feat(frontend): add styles for today hero and profile form`.

---

### Vertical A — Today redesign (prototype parity + improvements)

The current `TodayPage` shows a flat risk chip + metric list. The prototype shows a hero card with a colored gradient background, a giant risk word ("High"), a "where" line, the numeric score, a 3-up pollen grid (Tree/Grass/Weed with colored level), and a 6-up air/weather grid (PM2.5, PM10, Wind, Temp, Humidity, UV — note UV is **not** in the contract, so we drop it).

### A1 — Write the failing tests for the redesigned Today (TDD red)

Open `frontend/src/routes/TodayPage.test.tsx`. Keep all 8 existing tests — they assert behavior that must not regress. Add 6 new tests inside a new `describe("TodayPage — hero card")`:

```ts
it("renders the hero card with the risk word and location", async () => { ... });
it("renders the score chip with the points in the top-right of the hero", async () => { ... });
it("renders the three pollen cards in the Pollen section", async () => { ... });
it("renders five air/weather metrics in the Air & Weather section", async () => { ... });
it("renders the personalized note when pollen is HIGH and the user has a tree allergy", async () => { ... });
it("does NOT render a personalized note when the user has no allergies", async () => { ... });
```

For the "personalized note" test you need a way for the test to know whether the user has a tree allergy. **Today `getCurrentUser()` returns `UserResponse`**, which has no `allergies` field. Two options:

- (a) Make the test mock `listAllergies` and assert the Today page calls it once on mount. If the user has any tree-pollen allergy of `MODERATE` or `SEVERE`, render the note. If the user has no allergies, do not render it.
- (b) Skip the personalization test and add a `docs/headache/` note that user allergies are not on `UserResponse`.

Choose (a). This is a small feature add (Today fetching the user's allergies to decide whether to render a personalized note) and the test guards it. See A3.

Run the new tests:

```bash
cd frontend
pnpm test -- src/routes/TodayPage.test.tsx
```

**Expected:** the 6 new tests fail. Existing 8 still pass.

### A2 — Refactor `TodayPage` to render the hero card

Replace the body of `TodayPage` in `frontend/src/routes/TodayPage.tsx` so that, given the existing state (`env`, `hospitals`, `loaded`, etc.), it renders:

1. Hero card (CSS class `hero`): gradient background from `riskClass(env.risk)`. Eyebrow: "Overall allergy risk". Word: `formatRisk(env.risk)` in a `<b>`. Where: `env.latitude, env.longitude` formatted as e.g. `"37.5665°N, 126.9780°E"` — write a tiny helper `formatCoords(lat, lon)` in `format.ts` with one test. Score chip: top-right, `<b>{points}</b><span>risk pts</span>`.
2. `<div className="sectlbl">Pollen</div>` followed by a 3-column metrics grid: Tree / Grass / Weed. Each cell shows the level ("High" / "Moderate" / "Low" / "—") with the level color via `className={"lv " + (env.pollen.tree ?? "")}`. Use `formatPollen`.
3. `<div className="sectlbl">Air & weather</div>` followed by a 3-column grid with PM2.5, PM10, Wind, Temp, Humidity. Five metrics, 3 columns = two rows of 3 (last cell empty or skipped — match the prototype's `repeat(3, 1fr)`). Use `formatTemperature` for temp. PM2.5/PM10 values come from `env.air_quality` as raw numbers (no formatter — `formatDistance` doesn't fit).
5. Personalized note block (already-existing `.note`): "Tree pollen is high and you're allergic to it. Consider limiting long outdoor spells this afternoon and keeping windows shut." Rendered only if `pollen.tree === "HIGH"` **and** the user has at least one allergy whose `allergen === "TREE_POLLEN"` with `severity !== "MILD"`. The severity threshold avoids spamming users who mark tree pollen as a mild annoyance.
6. The sample-data note stays exactly as it is today (it's the right behavior).
7. The hospital section is unchanged (no regression).

**Guard rails:**
- All `setState` patterns inside `useEffect` are out. Use `useTransition` if you need a pending flag, or derive `loaded = !(env === null && envError === null)` directly. The current `oxlint-disable-next-line react/set-state-in-effect` comment in `TodayPage.tsx` (line 42–43) **must be removed** as part of this task — the new code does not need it. Do not add new disable comments.
- The new `useEffect` is allowed to call `Promise.allSettled` and dispatch into state inside the `.then` callback (async, not synchronous) — that's allowed by the rule.
- Every `RiskLevel` value rendered in a className flows through `riskClass()` (already a pure function).
- No hardcoded thresholds in the JSX (e.g. `env.pollen.tree === "HIGH"` is fine — it's reading the value the contract already returns, not defining the threshold).

Run:

```bash
cd frontend
pnpm test -- src/routes/TodayPage.test.tsx
pnpm tsc --noEmit -p tsconfig.app.json
pnpm lint
pnpm build
```

**Expected:** all 14 Today tests green (8 existing + 6 new), tsc clean, oxlint clean, vite build green. Commit: `feat(frontend): redesign today screen to match prototype (hero, sections, personalized note)`.

### A3 — If the personalized-note path needs `listAllergies`, wire it up

If you adopted A1 option (a) above, `TodayPage` now needs to fetch the user's allergies. Add to `TodayPage.tsx` a parallel `Promise.allSettled` branch that calls `listAllergies()`, and only after both `env` and allergies have settled does it render the personalized note. The state shape gains an `allergies: AllergyResponse[] | null` and an `allergiesError: string | null`. The fetch is **bearer-required**, so it runs only when `status === "authenticated"` — same gate as `hasLocation`.

Update `TodayPage.test.tsx` mock setup so `listAllergies` is also mocked (the existing `client.test.ts` already tests the real function; the page test mocks the module).

Commit (separate from A2): `feat(frontend): today page reads user allergies for personalized note`.

---

### Vertical B — Profile screen (new)

A new route `/profile` reachable from a settings gear in the `TopHeader`. Three sections — Location, Allergies, Notification preferences. Each section is its own presentational component and its own `useEffect` data fetch. Pure form state, real validation, no new dependencies.

### B1 — Add the route to `App.tsx`

Edit `frontend/src/App.tsx`:

- Add `<Route path="/profile" element={<ProfilePage />} />` inside the `<RequireAuth>` block.
- The auth-gated block currently has `/chat`, `/today`, `/alerts`. `/profile` joins them.

**Test:** add a smoke test `frontend/src/routes/ProfilePage.test.tsx` that asserts the route renders. One test, sufficient at the gate level (full coverage in B5).

Commit: `feat(frontend): register /profile route`.

### B2 — Profile page skeleton + Location section

Create `frontend/src/routes/ProfilePage.tsx`. Start with the skeleton — a heading, three empty section wrappers, and a real Location form:

- Email (read-only display)
- Latitude input (number, range -90..90, validation error if out of range)
- Longitude input (number, range -180..180, validation error if out of range)
- "Use my current location" button — calls `navigator.geolocation.getCurrentPosition` with a 3-second timeout, exactly like `RegisterPage.tsx` already does. Lift this into a small helper `useDeviceLocation` in `frontend/src/utils/useDeviceLocation.ts` so both pages share it.

State:
- `formEmail: string` (initialized from `useAuth().user.email`)
- `formLat: number | ""` (initialized from `user.latitude`)
- `formLon: number | ""` (initialized from `user.longitude`)
- `submitting: boolean`
- `error: string | null`
- `saved: boolean` (transient flag for the "Saved" toast — auto-clears after 1.5s)

On submit: validate ranges locally, call `updateCurrentUser({ latitude: formLat, longitude: formLon })`, update `useAuth().user` via a new context method `updateUser(user: UserResponse)` that you add to `AuthContext`. The new method is `setUser(updatedUser)` wrapped in `useCallback`. See B2.1.

**B2.1 — Extend `AuthContext`.** Add `updateUser` to the context value, exposed by a `useCallback` setter:

```ts
const updateUser = useCallback((updated: UserResponse) => {
  setUser(updated);
}, []);
```

No new deps. The `AuthContext` value interface gets a new field. Update `frontend/src/auth/AuthContext.tsx` only — no other call site changes for this plan (only `ProfilePage` will use it).

Commit: `feat(frontend): profile page skeleton + location section + auth updateUser`.

### B3 — Profile: Allergies section (CRUD)

Below the Location section, render:

- A list of the user's existing allergies as `<li>` rows: allergen label, severity label, a "Remove" button that calls `deleteAllergy(id)` and removes the row from local state on success.
- A "Add allergy" form below the list:
  - Two `<select>` dropdowns: Allergen (8 values from `Allergen`) and Severity (3 values).
  - A "Add" button that calls `createAllergy({ allergen, severity })` and prepends the new row to local state on success.
  - Disable the submit button while `submitting` is true.

State additions:
- `allergies: AllergyResponse[] | null`
- `addAllergen: Allergen | ""`
- `addSeverity: AllergySeverity | ""`
- `addingAllergy: boolean`

Refresh logic: the section's `useEffect` calls `listAllergies()` on mount. After `createAllergy` succeeds, the returned `AllergyResponse` is prepended (don't refetch — the response is authoritative). After `deleteAllergy(id)` succeeds, the local array is filtered.

**Important — bear in mind the lane rule:** this screen reads allergies via `listAllergies()`, which the contract exposes. It does not write `backend/app/services/triage.py`. It does not edit `backend/app/agents/`. We're within scope.

Commit: `feat(frontend): profile page allergies CRUD`.

### B4 — Profile: Notification preferences section

Below Allergies, render the user's notification preferences:

- Four toggles: `alert_pollen`, `alert_air_quality`, `alert_weather`, all boolean checkboxes.
- One `<select>` for `min_risk_level` (LOW / MODERATE / HIGH / EMERGENCY).
- Two number inputs: `quiet_hours_start` (0–23) and `quiet_hours_end` (0–23). The contract allows `null` for "no quiet hours"; if both fields are blank, send `null` in the PUT body.

On submit: build a `PreferenceUpdateRequest` with only the changed fields (compare against the loaded `PreferenceResponse`), PUT it, update local state with the returned `PreferenceResponse`.

**Why PUT-only-changed:** matches the existing `updateCurrentUser` pattern (the `UserUpdateRequest` type already has every field optional). Avoids round-tripping the full object.

### B5 — Tests for the Profile page

Create `frontend/src/routes/ProfilePage.test.tsx`. The test mocks `useAuth`, `listAllergies`, `createAllergy`, `deleteAllergy`, `readPreferences`, `updatePreferences`, `updateCurrentUser` exactly the way `TodayPage.test.tsx` mocks `useAuth` and `getCurrentEnvironment`. Test cases:

1. Renders the three section headings.
2. Renders the user's email as read-only.
3. Submits Location with valid lat/lon → calls `updateCurrentUser` with `{ latitude, longitude }`.
4. Rejects out-of-range latitude with a visible error and does not call the API.
5. Loads the user's allergies on mount.
6. Adds an allergy: selecting values + clicking Add → calls `createAllergy({ allergen, severity })` and prepends the new row.
7. Removes an allergy: clicking Remove → calls `deleteAllergy(id)` and removes the row from local state.
8. Loads preferences on mount and shows the current values.
9. Saves preferences with only the changed field (`min_risk_level`) — asserts the PUT body contains only `min_risk_level`.

Run `pnpm test -- src/routes/ProfilePage.test.tsx`. Fix anything red. TDD order: write all 9 tests first, run, expect 9 failures, implement, expect 9 passes.

Commit: `feat(frontend): profile page notification preferences + tests`.

### B6 — Add a Profile entry point to `TopHeader`

Edit `frontend/src/components/TopHeader.tsx`. Add a small "Profile" gear button to the right of the theme button, next to the `<span className="spacer">`. On click, `navigate("/profile")`. Use the new `UserIcon` from F2.

Update `frontend/src/components/icons.tsx` if not done. Verify `pnpm build` and `pnpm test` stay green.

Commit: `feat(frontend): top header links to /profile`.

---

### Vertical C — Alerts redesign (prototype parity)

The current `AlertsPage` is close to the prototype already. Improvements:

- Add a type-colored icon column on the left of each row (POLLEN → leaf icon, AIR_QUALITY → wind/air icon, WEATHER → cloud icon, GENERAL → bell icon). Use existing prototype SVGs; no new package.
- Show the alert body text larger and bolder; the timestamp smaller below.
- The unread dot stays. The row click behavior (mark-as-read) stays.
- Drop the "Unread only" filter toggle into a more obvious position (top-right of the section header, not floating).
- Render an empty state with a friendlier copy ("No alerts yet. We will notify you when the environment crosses your threshold.") — already there.

### C1 — Tests for the redesigned Alerts (TDD red)

Add to `frontend/src/routes/AlertsPage.test.tsx`:

```ts
it("renders a type-colored icon for POLLEN alerts", async () => { ... });
it("renders a type-colored icon for AIR_QUALITY alerts", async () => { ... });
it("renders the alert message larger and the timestamp smaller", async () => { ... });
```

Three new tests. The other 9 stay green.

### C2 — Implement the redesign

Edit `frontend/src/routes/AlertsPage.tsx`. Use `formatAlertType` for the type label. Render the icon column with the right SVG for each alert type. Keep the click-to-mark-read behavior; keep the keyboard support; keep the "filter refetches" behavior.

Verify:

```bash
cd frontend
pnpm test -- src/routes/AlertsPage.test.tsx
pnpm tsc --noEmit -p tsconfig.app.json
pnpm lint
pnpm build
```

Commit: `feat(frontend): redesign alerts screen with type-colored icons`.

---

## Tests / validation

The full test suite must pass at the end:

```bash
cd frontend
pnpm test
```

**Expected:** all tests pass. Specific counts:

- `format.test.ts`: existing 8 + 6 new = 14
- `client.test.ts`: existing 8 (unchanged)
- `TodayPage.test.tsx`: existing 8 + 6 new = 14
- `AlertsPage.test.tsx`: existing 9 + 3 new = 12
- `ProfilePage.test.tsx`: new, 9 tests
- `smoke.test.ts`: 1 (unchanged)

Total: ~58 tests. Every commit above leaves this count non-decreasing.

The full gate must pass before opening the PR:

```bash
cd frontend
pnpm install --frozen-lockfile
pnpm lint
pnpm build
pnpm test
```

All four exit `0`. Backend gate (`cd backend && uv run ruff check . && uv run ruff format --check . && uv run pytest`) is unchanged by this plan — the backend files in `git status` (`backend/.env.example`, `backend/app/agents/symptom_agent.py`, `backend/app/api/chat.py`, `backend/app/core/config.py`) belong to other work and are out of scope.

## Risks, tradeoffs, and open questions

1. **`AlertType` is internal-only in the contract.** F1.1 adds it to the FE `types.ts`. If the backend ever returns a new alert type the FE doesn't know about, the FE will fail to compile. That's the right tradeoff for a typed client — better to fail at build than render `POLLEN_FOO` raw. Mitigation: the contract should grow this enum publicly. Out of scope here; flag in the final commit body and open a follow-up ADR.

2. **`listAllergies()` is bearer-required.** Today fetches allergies for the personalized note only when the user is authenticated. The conditional render keeps unauthenticated users (who can't see `/today` anyway, because of `RequireAuth`) from hitting a 401. The mocked tests cover this path; the live integration is exercised when the user logs in.

3. **The personalized note thresholds are hardcoded in the JSX** (`pollen.tree === "HIGH"` and `severity !== "MILD"`). This is **not** the kind of hardcoding `CONVENTIONS.md` forbids — those rules ban hardcoding **configurable thresholds** (e.g. "alert when PM2.5 > 35"). The HIGH level is a domain enum value, not a threshold. If you want this to be configurable, it's a backend-side concern and belongs in `services/risk.py`, not the FE.

4. **`useDeviceLocation` extraction.** The current `RegisterPage.tsx` has its own `navigator.geolocation` block. Lifting it into a hook is a small refactor of an existing file. If you want to keep this PR small, skip the lift and duplicate the block in `ProfilePage`. Recommendation: do the lift — DRY, and the existing test surface for `RegisterPage` won't change because the behavior is identical.

5. **`AuthContext.updateUser`.** Adding a method to the context is a small API change. Only `ProfilePage` calls it. No other call site needs updating.

6. **The contract drift on alerts/preferences.** `docs/API_CONTRACT.md` documents 12 endpoints; the FE uses 15. This plan does not fix the drift — it just adds UI for endpoints that already work. The follow-up is a docs PR adding `/api/alerts`, `/api/alerts/{id}/read`, `/api/notifications/preferences` GET and PUT. Flag in the final commit body. Do not silently fix the doc in this PR — `AGENTS.md` rule 5: "Follow the spec, or change the spec first."

7. **The prototype's chat script** (`prototype.html` lines 323–560) is the visual model for what Jack's real chat screen will look like. This plan does not touch Jack's lane. The fact that `ChatPlaceholderPage` is the only `/chat` route and the prototype has a fully designed chat flow is a known gap — it belongs in TASKS.md J5, not here.

8. **Commit count.** This plan produces ~12 commits. Smaller is fine; lumping adjacent F1 + F1.1 into one commit is OK. Lumping F3 + A2 is **not** OK — keep CSS separate so a CSS-only regression is bisectable.

9. **PR title suggestion:** `feat(frontend): redesign today and alerts, add profile screen (Today v2, Alerts v2, Profile v1)`. Open against `origin/main` after rebase: `git fetch origin && git rebase origin/main`.

10. **Lane rule check.** This plan touches only `frontend/` files and one small `AuthContext` addition. It does not touch `backend/app/services/triage.py`, `backend/app/agents/`, `backend/app/main.py`, or `backend/pyproject.toml`. It does not touch `frontend/src/chat/`. Lane rule preserved.

11. **PWA / offline.** `vite.config.ts` already denies `/api/*` from precache. The Profile form is online-only (it mutates), which is correct. No PWA changes needed.

12. **`oxlint-disable react/set-state-in-effect`.** Today's `TodayPage.tsx` has two disable comments (lines 42–43 and the equivalent in `AlertsPage.tsx`). A2 removes the Today one. C2 must also remove the Alerts one if you refactor the Alerts useEffect (only do so if the rewrite naturally removes it; don't disable a new site).