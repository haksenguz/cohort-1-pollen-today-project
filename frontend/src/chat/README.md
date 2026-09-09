# frontend/src/chat/

Owned by Jack — TASKS.md **J5** ("Chat screen. The frontend chat UI against
the SSE contract."). Do not build UI here except as that lane.

This folder is intentionally empty. The `/chat` route currently renders a
placeholder defined in `frontend/src/routes/ChatPlaceholderPage.tsx` (outside
this folder, on purpose) so the app shell has a working nav without touching
Jack's lane. Wire it up here and point `App.tsx`'s `/chat` route at your
component when this lane is ready.

The typed `POST /api/chat` SSE client already exists at
`frontend/src/api/client.ts` (`streamChat`), built against
[docs/API_CONTRACT.md](../../../docs/API_CONTRACT.md) — reuse it rather than
hand-rolling another fetch/EventSource call.
