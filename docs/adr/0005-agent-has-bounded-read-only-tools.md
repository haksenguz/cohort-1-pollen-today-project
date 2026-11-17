# ADR 0005: The symptom agent may call bounded, read-only lookup tools

- Status: accepted
- Date: 2026-11-17
- Deciders: Ismoiljon (Tech Lead)

## Context

The spec says the agent has no tools (`docs/pollen_documentation.md` §3 and
the SSE section). That was true for the first version. Users still ask
practical questions mid-chat, such as "is there a clinic near me?". The agent
cannot answer that from the chat alone. A lookup adds real value. It also
opens a path toward the safety decision, so ADR 0001 must hold.

The symptom agent in `backend/app/agents/symptom_agent.py` now runs an
optional tool loop. Its one tool, `find_nearby_care`, reuses the Naver Local
Search behind `GET /api/hospitals/nearby`. The loop runs at most
`MAX_TOOL_STEPS = 3` calls per turn. Without a registry, the graph is unchanged.

## Decision

The agent may call tools, under these rules:

- **Read-only.** Every tool fetches factual directory data. No tool writes to
  the database, sends a message, or changes a user's profile.
- **Bounded.** A turn makes at most three tool calls. The count lives in graph
  state (`tool_steps`), so the cap survives a retry.
- **Never decides urgency.** Tool output is stored as text in
  `tool_observations`. No code path leads from that field to `triage_level`,
  `triage_reasons`, or any extracted field. `tests/test_tool_registry.py`
  enforces this by walking the registry, so a new tool that takes or returns a
  safety field fails the build.
- **Server resolves the origin.** The caller's saved location is resolved per
  request by `app.api.chat`. The model never reads the profile and never
  supplies coordinates.
- **Refusals are plain.** A tool that cannot run returns a fixed code
  (`no_location`, `provider_unavailable`). The user sees "we could not search,"
  never "there is nothing nearby."
- **`location_query` is untrusted.** The model picks this string, so it is
  treated as untrusted input. It only biases a Naver keyword search. It never
  feeds triage, and no code acts on it beyond building the search.

## Alternatives rejected

- **No tools, as the spec says.** Rejected for now. The lookup answers a real
  user need, and the boundary above keeps the safety path intact. The spec
  stays the source of truth for the no-tools rule until this ADR is accepted
  and the spec line changes with it.
- **Let the tool result feed the triage input.** Rejected. A clinic list says
  nothing about how severe a symptom is. Mixing the two would let a directory
  result move a safety verdict, which ADR 0001 forbids.
- **Open-ended tool loop.** Rejected. An unbounded loop costs money, adds
  latency to an emergency-adjacent turn, and makes the path hard to test.

## Consequences

Users get nearby-care answers in chat without a separate screen. The safety
guarantee from ADR 0001 is unchanged: the rule engine in
`backend/app/services/triage.py` still makes every decision. The cost is a
larger surface to test. Each new tool needs a registry test entry and a refusal path. A tool that is not read-only, or that touches a safety field, needs a new ADR first.
