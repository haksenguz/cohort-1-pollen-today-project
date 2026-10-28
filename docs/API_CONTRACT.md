# API Contract

Derived from the running code, not from the spec prose. Source of truth for
each endpoint is `backend/app/api/*.py` plus the Pydantic/SQLModel classes it
references. If this document and the code disagree, the code wins and this
document is stale. File a fix.

Base path in dev: `http://localhost:8000`. All bodies are JSON.

## Ownership boundary

Per [ADR 0001](adr/0001-llm-does-not-decide-safety.md): the LLM in
`app/agents/symptom_agent.py` does conversation and structured extraction
only. It never decides urgency. `POST /api/chat` and `POST /api/triage` both
end up calling the deterministic engine in `backend/app/services/triage.py`,
and that engine is the only place a `LOW` / `MODERATE` / `EMERGENCY` verdict
is produced. A `triage_level` in a chat response traces back to a
`triage.assess()` call, never to a model completion. If you're building a
client, treat any triage value that didn't come through this engine as a bug.

## Auth

Bearer JWT, issued by `/api/auth/register` or `/api/auth/login` as
`access_token`. Send it as `Authorization: Bearer <token>`. Tokens expire in
24h (`ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24`, HS256, signed with
`JWT_SECRET`). A missing or invalid token on a protected route returns `401`
with `{"detail": "Could not validate credentials"}`.

| Endpoint | Auth |
| --- | --- |
| `GET /health` | Public |
| `POST /api/auth/register` | Public |
| `POST /api/auth/login` | Public |
| `GET /api/users/me` | **Bearer required** |
| `PUT /api/users/me` | **Bearer required** |
| `GET /api/allergies` | **Bearer required** |
| `POST /api/allergies` | **Bearer required** |
| `DELETE /api/allergies/{allergy_id}` | **Bearer required** |
| `GET /api/environment/current` | Public |
| `POST /api/triage` | **Bearer required** |
| `POST /api/chat` | Bearer token |
| `GET /api/hospitals/nearby` | Public |
| `GET /api/alerts` | **Bearer required** |
| `PATCH /api/alerts/{alert_id}/read` | **Bearer required** |
| `GET /api/notifications/preferences` | **Bearer required** |
| `PUT /api/notifications/preferences` | **Bearer required** |

Plus two dev-only routes mounted by `dev_settings.router` that **404 on every
request** unless `DEV_SETTINGS_ENABLED` is true in a gitignored local `.env`:
`GET /api/dev/llm` and `PUT /api/dev/llm`.

**`POST /api/chat` takes its identity from the token.** `ChatRequest.user_id`
is gone. The route depends on `CurrentUser`, and the conversation is looked up
before the stream opens, so a `conversation_id` belonging to another user is
rejected with `404` rather than `403` — the endpoint never confirms that
someone else's conversation exists.

**`POST /api/chat` is rate limited.** Every turn is a real model call, so the
endpoint is bounded per user: a sliding window of
`CHAT_RATE_LIMIT_PER_MINUTE` (default 20, `0` disables). Over the limit the
response is a `429` with a `Retry-After` header and a detail string saying how
long to wait. It is raised *before* the stream opens, so it is a real status
code — a refusal emitted inside the generator would arrive after the `200` and
its headers were already sent. Every response carries `X-RateLimit-Limit` and
`X-RateLimit-Remaining`. The window is per process and held in memory: N
workers would each allow the full limit, and a restart clears it.

---

## `GET /health`

Liveness check. No auth, no params.

**200**: `Health`

```json
{ "status": "ok", "service": "allergy-ai-backend" }
```

---

## `POST /api/auth/register`

**Auth:** none. **Body:** `RegisterRequest`

| field | type | notes |
| --- | --- | --- |
| `email` | `EmailStr` | required |
| `password` | `str` | 8–72 chars |
| `latitude` | `float \| null` | optional, -90..90 |
| `longitude` | `float \| null` | optional, -180..180 |

```json
{ "email": "a@example.com", "password": "at-least-8-chars", "latitude": 37.5665, "longitude": 126.9780 }
```

**201**: `TokenResponse`

```json
{ "access_token": "eyJhbGciOi...", "token_type": "bearer" }
```

**409** if the email is already registered: `{"detail": "Email is already registered"}`.

---

