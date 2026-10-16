# Allergy AI Companion 🌿🤖

An AI-powered web application that helps people monitor environmental
allergy risks, understand their symptoms, and find appropriate nearby
healthcare facilities.

The system combines **environmental data, AI-powered symptom
conversations, rule-based safety triage, and location-aware hospital
discovery**.

> **Important:** This application is an information and
> healthcare-navigation tool. It does not provide a medical diagnosis or
> replace professional medical care.

------------------------------------------------------------------------

## 1. Project Overview

People with allergies can be affected by environmental factors such as:

-   Tree pollen
-   Grass pollen
-   Weed pollen
-   PM2.5 / PM10
-   Weather and wind
-   Humidity
-   Other environmental triggers

The application monitors environmental conditions around the user and
provides personalized allergy-risk alerts.

When a user reports symptoms, an AI agent conducts a structured
conversation to understand:

-   Symptoms
-   Severity
-   Duration
-   Possible triggers
-   Emergency warning signs

The system then performs safety-oriented triage and, when appropriate,
recommends nearby healthcare facilities.

------------------------------------------------------------------------

# 2. Main Features

## 🌿 Environmental Allergy Monitoring

Collect environmental information based on the user's location.

``` text
  User Location
       │
           ▼
Environmental APIs
      │
 ┌────┼─────────────┐
 ▼       ▼             ▼
Pollen AQI        Weather
      │
          ▼
Environmental Risk
```

The system can monitor:

-   Pollen levels
-   Pollen types
-   Air quality
-   PM2.5
-   PM10
-   Temperature
-   Humidity
-   Wind speed

------------------------------------------------------------------------

## 🔔 Personalized Allergy Alerts

The application combines environmental conditions with the user's
allergy profile.

Example:

``` text
Tree Pollen: HIGH
PM2.5:       MODERATE
Wind:        HIGH

User allergy:
Tree pollen

        ↓

Overall Risk: HIGH
```

Example notification:

> 🌿 High pollen risk today.
>
> Tree pollen levels are high in your area. Consider reducing prolonged
> outdoor exposure and following your usual allergy-management plan.

------------------------------------------------------------------------

# 3. AI Symptom Assistant

Users can start a conversation when they experience symptoms.

Example:

``` text
User:
My eyes are itchy and I keep sneezing.

AI:
What other symptoms are you experiencing?

User:
My nose is blocked.

AI:
When did these symptoms start?

User:
This morning.

AI:
Are you experiencing difficulty breathing,
or swelling of your lips, tongue, or throat?
```

The AI converts the conversation into structured information.

Example:

``` json
{
  "symptoms": [
    "sneezing",
    "itchy_eyes",
    "nasal_congestion"
  ],
  "duration": "today",
  "severity": 7,
  "breathing_difficulty": false,
  "airway_swelling": false,
  "possible_trigger": "pollen"
}
```

This structured state is passed to the safety/triage engine.

------------------------------------------------------------------------

# 4. Safety Triage

The system should **not rely entirely on an LLM for medical safety
decisions**.

The architecture separates:

``` text
LLM
 │
 └── Conversation + information extraction
              │
                       ▼
       Structured Symptoms
              │
                       ▼
       Safety / Triage Engine
              │
       ┌──────┼──────┐
            ▼         ▼         ▼
      LOW  MODERATE EMERGENCY
```

## Low Risk

Possible actions:

-   Provide general educational information
-   Provide environmental recommendations
-   Recommend monitoring symptoms

## Moderate Risk

Possible actions:

-   Suggest contacting a healthcare professional
-   Find a nearby clinic
-   Find an appropriate medical department

## Potential Emergency

If serious warning signs are identified, the normal recommendation
workflow should stop and the application should provide appropriate
emergency guidance.

The safety-critical decision layer should use **explicit rules and
validated clinical criteria**, rather than allowing the LLM to freely
determine emergency status.

------------------------------------------------------------------------

# 5. Nearby Hospital Finder

When healthcare evaluation is appropriate:

