# ADR 0002 — The model is an offline artifact, not a service

Date: 2026-08-04
Status: Accepted
Decider: Ismoiljon (Tech Lead), affects Slice A

## Context

Slice A trains a classifier predicting pollen risk 1–3 days ahead. The obvious
shape is a Python inference service the TypeScript API calls. That means two
runtimes, two deploys, and a network hop on every request.

## Decision

Training happens offline in `ml/` on the slice owner's machine, using whatever
Python tooling suits it. It exports a versioned JSON artifact — feature spec plus
learned parameters — which is committed and loaded by the API. Inference is
arithmetic in TypeScript. No Python is deployed.

## Why

The pollen index updates once per day. A live inference service adds cost,
latency, a second deploy, and a second failure mode, and buys nothing that a
daily batch does not already provide.

Keeping sklearn for training preserves the part that matters for slice A's
interview story: a persistence baseline, per-class recall on High and Very high,
and an honest write-up of where the model is weak. Hand-rolling that in
TypeScript would spend weeks on plumbing rather than on the model.

## Consequences

- `modelVersion` is a field in the artifact, so the contract's required version
  field is satisfied for free.
- The artifact is validated with a Zod schema on load — a malformed model fails
  at startup, not at 07:00.
- Retraining is a deliberate, reviewable commit rather than an invisible
  background process. This is a feature for a six-week project.
- If the model ever needs per-request features, this decision has to be revisited.
