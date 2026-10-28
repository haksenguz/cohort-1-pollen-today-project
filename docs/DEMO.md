# Demo script

Five minutes, one screen at a time, on a phone. Everything below was verified
against the real providers, so the numbers you see are the numbers on the
screen.

Have these ready before you start:

- a phone with the site open, signed in as a fresh account
- the pollen and air quality for Seoul (the demo city)
- this page

## 0. The one-line pitch

An allergy app that tells you how urgent your symptoms are, based on a rule
engine rather than a guess, and shows you the pollen, the air and the nearest
clinic.

## 1. Sign up and consent (30 seconds)

Register with a real email. The 민감정보 consent screen comes first, and it is
not a formality: symptom text is health data, and it is sent to the LLM
provider to be answered. Say that out loud. It is the most impressive thing in
the app, because most apps hide it.

## 2. Today (60 seconds)

Set your location, or accept the default for Seoul.

- The risk chip reads LOW, MODERATE or EMERGENCY. It comes from
  `backend/app/services/risk.py`, a rule engine. The model never touches it.
  It reads "unavailable" when no provider answered, because a day the app could
  not ask anybody is not a calm day.
- Air quality and weather are live from Open-Meteo.
- Pollen is live from KMA. In spring it is trees, in late summer weeds, and
  in between it is honestly "no data" rather than a neighbour's reading.
- The clinic list is live from Naver Local Search, ranked by distance.

Point at the clinic list and say: the backend can call this itself now, the
agent has a `find_nearby_care` tool, and it ranks by real distance.

## 3. The chat (90 seconds)

Type, in Korean:

```
눈이 너무 가려워요 계속 재채기해요
```

The app asks a follow-up about breathing and swelling instead of jumping to a
verdict. Type:

```
숨쉬기 힘들고 목이 부어서 부풀었어요
```

The verdict card comes back **EMERGENCY**, with a one-tap `tel:119` button and
a "find a clinic near you" action.

Say this: the model wrote the sentence, the engine wrote the verdict. The
emergency path is deterministic, so a flaky provider can never talk it down.

Then show that the answer streams in, that the history drawer has real
titles, and that the search finds a thread by a word from the middle of it.

## 4. Privacy and data (60 seconds)

Settings, privacy and data:

- **Export** downloads a JSON file with everything held about the account.
- **Delete account** is permanent and says so.
- The policy lists the four notice items and says it was written from the code
  and not by a lawyer. It names the operator once `OPERATOR_NAME` and
  `OPERATOR_REGISTRATION_NUMBER` are set in `.env`, and until then it says
  plainly that nobody is named yet. A policy that claims an operator nobody
  has is not a policy.

This is the section that makes the app credible to a Korean audience. Korean
privacy law treats symptom data as 민감정보 and requires consent, a published
policy, a named operator and a deletion that cannot be undone.

## 5. What is not there (30 seconds, say it yourself)

Do not let anyone find these on their own:

- Alerts are generated and stored, but delivery is not switched on by default.
- The clinic list is emergency and allergy clinics by name and distance. It
  does not know who is open right now, because no provider in reach publishes
  live opening hours for ordinary clinics.
- The rule engine decides urgency. The model does not diagnose, and it refuses
  to.

## Emergency fallback

If the model provider is slow or down, the chat answers with a stored fallback
and the app still works: today, the clinic list, the history and the privacy
rights do not depend on the model at all.

## Verify the deployment yourself

```bash
curl -sS https://your-domain/health
docker compose exec -e VERIFY_BASE_URL=https://your-domain api \
  python scripts/verify_live_chat.py
```

The first check is liveness. The second holds a real two-turn conversation and
asserts that the verdict matches a direct call to the rule engine, so it is
the check to run after any change to the chat path.