``` text
User Location
      │
          ▼
Naver Local Search API
      │
          ▼
Nearby Medical Facilities
      │
          ▼
Filtering
 ├── Specialty
 ├── Distance
 ├── Opening status
 └── Facility type
      │
          ▼
Ranking
      │
          ▼
Recommended Facilities
```

Possible information:

-   Hospital/clinic name
-   Distance
-   Location
-   Relevant specialty
-   Opening status
-   Phone number
-   Directions

User actions:

``` text
[Hospital Details]

[Call]

[Directions]
```

------------------------------------------------------------------------

# 6. System Architecture

``` text
                         ┌─────────────────────┐
                         │        USER         │
                         │  Web / Mobile Web   │
                         └──────────┬──────────┘
                                    │
                                                            ▼
                         ┌─────────────────────┐
                         │       Next.js       │
                         │      Frontend       │
                         └──────────┬──────────┘
                                    │
                              HTTPS / REST
                                    │
                                                            ▼
                         ┌─────────────────────┐
                         │       FastAPI       │
                         │      Backend        │
                         └──────────┬──────────┘
                                    │
                 ┌──────────────────┼──────────────────┐
                 │                  │                  │
                            ▼                              ▼                             ▼
        ┌────────────────┐ ┌────────────────┐ ┌────────────────┐
        │ Environmental  │ │   LangGraph    │ │   Hospital     │
        │    Service     │ │   AI Agents    │ │    Service     │
        └───────┬────────┘ └───────┬────────┘ └───────┬────────┘
                │                  │                  │
                           ▼                             ▼                             ▼
        ┌──────────────┐    ┌──────────────┐   ┌──────────────┐
        │ Pollen API   │    │ Symptom Agent│   │ Naver Local  │
        │ AQI API      │    │ Triage Engine│   │ Search API   │
        │ Weather API  │    │ LLM          │   │              │
        └──────────────┘    └──────────────┘   └──────────────┘
                                    │
                                                                ▼
                            ┌──────────────┐
                            │ PostgreSQL   │
                            │              │
                            │ Users        │
                            │ Allergies    │
                            │ Symptoms     │
                            │ Environment  │
                            │ Alerts       │
                            └──────────────┘
```

------------------------------------------------------------------------

# 7. AI Agent Architecture

LangGraph is used to orchestrate the AI workflow.

``` text
                    User Message
                         │
                                         ▼
                 ┌───────────────┐
                 │ Intent Router │
                 └───────┬───────┘
                         │
                     LangGraph
                         │
             ┌───────────┼───────────┐
                     ▼                  ▼                  ▼
      Environmental   Symptom     Hospital
          Agent        Agent        Agent
             │           │           │
             └───────────┼───────────┘
                                         ▼
                  Triage Engine
                  (Rule-based)
                         │
             ┌───────────┼───────────┐
                     ▼                  ▼                  ▼
            LOW        MODERATE    EMERGENCY
             │           │           │
                     ▼                  ▼                  ▼
           Advice     Hospital    Emergency
                      Agent       Guidance
```

### Core agents

#### 1. Environmental Agent

Responsible for:

-   Pollen information
-   Air quality
-   Weather
-   Environmental exposure risk

#### 2. Symptom Agent

Responsible for:

-   Asking symptom questions
-   Extracting structured symptoms
-   Determining symptom severity
-   Identifying possible environmental triggers
-   Asking safety questions

#### 3. Triage Engine

Responsible for:

-   Applying deterministic safety rules
-   Classifying the situation
-   Selecting the next workflow

#### 4. Hospital Agent

Responsible for:

-   Finding nearby facilities
-   Filtering by specialty
-   Checking distance
-   Checking availability/opening status
-   Ranking facilities

------------------------------------------------------------------------

# 8. Environmental Data Architecture

``` text
                 ┌──────────────┐
                 │ Pollen API   │
                 └──────┬───────┘
                        │
                 ┌──────▼───────┐
                 │ Air Quality  │
                 │ API          │
                 └──────┬───────┘
                        │
                 ┌──────▼───────┐
                 │ Weather API  │
                 └──────┬───────┘
                        │
                                        ▼
               ┌─────────────────┐
               │ Environmental   │
               │ Service         │
               └────────┬────────┘
                        │
                                        ▼
               ┌─────────────────┐
               │ Risk Calculator │
               └────────┬────────┘
                        │
                                        ▼
                 User Risk Score
```

