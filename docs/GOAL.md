# GOAL — build the agent ugly, now

Issued by Ismail, 2026-10-18. Shared contract for every agent on this project.
Read this before taking a task. If your instructions conflict with it, this file
and Ismail win.

## The goal

**The chat agent becomes a real agent.** Not a chatbot with a lookup bolted on.

Concretely, by the end of this build:

1. The model is handed typed tool schemas and **chooses which tool to call, with
   what arguments, in what order**. That is the whole difference between a
   chatbot and an agent.
2. There is a bounded loop — reason, act, observe, repeat — with a hard step cap
   and a cost ceiling. Never an open-ended `while`.
3. At least one tool is **real**, backed by real data:
   `find_nearby_care` → `find_nearby_hospitals`, which already exists and already
   returns ranked clinics by distance.
4. The user can **see** which tool ran and what came back. A tool call the user
   cannot see is indistinguishable from a slow chatbot.
5. ADR 0001 is untouched: **no tool may accept or return a triage level.** The
   deterministic engine still owns every safety decision.

Ugly first. A working end-to-end loop that is imperfect beats a beautiful
half-loop. Refinement is the next pass, not this one.

## Why this and not the rest

Group A of B-014 is closed and the safety work is merged. Everything else in
`bugs.md` is cosmetic next to this: the original complaint was *"it's not an
agent, it's just a chatbot"* and that is **still literally true**. Group D is
0 of 16.

## Division of labour

Disjoint files. Nobody touches anyone else's column. Nobody commits until the
end of the write phase.

### Backend lane — `backend/app/**`, `backend/tests/**`

| | Task | State |
|---|---|---|
| B1 | `core/openai_client.py` — tool schema binding, tool-call parsing, `complete_with_tools` | **ALREADY BUILT** `openai_client.py:126`, `ToolCall:87`, `_parse_arguments:143` |
| B2 | `agents/symptom_agent.py` — the ReAct loop | **ALREADY BUILT** `MAX_TOOL_STEPS:54`, loop at `:552`, `tool_steps`/`tool_observations:122` |
| B3 | `find_nearby_care` implemented for real against `find_nearby_hospitals` | open — `symptom_agent.py:278-279` is still `_not_wired_executor`, `wired=False` |
| B5 | **the real blocker, and it was missing from the first version of this file** — emit the `tool` SSE event from `chat.py` and put `tool_calls` on `ChatResponse` | open |
| B4 | **Reviewer-writer** — reviews the above, then **fixes what it finds**. Keeps the A4 guard green | pending |

**B5 is why nothing frontend-side can be tested yet.** The loop already collects
`tool_steps` and `tool_observations` into state and nothing reads them. There is
no `_sse("tool", ...)` anywhere in the backend and `ChatResponse` has no
`tool_calls` field, so every field in F1 and F3 is waiting on this one change.

### Frontend lane — `frontend/**`

| | Task |
|---|---|
| F1 | `api/types.ts`, `api/client.ts` — tool event types and SSE parsing |
| F2 | `chat/activity.ts`, `chat/ChatScreen.tsx` — show tool activity inline, in plain language |
| F3 | new `chat/ToolResult.tsx` — render a clinic list inside the chat from a tool result |
| F4 | **Reviewer-writer** — reviews F1–F3, then **fixes what it finds**. Also checks the backend SSE contract for client-side breakage |

## The wire contract — do not deviate

Additive only. Existing `status` / `message` / `error` / `done` events keep
their current shape.

```
event: tool
data: {"id":"call_1","name":"find_nearby_care","status":"running","args":{"radius_m":3000}}

event: tool
data: {"id":"call_1","name":"find_nearby_care","status":"done","summary":"3 clinics found"}

event: tool
data: {"id":"call_2","name":"find_nearby_care","status":"error","summary":"Provider unavailable"}
```

`status` is one of `running` | `done` | `error`. `summary` is one short
plain-English line for the user — never a raw exception, never a traceback.

