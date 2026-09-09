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
| `POST /api/triage` | Public |
| `POST /api/chat` | Bearer token |
| `GET /api/hospitals/nearby` | Public |

**`POST /api/chat` takes its identity from the token.** `ChatRequest.user_id`
is gone. The route depends on `CurrentUser`, and the conversation is looked up
before the stream opens, so a `conversation_id` belonging to another user is
rejected with `404` rather than `403` — the endpoint never confirms that
someone else's conversation exists.

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

```json
{ "latitude": 37.5, "longitude": 127.0 }
```

**200**: `UserResponse` (same shape as `GET /api/users/me`).
**409** if the new email is already taken by another user.

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

**Auth:** none. **Body:** `TriageRequest`

| field | type | notes |
| --- | --- | --- |
| `symptoms` | `list[str]` | default `[]`, free-text tokens (e.g. `"throat_swelling"`) |
| `severity` | `int \| null` | 0–10 |
| `breathing_difficulty` | `bool` | default `false` |
| `airway_swelling` | `bool` | default `false` |

```json
{ "symptoms": ["sneezing", "itchy_eyes"], "severity": 4, "breathing_difficulty": false, "airway_swelling": false }
```

**200**: `TriageResponse`, always produced by `triage.assess()`.

```json
{
  "level": "LOW",
  "recommendation": "Symptoms look mild. Consider an antihistamine and monitor.",
  "reasons": [],
  "rule_version": "triage-2026-09-07"
}
```

`level` is a `TriageLevel` (`LOW | MODERATE | EMERGENCY`). Any red-flag
symptom or either boolean flag forces `EMERGENCY` and short-circuits
everything else (see `triage.py`'s `EMERGENCY_SYMPTOMS`).

---

## `POST /api/chat`

**Auth:** `Authorization: Bearer <token>`, required. **Body:** `ChatRequest`

| field | type | notes |
| --- | --- | --- |
| `message` | `str` | 1–2000 chars |
| `conversation_id` | `int \| null` | omit to start a new conversation |

A `user_id` in the body is ignored. The user is the token holder.

**Status codes:** `401` without a valid token. `404` when `conversation_id`
does not exist or belongs to someone else.

```json
{ "message": "I've had itchy eyes and sneezing since this morning", "conversation_id": null }
```

### Response: this is Server-Sent Events, not a plain JSON body

`chat()` returns `StreamingResponse(..., media_type="text/event-stream")`.
Read `backend/app/api/chat.py` for the exact generator (`_run_chat`). It is
**not** token-by-token streaming. It always emits exactly one of these two
sequences, then closes the stream:

**Normal turn**: one `message` event, then one `done` event:

```
event: message
data: {"delta": "Are you having any difficulty breathing, or swelling of your lips, tongue, or throat?"}

event: done
data: {"message": "Are you having any...", "conversation_id": 42, "symptoms": ["sneezing", "itchy_eyes"], "severity": 4, "duration": "this morning", "possible_trigger": null, "breathing_difficulty": null, "airway_swelling": null, "triage_level": null, "triage_reasons": [], "triage_rule_version": null}

```

`message.delta` is the field name, but it carries the **full assistant
reply as one string**, not an incremental chunk. The frontend must not treat
it as a token stream. The `done` event's `data` is the complete
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

**`Allergen`** (`POST /api/allergies`):
`TREE_POLLEN`, `GRASS_POLLEN`, `WEED_POLLEN`, `PM25`, `PM10`, `DUST`, `MOLD`, `OTHER`

**`AllergySeverity`** (`POST /api/allergies`):
`MILD`, `MODERATE`, `SEVERE`

Response-only (a client reads these, never sends them):

**`PollenLevel`** (`environment.pollen.*`): `LOW`, `MODERATE`, `HIGH`

**`RiskLevel`** (`environment.risk`): `LOW`, `MODERATE`, `HIGH`, `EMERGENCY`

**`TriageLevel`** (`triage.level`, `chat.triage_level`): `LOW`, `MODERATE`, `EMERGENCY`

Not exposed by any of the 12 endpoints above (internal only, for reference):
**`AlertType`** (`POLLEN`, `AIR_QUALITY`, `WEATHER`, `GENERAL`),
**`MessageRole`** (`USER`, `ASSISTANT`, `SYSTEM`),
**`ConversationStatus`** (`ACTIVE`, `COMPLETED`, `ABANDONED`).

---

## External API status

Verified against `backend/app/services/*.py` and `backend/app/core/config.py`.

| Service | Provider | Config setting (env var) | Key required? | Status as of this doc |
| --- | --- | --- | --- | --- |
| Weather | Open-Meteo (`api.open-meteo.com`) | none used | No | Live. `weather_api_key` (`WEATHER_API_KEY`) exists in `Settings` but nothing in `weather_service.py` reads it. Dead config. |
| Air quality | Open-Meteo Air Quality (`air-quality-api.open-meteo.com`) | none used | No | Live, keyless, same pattern as weather. |
| Pollen | none wired | `pollen_api_key` (`POLLEN_API_KEY`) | Checked but has no effect | `fetch_pollen()` always returns `sample_pollen()`: a hardcoded, clearly-flagged (`is_sample: true` → `pollen_is_sample` in the response) sample, whether or not `POLLEN_API_KEY` is set. Korea isn't covered by the keyless providers; a real provider (Google Pollen, Ambee, ...) is not yet plugged in. |
| Hospitals | Naver Local Search (`openapi.naver.com/v1/search/local.json`) | `naver_client_id` + `naver_client_secret` (`NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`) | **Yes, both** | Live when both are set. If either is blank, `NaverLocalClient.search()` raises before any HTTP call and the endpoint degrades to `provider_available: false` (see above), not an error. |
| LLM (chat agent) | OpenAI, model `gpt-4o-mini` | `openai_api_key` (`OPENAI_API_KEY`) | **Yes** | `get_llm_client()` raises `RuntimeError` if unset. Since this runs in a FastAPI dependency on `POST /api/chat`, an unset key surfaces as a `500`, not a graceful degradation, unlike weather/air-quality/pollen/hospitals. |