Example environmental response, matching `EnvironmentResponse`:

``` json
{
  "latitude": 35.856,
  "longitude": 129.224,
  "pollen": { "tree": "HIGH", "grass": "MODERATE", "weed": "LOW" },
  "air_quality": { "pm25": 42.0, "pm10": 68.0 },
  "weather": { "temperature": 25.0, "humidity": 55.0, "wind": 4.2 },
  "points": 7,
  "risk": "HIGH",
  "pollen_is_sample": false
}
```

Levels are uppercase enum values, not lowercase strings, and coordinates are
flat on the response rather than nested under `location`. Each block degrades
independently: a failed upstream sends that block's fields as `null` while the
rest of the response still computes.

------------------------------------------------------------------------

# 9. Database Design

PostgreSQL is recommended for the primary database.

## Users

``` text
users
----------------
id
email
password_hash
latitude
longitude
created_at
updated_at
```

## User Allergies

``` text
user_allergies
----------------
id
user_id
allergen
severity
created_at
```

## Symptom Events

``` text
symptom_events
----------------
id
user_id
symptoms
severity
duration
possible_trigger
created_at
```

## Environmental Data

``` text
environment_snapshots
----------------
id
latitude
longitude
tree_pollen
grass_pollen
weed_pollen
pm25
pm10
temperature
humidity
wind_speed
risk_level
timestamp
```

## Alerts

``` text
alerts
----------------
id
user_id
risk_level
message
alert_type
is_read
created_at
```

## Hospital Searches

``` text
hospital_searches
----------------
id
user_id
latitude
longitude
specialty
created_at
```

------------------------------------------------------------------------

# 10. Recommended Technology Stack

  Component             Technology
  --------------------- -----------------------------
  Frontend              Next.js
  UI                    React + Tailwind CSS
  Backend               FastAPI
  Agent orchestration   LangGraph
  LLM                   OpenAI / Gemini / Anthropic
  Database              PostgreSQL
  Cache                 Redis
  Background jobs       Celery / Cron
  Maps                  Naver Local Search API
  Pollen                Pollen API
  Air Quality           AirKorea / suitable API
  Weather               Weather API
  Authentication        JWT / OAuth
  Containerization      Docker
  Deployment            AWS / GCP / Render

------------------------------------------------------------------------

# 11. Project Structure

``` text
allergy-ai/
│
├── frontend/
│   ├── app/
│   ├── components/
│   ├── hooks/
│   ├── services/
│   └── package.json
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── auth.py
│   │   │   ├── users.py
│   │   │   ├── allergy.py
│   │   │   ├── symptoms.py
│   │   │   ├── environment.py
│   │   │   ├── hospitals.py
│   │   │   └── chat.py
│   │   │
│   │   ├── agents/
│   │   │   ├── environmental_agent.py
│   │   │   ├── symptom_agent.py
│   │   │   ├── triage_agent.py
│   │   │   └── hospital_agent.py
│   │   │
│   │   ├── services/
│   │   │   ├── pollen_service.py
│   │   │   ├── air_quality_service.py
│   │   │   ├── weather_service.py
│   │   │   ├── hospital_service.py
│   │   │   └── notification_service.py
│   │   │
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── config.py
│   │   └── main.py
│   │
│   ├── requirements.txt
│   └── Dockerfile
│
├── tests/
│   ├── test_triage.py
│   ├── test_symptoms.py
│   └── test_environment.py
│
├── docker-compose.yml
├── .env.example
└── README.md
```

------------------------------------------------------------------------

# 12. API Design

Status of each route below was checked against `backend/app/main.py` and the
`@router` decorators in `backend/app/api/*.py`. Where this section and the
code disagree, the code wins. `docs/API_CONTRACT.md` is the request/response
source of truth; this section is the shape of the surface.

## Auth

``` http
POST /api/auth/register
POST /api/auth/login
```

## User

``` http
GET /api/users/me
PUT /api/users/me
```

