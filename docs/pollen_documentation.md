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

Example environmental response:

``` json
{
  "location": {
    "lat": 35.856,
    "lon": 129.224
  },
  "pollen": {
    "tree": "high",
    "grass": "moderate",
    "weed": "low"
  },
  "air_quality": {
    "pm25": 42,
    "pm10": 68
  },
  "weather": {
    "temperature": 25,
    "humidity": 55,
    "wind": 4.2
  },
  "risk": "HIGH"
}
```

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

## User

``` http
POST /api/users
GET /api/users/me
PUT /api/users/me
```

## Allergy Profile

``` http
GET /api/allergies
POST /api/allergies
DELETE /api/allergies/{id}
```

## Environment

``` http
GET /api/environment/current
GET /api/environment/forecast
GET /api/environment/risk
```

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

Response:

``` json
{
  "message": "When did your symptoms start?",
  "conversation_id": "abc123"
}
```

## Triage

``` http
POST /api/triage
```

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

The agent can maintain a structured state:

``` python
class AllergyState(TypedDict):
    user_id: str

    symptoms: list[str]
    severity: int | None
    duration: str | None

    breathing_difficulty: bool
    airway_swelling: bool

    possible_trigger: str | None

    pollen_level: str | None
    air_quality: str | None

    triage_result: str | None

    recommended_facilities: list
```

This prevents the workflow from depending entirely on free-form LLM
text.

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

    
