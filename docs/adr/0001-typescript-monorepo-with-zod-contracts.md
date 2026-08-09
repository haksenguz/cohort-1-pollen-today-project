# ADR 0001 — TypeScript monorepo with Zod as the shared contract

Date: 2026-08-04
Status: Superseded by ADR 0006 (language) — the monorepo and one-shared-contract
principle still hold; the language does not.
Decider: Ismoiljon (Tech Lead)

## Context

Three engineers own three vertical slices that must integrate without blocking
each other. The kickoff deck's slice-A description mentions FastAPI, and the
Week-0 brief lists a Python toolchain (ruff, pytest, APScheduler). The API
contract freezes at the end of Week 1 and cannot drift after that.

## Decision

One pnpm monorepo in TypeScript. `packages/contracts` holds Zod schemas as the
single source of truth. NestJS DTOs are generated from them via `nestjs-zod`;
the Vite app parses responses with the same schemas.

## Why

A frozen contract is only frozen if it is mechanically enforced. With one shared
package, a contract change breaks all three packages' typecheck in the same CI
run. With three services and a written-down agreement, the freeze is
honour-system and drift is discovered at integration time.

Zod also gives runtime validation on both sides of the wire from one definition,
so the API and the web app cannot disagree about a payload shape.

## Alternatives considered

- **Python everywhere (FastAPI + Pydantic)** — matches the deck literally, and
  is the more natural fit for slices A and B. Rejected: the tech lead is
  strongest in TypeScript, owns the repo, and the runtime does not need Python
  once training is offline (see ADR 0002).
- **Three separate repos** — rejected, makes the contract freeze unenforceable.
- **class-validator (NestJS default)** — rejected, decorator DTOs cannot be
  shared with the frontend, so the contract would exist twice.

## Consequences

- Deviates from the deck's stated FastAPI. Flagged to the mentor.
- Jamshid and Giyos work in TypeScript for their API and UI layers.
- Jamshid keeps Python for model training only — ADR 0002.
