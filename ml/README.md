# ml/ — offline model training

Owner: Jamshid (Slice A)

**Nothing in this directory is deployed.** Training runs on your machine. The
only thing that crosses into the application is a JSON artifact.

See [ADR 0002](../docs/adr/0002-model-runs-as-an-offline-artifact.md) for why.

## The contract with the app

Training must output `models/forecast.vN.json` shaped like:

```json
{
  "modelVersion": "gbm-v1",
  "trainedAt": "2026-08-20T00:00:00Z",
  "features": ["lag1_risk", "lag2_risk", "temp_c", "humidity", "wind_ms", "doy"],
  "classes": ["LOW", "MODERATE", "HIGH", "VERY_HIGH"],
  "params": {}
}
```

The API validates this with a Zod schema on load. A malformed artifact fails at
startup, not at 07:00 in front of real subscribers.

## What must exist by Milestone 2

Per the kickoff deck, slide 14 — this is the part you get interviewed on:

1. A **persistence baseline** first: tomorrow equals today. Every later claim is
   measured against it.
2. **Per-class recall for High and Very high**, reported separately. Overall
   accuracy is not an acceptable answer — a model that always predicts LOW
   scores well and warns nobody.
3. `MODEL_CARD.md`: what it does, how well, and where it is weak. An honest
   limitation beats an inflated number.

## Blocked

Historical KMA data is not available yet — the data.go.kr key is not issued.
See [OPEN_QUESTIONS.md](../OPEN_QUESTIONS.md) §2.