## `POST /api/auth/login`

**Auth:** none. **Body:** `LoginRequest`: `email: EmailStr`, `password: str`.

```json
{ "email": "a@example.com", "password": "at-least-8-chars" }
```

**200**: `TokenResponse` (same shape as register).
**401** on bad credentials: `{"detail": "Invalid email or password"}`.

---

## `GET /api/users/me`

**Auth:** Bearer required. No params.

**200**: `UserResponse`

```json
{
  "id": 1,
  "email": "a@example.com",
  "latitude": 37.5665,
  "longitude": 126.978,
  "created_at": "2026-09-01T09:00:00Z",
  "updated_at": "2026-09-01T09:00:00Z"
}
```

**401** if the token is missing/invalid.

---

## `PUT /api/users/me`

**Auth:** Bearer required. **Body:** `UserUpdateRequest`. Every field is optional;
only a supplied field changes.

| field | type | notes |
| --- | --- | --- |
| `email` | `EmailStr \| null` | |
| `password` | `str \| null` | 8–72 chars, rehashed |
| `latitude` | `float \| null` | -90..90 |
| `longitude` | `float \| null` | -180..180 |

**An explicit `null` clears the field; omitting the field leaves it alone.**
The two are different and only the distinction makes the endpoint usable:
`{"latitude": null, "longitude": null}` removes a saved location, while
`{"email": "..."}` does not touch it. A saved location you cannot clear is a
location you cannot correct, and the chat's `no_location` card tells people to
go and fix theirs.

```json
{ "latitude": 37.5, "longitude": 127.0 }
```

**200**: `UserResponse` (same shape as `GET /api/users/me`).
**409** if the new email is already taken by another user.

---

## `/api/privacy/*`

Personal-data rights under 개인정보 보호법. All three are behind the same bearer
token the user already has: **제38조④** requires that asking for access or
deletion be no harder than signing up was, and sign-up is one form. No email
round-trip, no support ticket.

| endpoint | law | what it does |
| --- | --- | --- |
| `GET /api/privacy/summary` | 제4조1, 제30조 | what is held, and what is never collected |
| `GET /api/privacy/export` | 제4조3, 제35조 | a complete copy, as a file download |
| `DELETE /api/privacy/account` | 제36조 | hard delete of the account and all its rows |
| `GET /api/privacy/health-note` | 제23조 | states that symptom data is 민감정보 |

**`GET /api/privacy/export`** → `application/json`, with
`Content-Disposition: attachment; filename="my-data-<stamp>.json"` and
`Cache-Control: no-store`.

**`password_hash` is never included**, anywhere, in any shape. An export that
carries it is a credential-disclosure bug wearing a privacy feature's clothes.

The document is nested rather than flat — messages sit inside their
conversation, the triage verdict inside its symptom event, clinic results
inside their search — because the point of an export is that a person can read
it and recognise it. A flat dump of eleven tables is not checkable. Each
section carries a `counts` block alongside it.

```json
{
  "format": "allergy-ai/personal-data/v1",
  "account": { "email": "...", "latitude": 37.5, "longitude": 127.0 },
  "conversations": [ { "id": 1, "title": "...", "messages": [ { "role": "USER", "content": "..." } ] } ],
  "symptom_events": [ { "symptoms": ["itchy eyes"], "triage_result": { "risk_level": "LOW" } } ],
  "hospital_searches": [ { "latitude": 37.5, "results": [ { "name": "..." } ] } ],
  "counts": { "conversations": 1, "messages": 4, "triage_results": 1 }
}
```

**`DELETE /api/privacy/account`** → 200 with a receipt of rows removed per
table:

```json
{ "deleted": { "account": 1, "messages": 4, "triage_results": 1, "conversations": 1 },
  "note": "Permanently deleted. This cannot be undone and there is no recovery period." }
```

Deletion is a **hard delete**, in one commit, children first. `messages`,
`triage_results` and `hospital_results` carry no `user_id` of their own, so a
delete written table-by-table on `user_id` leaves them behind as orphans
pointing at a user that no longer exists. There is no soft-delete column and no
tombstone row, because **제36조③** requires that deletion leave nothing that
can be recovered or regenerated. A half-deleted account is worse than a failed
delete: the user believes their data is gone and it is not.

