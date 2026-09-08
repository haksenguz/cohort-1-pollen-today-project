# ADR 0001 — The LLM never makes the safety decision

- Status: accepted
- Date: 2026-09-08
- Deciders: Ismoiljon (Tech Lead)

## Context

This app handles health symptoms and can steer someone toward or away from
emergency care. The spec is explicit (§4, §23): the safety-critical decision
must use explicit rules and validated criteria, not a model's free judgement.
The 2026 agent-team consensus says the same thing — keep the component that
decides separate from the one that converses, and put a deterministic guardrail
outside the model.

## Decision

The LLM does conversation and structured extraction only. It turns a chat into
`{symptoms, severity, breathing_difficulty, airway_swelling, ...}`. A
deterministic rule engine, `backend/app/services/triage.py`, takes that struct
and decides `LOW | MODERATE | EMERGENCY`. Red flags (breathing difficulty,
airway swelling, listed emergency symptoms) force `EMERGENCY` regardless of any
score. Each decision records a `rule_version` and is stored in `triage_results`
separately from the LLM-extracted `symptom_events`, so the decision is auditable.

## Alternatives rejected

- **Let the LLM classify triage directly.** Rejected: non-deterministic,
  untestable, unauditable, and unsafe for an emergency gate. A prompt tweak
  could silently change who gets told to call an ambulance.
- **One table holding symptoms and the triage verdict together.** Rejected:
  collapses the extraction/decision boundary and loses re-evaluation history
  when `rule_version` changes. Kept them as `symptom_events` → `triage_results`
  (1:N).

## Consequences

Triage logic is boring, testable Python with full branch coverage. The LLM can
be swapped or improved without touching the safety guarantee. The cost is a
second table and an extra hop, which is the point.
