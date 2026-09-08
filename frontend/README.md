# frontend/

Phone-first PWA. Stack decision: [ADR 0002](../docs/adr/0002-vite-react-pwa-frontend.md)
(Vite + React + `vite-plugin-pwa`).

Today this folder holds only `prototype.html`, the design reference. The Vite
app gets scaffolded here once the visual design is settled. It talks to the
FastAPI backend in `../backend` over REST + SSE.