`environment_snapshots` is deliberately **not** deleted. It has no `user_id`
and holds observed pollen and air quality for a *location*, not a person — it
is shared cache, and removing it on one account's exit would destroy data
other accounts still read.

---

## `GET /api/allergies`

**Auth:** Bearer required. Lists the caller's own allergies. No params.

**200**: `list[AllergyResponse]`

```json
[
  { "id": 3, "allergen": "TREE_POLLEN", "severity": "MODERATE", "created_at": "2026-09-01T09:00:00Z" }
]
```

---

## `POST /api/allergies`

**Auth:** Bearer required. **Body:** `AllergyCreateRequest`

| field | type | allowed values |
| --- | --- | --- |
| `allergen` | `Allergen` enum | see [Enums](#enums) |
| `severity` | `AllergySeverity` enum | see [Enums](#enums) |

```json
{ "allergen": "GRASS_POLLEN", "severity": "SEVERE" }
```

**201**: `AllergyResponse` (same shape as the list item above), scoped to
`current_user.id` from the token.

---

## `DELETE /api/allergies/{allergy_id}`

**Auth:** Bearer required. Path param `allergy_id: int`.

**204**: no body, on success.
**404**: `{"detail": "Allergy not found"}` if the id doesn't exist or belongs
to a different user (the check is `allergy.user_id != current_user.id`, so
this also hides other users' rows rather than a separate 403).

---

## `GET /api/environment/current`

**Auth:** none. **Query params:** `lat: float` (-90..90, required), `lon: float`
(-180..180, required).

`GET /api/environment/current?lat=37.5665&lon=126.9780`

**200**: `EnvironmentResponse`, always 200. Weather, air quality, and pollen
are fetched concurrently and each degrades independently. See
[Degradation contracts](#degradation-contracts).

```json
{
  "latitude": 37.5665,
  "longitude": 126.978,
  "pollen": { "tree": "HIGH", "grass": "MODERATE", "weed": "LOW" },
  "air_quality": { "pm25": 12.4, "pm10": 20.1 },
  "weather": { "temperature": 24.5, "humidity": 61.0, "wind": 3.2 },
  "points": 7,
  "risk": "MODERATE",
  "pollen_is_sample": true
}
```

---

## `POST /api/triage`

**Auth:** `Authorization: Bearer <token>`, required. **Body:** `TriageRequest`

| field | type | notes |
| --- | --- | --- |
| `symptoms` | `list[str]` | default `[]`, free-text tokens (e.g. `"throat_swelling"`) |
| `severity` | `int \| null` | 0–10 |
| `breathing_difficulty` | `bool` | default `false` |
| `airway_swelling` | `bool` | default `false` |

```json
{ "symptoms": ["sneezing", "itchy_eyes"], "severity": 4, "breathing_difficulty": false, "airway_swelling": false }
```

Auth became required in Phase 4 (triage persistence). `symptom_events.user_id`
is a `NOT NULL` foreign key, so a submission now needs an identity to attach
to — the endpoint was public only while nothing was written to the database.
`401` on a missing/invalid token, same shape as every other protected route.

**200**: `TriageResponse`, always produced by `triage.assess()`.

```json
{
  "level": "LOW",
  "recommendation": "Symptoms look mild. Consider an antihistamine and monitor.",
  "reasons": [],
  "rule_version": "triage-2026-09-07",
  "symptom_event_id": 12,
  "triage_result_id": 9
}
```

`level` is a `TriageLevel` (`LOW | MODERATE | EMERGENCY`). Any red-flag
symptom or either boolean flag forces `EMERGENCY` and short-circuits
everything else (see `triage.py`'s `EMERGENCY_SYMPTOMS`) — the verdict on the
wire is always the same enum value the deterministic engine returned, never
inferred or reconstructed. Every call persists a `symptom_events` row (the
submitted symptoms) and a linked `triage_results` row (the verdict);
`symptom_event_id`/`triage_result_id` are those rows' ids, so a client or
auditor can trace a response back to what was stored.

---

## `POST /api/chat`

**Auth:** `Authorization: Bearer <token>`, required. **Body:** `ChatRequest`

| field | type | notes |
| --- | --- | --- |
| `message` | `str` | 1–2000 chars. Optional when `regenerate` is true, and ignored then. |
| `conversation_id` | `int \| null` | omit to start a new conversation. Required when `regenerate` is true. |
| `regenerate` | `bool` | default `false`. Re-ask the last user turn and replace the last assistant message in place. |

A `user_id` in the body is ignored. The user is the token holder.

**Status codes:** `401` without a valid token. `404` when `conversation_id`
does not exist or belongs to someone else. `422` when neither `message` nor
`regenerate` is given, and when `regenerate` is true without a
`conversation_id`. `409` when the conversation has no user turn to regenerate.

```json
{ "message": "I've had itchy eyes and sneezing since this morning", "conversation_id": null }
```

### Response: this is Server-Sent Events, not a plain JSON body

`chat()` returns `StreamingResponse(..., media_type="text/event-stream")`.
Read `backend/app/api/chat.py` for the exact generator (`_run_chat`). The reply
arrives as `message` events carrying one piece each, in order, so a client
appends them as they arrive. The pieces concatenate to exactly the `message`
field of the `done` event.

### `status` events (added 2026-10-14)

A turn is two sequential model calls plus the rule engine — several seconds.
The stream therefore emits one or more `status` events first, each naming the
part of the turn currently running:

```
event: status
data: {"stage": "starting"}

event: status
data: {"stage": "extracting"}
...
```

Stages: `starting`, `extracting`, `asking`, `assessing`, `saving`. Which ones
appear depends on the branch the graph takes — a first turn that asks the
safety question goes `starting → extracting → saving` and never reaches
`asking`, because that turn makes no question-calling model call.

**These are pipeline stages, not tool calls.** The agent has no tools and does
no function-calling; `LLMClient` is a single `complete(messages) -> str`. A
client must not render a `status` event as "using tool X". In particular
`assessing` is the deterministic engine in `app/services/triage.py` reaching a
verdict, never the model (ADR 0001) — a UI that labels it as model reasoning
would misstate where the safety decision comes from.

After the status events come exactly one of these two sequences, then the
stream closes:

**Normal turn**: one or more `message` events, then one `done` event:

```
event: message
data: {"delta": "Are you having any difficulty breathing, or swelling of your lips, tongue, or throat?"}

event: done
data: {"message": "Are you having any...", "conversation_id": 42, "symptoms": ["sneezing", "itchy_eyes"], "severity": 4, "duration": "this morning", "possible_trigger": null, "breathing_difficulty": null, "airway_swelling": null, "triage_level": null, "triage_reasons": [], "triage_rule_version": null}

```

`message.delta` carries one piece of the assistant reply, and the pieces arrive
as the model produces them. A client appends them in order. When the provider
cannot stream, the whole reply is sent as several `message` events instead, and
the concatenation still matches the `done` event's `message` field exactly. The
`done` event's `data` is the complete
`ChatResponse` (field names and types below), including whatever the
extraction filled in so far. `triage_level`/`triage_reasons`/
`triage_rule_version` stay `null`/`[]` until the agent's `triage_node` has
actually run `triage.assess()`, usually once `breathing_difficulty` or
`airway_swelling` is confirmed, or `MAX_QUESTIONS` (4) is reached.

**Agent failure**: one `error` event only, then the stream ends (nothing is
persisted for that turn):

```
event: error
data: {"detail": "the symptom agent failed to process this message"}

```

`ChatResponse` fields:

| field | type |
| --- | --- |
| `message` | `str` |
| `conversation_id` | `int` |
| `symptoms` | `list[str]` |
| `severity` | `int \| null` |
| `duration` | `str \| null` |
| `possible_trigger` | `str \| null` |
| `breathing_difficulty` | `bool \| null` |
| `airway_swelling` | `bool \| null` |
| `triage_level` | `str \| null` (a `TriageLevel` value when set) |
| `triage_reasons` | `list[str]` |
| `triage_rule_version` | `str \| null` |
| `tool_calls` | `list[ToolCallEvent] \| null` — **omitted entirely when no tool ran**, never `[]`. Absence and an empty array are different states. |

### `tool` events (added 2026-10-18)

A tool call is announced when the model chooses it and settled when it returns.
`status` is `running` | `done` | `error`. `id` pairs a `running` with its
terminal event.

| field | on | notes |
| --- | --- | --- |
| `id` | all | pairs the `running` with its `done`/`error` |
| `name` | all | internal identifier — never render it |
| `status` | all | |
| `args` | `running` only | what the model asked for; noise once settled |
| `summary` | settled | one plain-English line, never an exception, never JSON |
| `result` | `done` only | the rows, for a tool with an agreed result key |
| `code` | settled | why there is no result; see below |

```
event: tool
data: {"id":"call_1","name":"find_nearby_hospitals","status":"running","args":{"speciality":"ALLERGY"}}

event: tool
data: {"id":"call_1","name":"find_nearby_hospitals","status":"done","summary":"Found 5 results.",
       "result":{"clinics":[{"name":"...","address":"...","distance_m":129,"phone":null,"rank":1}],
                 "provider_available":true}}

event: tool
data: {"id":"call_2","name":"find_nearby_hospitals","status":"error","code":"no_location",
       "summary":"We need your location first. Your profile has no location saved, so we could not
                  search. This does not mean there are no clinics around you."}
```

**`code`** is what stops three different failures collapsing into one flat
"something went wrong":

| code | means | client |
| --- | --- | --- |
| `no_location` | the caller's profile has no coordinates | "We need your location first", with a button to Settings |
| `provider_unavailable` | the upstream was not configured or not reachable | "Clinic search is offline… We did not search." |
| `no_hours_source` | no real opening-hours data exists | plain failure; reserved, not yet emitted |

**`no_location` must never render as "no clinics found."** Nothing was searched,
so the count is unknown, and on a safety path that is a claim nobody can
support. An unrecognised `code` renders as a plain failure — never as success.

`provider_available` inside `result` carries the same distinction for the
success path: `true` with an empty `clinics` means we searched and found
nothing, which is a different statement from never having searched.

**Other error paths:** an unknown `conversation_id` raises `HTTPException(404,
"conversation not found")`. That happens inside an already-started
`StreamingResponse` generator, though, so FastAPI cannot turn it into a clean
`404` JSON body: the client just sees the stream fail. If `OPENAI_API_KEY`
is unset, the `get_llm` dependency raises `RuntimeError` before the stream
starts, which surfaces as a `500`.

---

## `GET /api/hospitals/nearby`

**Auth:** none. **Query params:**

| param | type | notes |
| --- | --- | --- |
| `lat` | `float` | required, -90..90 |
| `lon` | `float` | required, -180..180 |
| `specialty` | `str \| null` | max 40 chars, one of the keys below or free text |
| `location_query` | `str \| null` | max 80 chars, mixed into the Naver keyword to bias results toward an area |
| `radius_m` | `int` | default `5000`, 100..50000, **client-side post-filter only** |

`specialty` keywords recognized (`hospital_service.SPECIALTY_KEYWORDS`):
`ENT`, `ALLERGY`, `PULMONOLOGY`, `DERMATOLOGY`, `PEDIATRICS`, `EMERGENCY`,
`GENERAL`. An unrecognized value is still sent to Naver as free text rather
than rejected.

`GET /api/hospitals/nearby?lat=37.5665&lon=126.9780&specialty=ENT&radius_m=3000`

**200**: `HospitalNearbyResponse`, always 200.

```json
{
  "latitude": 37.5665,
  "longitude": 126.978,
  "specialty": "ENT",
  "provider_available": true,
  "count": 2,
  "results": [
    {
      "name": "Seoul ENT Clinic",
      "address": "123 Teheran-ro, Gangnam-gu, Seoul",
      "distance_m": 850,
      "specialty": "ENT",
      "category": "병원>이비인후과",
      "phone": "02-1234-5678",
      "rank": 1
    }
  ]
}
```

### Known limits (Naver Local Search, not a client choice)

- **At most 5 results, no pagination.** `display` is capped at
  `NAVER_MAX_DISPLAY = 5` and `start` only accepts `1`. There is no way to
  fetch a second page.
- **No opening-hours data.** Naver Local Search has no "open now" field. The
  old Google Places version had one; it was removed, not faked.
- **`radius_m` never reaches Naver.** Naver Local Search takes a keyword, not
  a center point + radius. `radius_m` is applied in `find_nearby_hospitals()`
  as a haversine-distance filter on the results Naver already returned, after
  they're ranked. Without `location_query`, the keyword is specialty-only and
  results can come from anywhere in the country that matches it.

---

## Alerts and notification preferences

Served by `backend/app/api/notifications.py`. Alert *generation* lives in
`backend/app/services/notification_service.py` (an in-process APScheduler job
on `CHECK_INTERVAL_MINUTES = 60`, wired into the FastAPI lifespan); this router
only reads and writes. Every route is scoped to `CurrentUser`.

### `GET /api/alerts`

**Auth:** Bearer required. **Query params:** `unread_only: bool` (default
`false`).

Returns the caller's alerts, newest first, each scoped by
`Alert.user_id == current_user.id`.

**200**: `list[AlertResponse]`

```json
[
  {
    "id": 8,
    "risk_level": "HIGH",
    "alert_type": "POLLEN",
    "message": "Tree pollen risk is high in your area today.",
    "is_read": false,
    "created_at": "2026-10-14T09:00:00Z"
  }
]
```

`alert_type` is an `AlertType` value. `risk_level` is a `RiskLevel` value.

### `PATCH /api/alerts/{alert_id}/read`

**Auth:** Bearer required. Path param `alert_id: int`.

**200**: `AlertResponse`, same shape as the list item above.
**404**: `{"detail": "Alert not found"}` if the id doesn't exist or belongs to
another user — the check is `alert.user_id != current_user.id`, so it hides
other users' rows rather than returning a separate 403. This route is not
idempotent: it only ever sets `is_read = True`.

### `GET /api/notifications/preferences`

**Auth:** Bearer required. No params.

**200**: `PreferenceResponse`. The row is created on first read
(`get_or_create_preferences`), so this never 404s for a user who has none.

```json
{
  "alert_pollen": true,
  "alert_air_quality": true,
  "alert_weather": false,
  "min_risk_level": "MODERATE",
  "quiet_hours_start": null,
  "quiet_hours_end": null
}
```

### `PUT /api/notifications/preferences`

**Auth:** Bearer required. **Body:** `PreferenceUpdateRequest`. Every field is
optional; only supplied fields change.

| field | type | notes |
| --- | --- | --- |
| `alert_pollen` | `bool \| null` | |
| `alert_air_quality` | `bool \| null` | |
| `alert_weather` | `bool \| null` | |
| `min_risk_level` | `RiskLevel \| null` | `LOW` \| `MODERATE` \| `HIGH` \| `EMERGENCY` |
| `quiet_hours_start` | `int \| null` | 0–23 |
| `quiet_hours_end` | `int \| null` | 0–23 |

**200**: `PreferenceResponse`, same shape as above.

---

## Degradation contracts

Two endpoints are designed to **never 500 on a dead upstream**: they return
`200` with an explicit "this data is missing/unavailable" signal instead:

- **`GET /api/environment/current`**: if the weather, air-quality, or pollen
  provider fails (timeout, non-2xx, bad JSON, or an unexpected exception),
  that block's fields come back all `null` (`weather.temperature`,
  `air_quality.pm25`, `pollen.tree`, etc.). `risk.score()` treats a `null`
  field as zero-contribution, so `points`/`risk` still compute from whatever
  succeeded. There is no single "environment is down" flag. A client checks
  each block's fields for `null` instead.
- **`GET /api/hospitals/nearby`**: if Naver is unreachable or misconfigured
  (missing `naver_client_id`/`naver_client_secret`, network error, non-2xx,
  bad JSON, or an `errorMessage` body), the response is `200` with
  `provider_available: false`, `count: 0`, `results: []`.

---

## Enums

Client-facing (sent in a request body): `backend/app/core/enums.py`.

**`Allergen`** (`POST /api/allergies`): named species plus legacy coarse
buckets. The named values are what the app offers; the legacy ones remain
accepted so existing rows keep working.

- **Tree (8):** `BIRCH`, `OAK`, `ALDER`, `WILLOW`, `POPLAR`, `JAPANESE_CEDAR`,
  `PEACH`, `OLIVE`
- **Grass (6):** `TIMOTHY`, `COCKSFOOT`, `ZOYSIA`, `BERMUDA_GRASS`,
  `SILVER_GRASS`, `WEEPING_GRASS`
- **Weed (6):** `RAGWEED`, `MUGWORT`, `COCKLEBUR`, `BEGGAR_TICKS`,
  `LAMB_QUARTERS`, `DOCK`
- **Mould (2):** `ALTERNARIA`, `CLADOSPORIUM`
- **Indoor (2):** `HOUSE_DUST_MITE`, `COCKROACH`
- **Particulates (2):** `PM25`, `PM10`
- **Legacy coarse (6):** `TREE_POLLEN`, `GRASS_POLLEN`, `WEED_POLLEN`, `DUST`,
  `MOLD`, `OTHER`

**`AllergenCategory`** is *not* an API enum — it is the internal scoring bucket
that `allergen_category(value)` derives for any `Allergen`: `TREE`, `GRASS`,
`WEED`, `MOLD`, `DUST`, `AIR_QUALITY`, `OTHER`. Scoring matches on the category,
never on the exact species, so `BIRCH` scores identically to `TREE_POLLEN` and
`PM25` resolves to `AIR_QUALITY`. `resolve_allergen()` raises on an unknown
string rather than defaulting — a silent fallback would drop a real allergy
match.

**`AllergySeverity`** (`POST /api/allergies`):
`MILD`, `MODERATE`, `SEVERE`

Response-only (a client reads these, never sends them):

**`PollenLevel`** (`environment.pollen.*`): `LOW`, `MODERATE`, `HIGH`

**`RiskLevel`** (`environment.risk`, `alerts[].risk_level`,
`notifications.min_risk_level`): `LOW`, `MODERATE`, `HIGH`, `EMERGENCY`

**`TriageLevel`** (`triage.level`, `chat.triage_level`): `LOW`, `MODERATE`, `EMERGENCY`

**`AlertType`** (`alerts[].alert_type`): `POLLEN`, `AIR_QUALITY`, `WEATHER`,
`GENERAL`

Not exposed by any of the 16 endpoints above (internal only, for reference):
**`MessageRole`** (`USER`, `ASSISTANT`, `SYSTEM`),
**`ConversationStatus`** (`ACTIVE`, `COMPLETED`, `ABANDONED`).

---

## External API status

Verified against `backend/app/services/*.py` and `backend/app/core/config.py`.

| Service | Provider | Config setting (env var) | Key required? | Status as of this doc |
| --- | --- | --- | --- | --- |
| Weather | Open-Meteo (`api.open-meteo.com`) | none | No | Live and keyless. `weather_api_key` was removed from `Settings` on 2026-10-04 because nothing read it and Open-Meteo needs no key. |
| Air quality | Open-Meteo Air Quality (`air-quality-api.open-meteo.com`) | none used | No | Live, keyless, same pattern as weather. |
| Pollen | KMA 꽃가루농도위험지수 (`apis.data.go.kr`, see `docs/research/pollen-providers.md`) | `pollen_api_key` (`POLLEN_API_KEY`) | Optional (graceful fallback) | `fetch_pollen()` calls the real KMA provider when `POLLEN_API_KEY` is set; on any provider failure it degrades to an all-`None` `PollenData` (`is_sample: false` — a real "no data" response, not the sample). With no key it returns `sample_pollen()`: a hardcoded, clearly-flagged (`is_sample: true` → `pollen_is_sample` in the response) sample. The two are never blended. The provider doesn't report a grass reading, so `pollen.grass` stays `null` even with a real key. |
| Hospitals | Naver Local Search (`openapi.naver.com/v1/search/local.json`) | `naver_client_id` + `naver_client_secret` (`NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`) | **Yes, both** | Live when both are set. If either is blank, `NaverLocalClient.search()` raises before any HTTP call and the endpoint degrades to `provider_available: false` (see above), not an error. |
| LLM (chat agent) | OpenAI-compatible endpoint, model from `OPENAI_MODEL` (default `gpt-4o-mini`); `OPENAI_BASE_URL` points it at OpenRouter or any proxy | `openai_api_key` (`OPENAI_API_KEY`) | **Yes** | One client, `get_openai_client_from_settings()` in `app/core/openai_client.py`, built lazily so an unset key is not a 500 on unauthenticated requests. Every call is capped by `openai_max_tokens` (default 512) and `openai_timeout_seconds` (default 20). Provider failures are raised as `LLMCallError` with a `kind` (`timeout` / `rate_limit` / `unavailable` / `malformed`) and surface to the client as an SSE `error` event, never a 500. That event is emitted after `done` and only when the rule engine produced no verdict, so it can never mask an EMERGENCY recommendation. |