The terminal `done` event carries the audit list:

```
data: { ..., "tool_calls":[{"name":"find_nearby_care","status":"done","summary":"3 clinics found"}] }
```

A `find_nearby_care` result carries clinics for rendering:

```json
{"name":"...","address":"...","distance_m":1240,"phone":"...","rank":1}
```

`code` names WHY a call produced no result, in a small agreed set. It exists so
three failures a user can act on never collapse into one another. An
unrecognised code renders as a plain failure — never as success.

```
event: tool
data: {"id":"call_1","name":"find_nearby_care","status":"error",
       "code":"no_location","summary":"I don't have your location yet"}
```

| code | means | client |
|---|---|---|
| `no_location` | the profile has no coordinates | "We need your location first", with a button to Settings |
| `provider_unavailable` | the upstream is not configured | "Clinic search is offline… We did not search." |
| `no_hours_source` | no real hours data exists | renders as a plain failure until D4 has a source |

**`no_location` must not fold into "no clinics found."** That is a false claim
on a safety path: the verdict said get help, the agent searched, and it would
report an empty result. It is also not a failed search — nothing broke, the user
simply has not set a location, which takes five seconds.

**If you need a field that is not in here, say so in the group message before
you invent it.** A mismatched guess costs both lanes a debugging round.

## Rules that matter more than speed

- **ADR 0001 is the ceiling.** No tool schema may contain `triage_level`,
  `triage_severity` or `triage_verdict`. No tool assesses urgency. The
  `test_tool_registry.py` guard must stay green.
- **Never invent clinical data.** If a tool cannot get real hours for a clinic,
  it says it cannot. A guessed clinic hour is worse than no answer.
- **Plain English for users.** The user is a beginner Korean learner. No jargon,
  no raw JSON on screen.
- **Path-scoped `git add <file>...` only.** Never `-A`, never `commit -a`. Two
  lanes share one checkout.

## Phases

1. **Write** — every lane implements its tasks, in parallel, disjoint files.
   No commits yet.
2. **Cross review** — B4 reviews the frontend, F4 reviews the backend. Both fix
   in place. Both write code; review is not read-only.
3. **Gate** — backend: ruff, ruff format, pytest (on Postgres). Frontend: tsc,
   vitest, oxlint. All green or it does not ship.
4. **Live smoke** — a real turn against the running backend that calls a tool.
   Screenshot or pasted transcript, not a claim.
5. **Push** — path-scoped commits, then push `feat/ismoiljon`, then a PR to
   `main`. Never straight to `main`.

## Status

- [x] B1 tool binding — already built before this file existed
- [x] B2 ReAct loop — already built before this file existed
- [ ] **B5 `tool` SSE emission — THE BLOCKER**
- [ ] B3 `find_nearby_care` real
- [ ] B4 backend review pass
- [x] F1 tool events client
- [ ] F2 tool activity UI
- [x] F3 tool result render
- [ ] F4 frontend review pass
- [ ] gate green
- [ ] live smoke
- [ ] pushed + PR

## Corrections to the first version of this file

Written 2026-10-18 after B1/B2 were found already on `main`, and after two of
my own agents had to be corrected mid-build.

1. **B1 and B2 were phantom tasks.** They were reported as done days earlier and
   I wrote them into this file without verifying. Both are real and merged.
2. **B5 was missing entirely** — and it is the only thing the frontend is
   actually waiting on.
3. **The `done` payload must stay additive.** `tool_calls` is present only when
   the backend sent it. An agent here tried to inject `tool_calls: []` into every
   response and then edited the pre-existing additive-contract test to match its
   own behaviour. It was overruled.
4. **Stale comment already on `main`:** `chat.py:250-251` still says *"The agent
   has no tools and does no function-calling."* That stopped being true when the
   loop landed. Same class as B-013 — worth fixing while B5 is in that file.