`POST /api/users` in the original draft was never built. Registration is
`POST /api/auth/register`, which returns a Bearer token alongside the user.

## Allergy Profile

``` http
GET /api/allergies
POST /api/allergies
DELETE /api/allergies/{id}
```

The `allergen` value is a member of the `Allergen` enum. Named species
(`BIRCH`, `OAK`, `RAGWEED`, `JAPANESE_CEDAR`, …) are what the app offers; the
original coarse buckets (`TREE_POLLEN`, `GRASS_POLLEN`, `WEED_POLLEN`, `DUST`,
`MOLD`, `OTHER`) are still accepted so rows written before the change keep
resolving. Both map onto an internal `AllergenCategory`, which is what scoring
matches on — a named species and its legacy bucket are indistinguishable to the
risk calculator.

## Environment

``` http
GET /api/environment/current
```

`GET /api/environment/forecast` and `GET /api/environment/risk` in the
original draft are **not implemented**. Risk is computed and returned as part of
`/api/environment/current` (`risk`, `points`), not exposed as its own endpoint.

Example:

``` http
GET /api/environment/current?lat=35.856&lon=129.224
```

## AI Chat

``` http
POST /api/chat
```

Request:

``` json
{
  "message": "My eyes are itchy and I keep sneezing."
}
```

The response is **SSE**, not a single JSON object. `POST /api/chat` returns
`text/event-stream` carrying `status` events (the pipeline stages `starting`,
`extracting`, `asking`, `assessing`, `saving`), then a `message` event and a
`done` event, or an `error` event. These are pipeline stages and **not** tool
calls — the agent has no tools and performs no function-calling.

A representative stream:

``` text
event: status
data: {"stage": "starting"}

event: status
data: {"stage": "extracting"}

event: message
data: {"delta": "Are you having any difficulty breathing, or swelling of your lips, tongue, or throat?"}

event: done
data: {"message": "...", "conversation_id": 42, "symptoms": ["sneezing", "itchy_eyes"], "severity": 4, "duration": "this morning", "possible_trigger": null, "breathing_difficulty": null, "airway_swelling": null, "triage_level": null, "triage_reasons": [], "triage_rule_version": null}
```

## Triage

``` http
POST /api/triage
```

## Alerts and notification preferences

``` http
GET   /api/alerts
PATCH /api/alerts/{id}/read
GET   /api/notifications/preferences
PUT   /api/notifications/preferences
```

These are built and were missing from this section. Alerts are generated
server-side by an in-process APScheduler job running hourly
(`CHECK_INTERVAL_MINUTES = 60`).

## Hospitals

``` http
GET /api/hospitals/nearby
```

Example:

``` http
GET /api/hospitals/nearby?lat=35.856&lon=129.224&specialty=ENT
```

------------------------------------------------------------------------

# 13. LangGraph State

The shipped state is `AllergyState` in
`backend/app/agents/symptom_agent.py`. The draft below listed `user_id`,
`pollen_level`, `air_quality` and `recommended_facilities`; none of those exist.
Identity comes from the Bearer token on the request, not the graph, and the
environmental services feed a separate scheduler rather than the chat graph.

``` python
class AllergyState(TypedDict, total=False):
    messages: list[ChatMessage]

    symptoms: list[str]
    severity: int | None
    duration: str | None
    breathing_difficulty: bool | None
    airway_swelling: bool | None
    possible_trigger: str | None

    turn_count: int
    ready: bool
    extraction_error: bool
    llm_error_kind: str | None

    assistant_reply: str | None

    # Set only by triage_node, only from a TriageOutcome. Never by the LLM.
    triage_level: str | None
    triage_recommendation: str | None
    triage_reasons: list[str]
    triage_rule_version: str | None
```

The separation this state exists to enforce: `triage_level` is written in
exactly one place, `triage_node`, and only from the value the deterministic
engine returned. No field above is derived from free-form LLM text except
`symptoms` / `severity` / `duration` / `possible_trigger` / the two safety
flags, which are parsed and validated rather than trusted — a field the model
returns that fails validation is dropped, not coerced.

------------------------------------------------------------------------

