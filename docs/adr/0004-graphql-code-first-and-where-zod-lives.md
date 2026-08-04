# ADR 0004 — Schema-first GraphQL, and what is left for Zod

Date: 2026-08-04
Status: Accepted
Decider: Ismoiljon (Tech Lead)
Supersedes part of ADR 0001

## Context

ADR 0001 made Zod schemas in `@pollen/contracts` the single source of truth for
every payload, with NestJS DTOs generated from them. We have since chosen
GraphQL for the API, which introduces a second candidate source of truth for the
same shapes. Two sources of truth for one payload always drift; one has to go.

A second decision followed: code-first or schema-first.

## Decision

**Schema-first.** The SDL in `apps/api/src/schema/*.graphql` is hand-written and
is the contract. TypeScript types are generated from it into
`apps/api/src/graphql.generated.ts`, which is committed. CI regenerates and
fails on any difference.

**Zod is kept for untrusted boundaries only** — where data arrives from outside
the system and GraphQL offers no protection:

- KMA / data.go.kr API responses
- the exported ML artifact (ADR 0002)
- environment configuration

`@pollen/contracts` keeps the Zod schemas for those boundaries and the shared
constants the web app needs.

## Why schema-first over code-first

Code-first derives the contract from implementation classes, which means the
contract changes as a *side effect* of editing code. Schema-first inverts that:
the contract is a file you open on purpose, in a language that says nothing
about TypeScript, and the implementation is checked against it.

For a three-person team freezing an API at the end of Week 1, that direction
matters more than the convenience of decorators. The SDL is also readable by
someone who does not know NestJS — which includes the mentor reviewing it.

## Why not keep Zod on internal payloads

Belt-and-braces validation on an internal boundary is not free: it is a second
definition to keep in step, and in practice the two drift silently until an
integration bug surfaces. GraphQL already validates every query against the
schema at the edge, so a Zod re-parse of the same payload adds nothing.

External data is the opposite case. KMA can change a field, ship an unexpected
null, or return an error body with a 200. Nothing in GraphQL helps there, and
that is exactly where parse-don't-cast earns its keep.

## Consequences

- `nestjs-zod` is removed. No `@ObjectType`/`@Field`/`@ArgsType` decorators.
- DTO files under `components/<feature>/dto/` re-export the generated types, so
  components still import from their own folder.
- Scalars declared in SDL need runtime implementations — `DateTimeScalar` and
  `ObjectIdScalar` in `libs/scalars/`. A scalar declared with no implementation
  silently passes values through unvalidated, which is worse than not having it.
- Persistence models (`schemas/`) stay separate from the exposed types (`dto/`).
- `src/schema/` (GraphQL SDL) and `components/*/schemas/` (Mongoose) are
  different things despite similar names.
- The web app is typed by hand against the SDL. If the query count grows past a
  handful, generate the client types too.

## Reconsider if

The team finds the SDL and the resolvers drifting in practice — schema-first
gives no compile-time guarantee that a resolver matches its SDL field, which is
the real cost of this choice versus code-first.
