# ADR 0006 — The API is Python and FastAPI

Date: 2026-08-09
Status: Accepted
Decider: Ismoiljon (Tech Lead)
Supersedes ADR 0001's language choice; ADR 0004's schema-first decision stands

## Context

ADR 0001 chose a TypeScript monorepo. Since then three things changed the
balance:

1. The Week-0 brief specifies a Python toolchain by name — ruff, pytest,
   APScheduler, and a compose file of app / scheduler / postgres / caddy.
   Python is the stack the mentor will read and debug fluently.
2. Slice A is machine learning and Slice B is time-series analytics. Both are
   Python-native. Under TypeScript, two of three engineers work in their second
   language while the tech lead — who reviews every pull request within 24
   hours — works in his first.
3. The tech lead wants to learn Python and FastAPI. On a portfolio project whose
   stated purpose is employability, that is a legitimate input, not a whim.

## Decision

The API is Python 3.12: FastAPI, Ariadne for GraphQL, Beanie over PyMongo's
async client, APScheduler, Pydantic v2. Tooling is uv, ruff and pytest.

`apps/web` stays TypeScript — React and Vite. It speaks GraphQL over HTTP and
does not care what serves it.

## What this did NOT cost

The port took under a day because the schema-first decision (ADR 0004) made the
contract portable. `apps/api/schema/*.graphql` moved byte-for-byte; Ariadne
loads the same files NestJS did. Had we been code-first, the contract would have
been expressed in TypeScript decorators and would have had to be rewritten and
re-agreed.

The business logic was likewise small — roughly 150 meaningful lines across the
idempotency claim, KST date handling, the Korean message template and the
staleness rule. Everything else was framework wiring, which is exactly the part
a framework should let you throw away.

## What it did cost

`packages/contracts` no longer serves both sides. It now generates TypeScript
for the web app only, via graphql-codegen; the Python API reads the SDL
directly. Two derivations from one source instead of one — still no drift, but
more plumbing.

Python cannot generate enums from SDL the way graphql-codegen does, so
`libs/enums.py` is hand-written. `tests/test_enums_match_sdl.py` parses the real
SDL and fails if the two disagree. That test is what makes hand-writing
acceptable, and deleting it would quietly reintroduce the drift this project has
spent four ADRs avoiding.

## Alternatives considered

- **Stay on TypeScript.** Rejected on team fit, not on technical merit — TS was
  working, green, and adequate. The deciding factor was that two of three
  engineers and the mentor are Python-first.
- **Strawberry instead of Ariadne.** Rejected: Strawberry is code-first, which
  would have undone ADR 0004 and made the SDL a generated artifact again.
- **Keep TS and run Jamshid's ingest as a separate Python process writing to the
  same MongoDB.** Genuinely viable, and cheaper. Rejected because it leaves the
  team split across two languages permanently, and the tech lead reviews both.

## Consequences

- Verification is now two commands, not one: `uv run ruff check . && uv run
  ruff format --check . && uv run pytest` for the API, `pnpm build/typecheck/
  lint/test` for the web.
- CI runs a real MongoDB service container. The idempotency tests demand it — a
  mock that accepts two identical inserts would pass while proving nothing.
- Python modules are snake_case; the kebab-case rule in CONVENTIONS §1 now
  applies to `apps/web` only.
- The switch happened at 4 commits. It would have cost several times more in
  week 4, and this is noted so the next language debate happens early or not at
  all.