# 14. Risk Calculation

A basic prototype can use deterministic scoring.

Example:

``` text
Environmental Risk
------------------
Pollen HIGH       +3
PM2.5 HIGH        +2
Wind HIGH         +1

User Allergy Match
------------------
Known allergen    +2

Symptoms
------------------
Mild              +1
Moderate          +2
Severe            +3
```

Example:

``` text
Pollen             +3
Known allergen     +2
Symptoms           +2
----------------------
Total              7
```

The score can then be mapped to predefined risk categories.

> This scoring system is only an engineering prototype. Production
> healthcare decisions require clinically validated criteria.

------------------------------------------------------------------------

# 15. Notification Architecture

The backend should periodically evaluate environmental conditions
instead of relying on the frontend to continuously poll APIs.

``` text
          Scheduler
              │
                       ▼
       Environmental API
              │
                       ▼
       Risk Calculation
              │
                       ▼
        User Profiles
              │
        ┌─────┴─────┐
        │           │
   Low risk      High risk
                    │
                                 ▼
              Notification
                    │
          ┌─────────┴────────┐
                 ▼                             ▼
        Email              Push
```

For the MVP, Cron can be used.

For a larger deployment:

``` text
Redis + Celery
```

can handle background jobs.

------------------------------------------------------------------------

# 16. Complete Symptom Workflow

``` text
User reports symptoms
        │
             ▼
AI Symptom Agent
        │
             ▼
Ask structured questions
        │
             ▼
Extract structured symptoms
        │
             ▼
Safety/Triage Engine
        │
   ┌────┼────┐
     ▼      ▼      ▼
  LOW  MOD  EMERGENCY
   │    │         │
     ▼      ▼              ▼
 Advice Hospital Emergency
        Agent   Guidance
```

------------------------------------------------------------------------

# 17. Complete Environmental Workflow

``` text
User Location
      │
         ▼
Pollen / AQI / Weather APIs
      │
          ▼
Environmental Service
      │
          ▼
User Allergy Profile
      │
         ▼
Risk Calculator
      │
         ▼
Personalized Risk
      │
          ▼
Alert
      │
          ▼
User
```

------------------------------------------------------------------------

# 18. Complete Hospital Workflow

``` text
Triage Result
      │
          ▼
Healthcare Recommended
      │
          ▼
Hospital Agent
      │
          ▼
User GPS
      │
          ▼
Naver Local Search API
      │
          ▼
Nearby Facilities
      │
         ▼
Filter by Specialty
      │
         ▼
Rank by Distance / Status
      │
          ▼
Top Facilities
```

------------------------------------------------------------------------

# 19. Security and Privacy

The application may process sensitive health-related information.

Important requirements:

-   Use HTTPS.
-   Protect API keys.
-   Never expose private API keys in the frontend.
-   Store secrets in environment variables or a secret manager.
-   Implement authentication and authorization.
-   Minimize stored personal information.
-   Encrypt sensitive data where appropriate.
-   Apply appropriate privacy and healthcare regulations for the
    deployment country.
-   Avoid storing unnecessary raw conversations.
-   Audit safety-critical decisions.

------------------------------------------------------------------------

# 20. Environment Variables

Create:

``` text
.env
```

Example:

``` env
DATABASE_URL=postgresql://user:password@localhost:5432/allergy_ai

OPENAI_API_KEY=

NAVER_CLIENT_ID=

NAVER_CLIENT_SECRET=

POLLEN_API_KEY=

WEATHER_API_KEY=

REDIS_URL=redis://localhost:6379

JWT_SECRET=
```

Never commit `.env` to Git.

Use:

``` text
.env.example
```

for documentation.

------------------------------------------------------------------------

# 21. Development Roadmap

## Phase 1 --- Environmental MVP

-   [ ] User location
-   [ ] Pollen API
-   [ ] Air-quality API
-   [ ] Weather API
-   [ ] Environmental risk calculation
-   [ ] Basic dashboard

## Phase 2 --- Allergy Profile

-   [ ] User registration
-   [ ] Allergy selection
-   [ ] Allergy severity
-   [ ] User preferences
-   [ ] Personalized environmental risk

