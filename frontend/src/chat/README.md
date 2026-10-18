# frontend/src/chat/

Home of TASKS.md **J5** ("Chat screen. The frontend chat UI against the
SSE contract"). Owned by Ismoiljon since the two-lane split ended
2026-10-02.

The screen is built. `App.tsx` points `/chat` at `ChatScreen.tsx`.

## The shape of it

| File | Job |
|---|---|
| `ChatScreen.tsx` | Thread, composer and message rendering, built from assistant-ui primitives |
| `allergyChatAdapter.ts` | The only file that knows our chat wire format. Feeds assistant-ui one finished message per turn |
| `activity.ts` | Store for what the turn is doing right now: pipeline stages and tool calls |
| `agentActivity.tsx` | The strip above the composer that renders that store |
| `ToolResult.tsx` | The clinic list a `find_nearby_care` result becomes |
| `TriageVerdict.tsx` | The safety verdict card |

## What the user is not allowed to see

Tool names, tool arguments and raw JSON. `activity.ts` is the seam that
guarantees it: `setToolActivity` reads `name` and `args` off the SSE event and
drops both before anything downstream holds them, so no component has the
option of rendering an identifier. A tool with no sentence of its own gets an
honest generic line rather than a guess.

The same rule covers values we did not get. A result we cannot read, a provider
that is offline and a search that found nothing are three different answers and
`ToolResult.tsx` gives each its own state, icon and sentence. ADR 0001 is the
ceiling: no tool type carries a triage level and nothing here may imply that a
lookup can judge urgency. That stays with the rule engine in
`backend/app/services/triage.py`.

## The wire

The typed `POST /api/chat` SSE client is at `frontend/src/api/client.ts`
(`streamChat`) and is built against [docs/API_CONTRACT.md](../../../docs/API_CONTRACT.md)
and the tool-event contract in [docs/GOAL.md](../../../docs/GOAL.md) — reuse
it rather than hand-rolling another fetch/EventSource call.