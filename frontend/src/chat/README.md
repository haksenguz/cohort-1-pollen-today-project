# frontend/src/chat/

Home of TASKS.md **J5** ("Chat screen. The frontend chat UI against the
SSE contract"). Owned by Ismoiljon since the two-lane split ended
2026-10-02.

This folder is still empty. The `/chat` route currently renders a
placeholder defined in `frontend/src/routes/ChatPlaceholderPage.tsx` so
the app shell has a working nav. Build the real screen here and point
`App.tsx`'s `/chat` route at it.

The typed `POST /api/chat` SSE client already exists at
`frontend/src/api/client.ts` (`streamChat`), built against
[docs/API_CONTRACT.md](../../../docs/API_CONTRACT.md) — reuse it rather than
hand-rolling another fetch/EventSource call.
