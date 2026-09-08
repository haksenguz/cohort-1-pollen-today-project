# ADR 0002 — Frontend is a Vite + React PWA, backend stays separate

- Status: accepted
- Date: 2026-09-08
- Deciders: Ismoiljon (Tech Lead)

## Context

Clients are on phones. The app is chat-first. We already have a FastAPI backend
that owns the LLM, triage, and data. We wanted a stack that an AI agent can build
correctly with the least flailing, and that reaches "installable on a phone"
cheaply.

## Decision

Vite + React + `vite-plugin-pwa`. The frontend is a client SPA that talks to the
FastAPI backend over HTTPS and streams chat over SSE. Chat UI is lifted from
existing kits (shadcn/ui chat components, assistant-ui with its LangGraph
adapter), not hand-built. The polished visual design is done by a designer; the
committed HTML prototype in `frontend/prototype.html` is the reference.

## Alternatives rejected

- **Next.js.** More turnkey AI-chat templates exist, but they assume a Next
  backend we don't need, and the App Router's server/client split, RSC, and
  hydration traps are where agents make wrong turns. The template edge cancels
  once you remove the backend half.
- **Build chat UI from scratch.** Rejected: slow, and it looks AI-made. We glue
  proven components instead.

## Consequences

One mental model (everything is client), browser-only debugging, first-class
PWA. The backend contract (its REST + SSE API) is the boundary the PWA consumes,
which keeps the two tracks independent. Frontend lives in `frontend/` and is not
scaffolded (Vite) until the design is settled; only the prototype sits there now.