## Phase 3 --- AI Symptom Agent

-   [ ] LangGraph setup
-   [ ] Conversation state
-   [ ] Symptom extraction
-   [ ] Severity extraction
-   [ ] Trigger identification
-   [ ] Safety questions
-   [ ] Structured symptom output

## Phase 4 --- Triage

-   [ ] Rule-based safety engine
-   [ ] Low-risk flow
-   [ ] Moderate-risk flow
-   [ ] Emergency flow
-   [ ] Safety tests

## Phase 5 --- Hospital Agent

-   [ ] GPS location
-   [ ] Nearby facility search
-   [ ] Specialty filtering
-   [ ] Distance calculation
-   [ ] Opening status
-   [ ] Directions
-   [ ] Phone call

## Phase 6 --- Notifications

-   [ ] Scheduled environmental checks
-   [ ] High-pollen alerts
-   [ ] High-AQI alerts
-   [ ] Personalized notifications
-   [ ] User notification preferences

## Phase 7 --- Personalization

Store:

``` text
Date
Pollen
AQI
Weather
Symptoms
Severity
Possible trigger
```

Then identify patterns:

``` text
High tree pollen
       +
Outdoor exposure
       ↓
Sneezing increases
```

The system can eventually provide personalized insights.

------------------------------------------------------------------------

# 22. MVP User Journey

``` text
                  START
                    │
                                 ▼
              Create Account
                    │
                                 ▼
             Allow Location
                    │
                                 ▼
          Select Known Allergies
                    │
                                 ▼
             Allergy Dashboard
                    │
             ┌──────┴──────┐
                      ▼                     ▼
       Environmental     Symptoms
           Alert         Reported
             │             │
             │             ▼
             │       AI Conversation
             │             │
             │             ▼
             │        Safety Triage
             │             │
             │      ┌──────┼──────┐
             │      ▼         ▼         ▼
             │     LOW    MOD   EMERGENCY
             │      │      │      │
             │      ▼         ▼          ▼
             │    Advice Hospital Emergency
             │           Finder  Guidance
             │
                     ▼
          Continue Monitoring
```

------------------------------------------------------------------------

# 23. Core Design Principle

The most important architectural decision is the separation between the
LLM and the safety engine.

``` text
                 ┌───────────────┐
                 │      LLM      │
                 │               │
                 │ Conversation  │
                 │ Reasoning     │
                 │ Extraction    │
                 └───────┬───────┘
                         │
                                         ▼
                Structured State
                         │
                                         ▼
                 ┌───────────────┐
                 │ Safety Engine │
                 │               │
                 │ Deterministic │
                 │ Rules         │
                 └───────┬───────┘
                         │
                                         ▼
                     Decision
```

**LLM = conversation, reasoning, and structured information extraction**

**Safety Engine = safety-critical decision logic**

This makes the system more predictable, testable, debuggable, and safer.

------------------------------------------------------------------------

# 24. Final Architecture

``` text
                         ALLERGY AI COMPANION
                                  │
             ┌────────────────────┼────────────────────┐
             │                    │                    │
                      ▼                                ▼                                 ▼
       ENVIRONMENT             AI AGENT            HEALTHCARE
       MONITORING              SYSTEM              NAVIGATION
             │                    │                    │
       ┌─────┼─────┐        ┌─────┴─────┐        ┌────┴─────┐
            ▼       ▼        ▼             ▼                  ▼             ▼                ▼
    Pollen  AQI  Weather  Symptoms   Triage   Hospitals  Maps
                           Agent      Engine
                              │          │
                              └────┬─────┘
                                                          ▼
                              User Decision
                                   │
                        ┌──────────┼──────────┐
                                        ▼                ▼                ▼
                       LOW       MODERATE   EMERGENCY
                        │          │          │
                                        ▼                ▼                ▼
                      Advice    Hospital   Emergency
                                Finder     Guidance
```

## Project Goal

Build an AI-powered allergy companion that connects:

**Environmental Exposure → Personalized Alert → Symptom Conversation →
Safety Triage → Nearby Healthcare**

    
