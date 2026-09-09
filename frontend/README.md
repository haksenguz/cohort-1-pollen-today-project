# frontend/

Phone-first PWA. Stack decision: [ADR 0002](../docs/adr/0002-vite-react-pwa-frontend.md)
(Vite + React + `vite-plugin-pwa`). Visual language follows `prototype.html`
(design reference, kept in place — don't delete it).

## Stack

- Vite 8 + React 19 + TypeScript, `react-router-dom` for routing.
- `vite-plugin-pwa` for the manifest + service worker (installable).
- No UI kit: styling is hand-written CSS using the tokens from
  `prototype.html` (`src/styles/theme.css`).

## Layout

```
src/
  api/          typed client for docs/API_CONTRACT.md (client.ts, types.ts)
  auth/         token storage, auth context, guarded-route wrapper
  components/   app shell: header, bottom nav, icons
  routes/       screens: login, register, today, alerts, chat placeholder
  chat/         Jack's lane (TASKS.md J5) — empty except README, do not build here
  styles/       design tokens + shared classes lifted from prototype.html
```

## Run it

```bash
pnpm install
pnpm dev      # http://localhost:5173, talks to the backend at VITE_API_BASE_URL
pnpm build    # type-checks then builds to dist/
pnpm lint     # oxlint
```

Copy `.env.example` to `.env.local` and point `VITE_API_BASE_URL` at the
backend if it isn't on `http://localhost:8000`.

## Auth

`POST /api/auth/register` / `login` return a bearer JWT. It's stored in
`localStorage` (`src/auth/token.ts`) and attached by the API client
(`src/api/client.ts`) on every protected call. `RequireAuth` guards routes
and redirects to `/login` when there's no valid session; it also probes
`GET /api/users/me` on load to confirm a stored token still works.

## Chat screen

`/chat` is a placeholder (`src/routes/ChatPlaceholderPage.tsx`) that renders
"owned by Jack" and nothing else. The real chat UI is Jack's lane
(TASKS.md J5) and lives in `src/chat/`, which is intentionally empty apart
from its own README. The SSE client for `POST /api/chat` already exists at
`src/api/client.ts` (`streamChat`) for that lane to reuse.
