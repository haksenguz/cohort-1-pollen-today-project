# ADR 0003 — Tailwind v4 is the FE styling layer; theme.css tokens survive as the source of truth

- Status: accepted
- Date: 2026-09-11
- Deciders: Ismoiljon (Tech Lead)

## Context

The frontend (`frontend/`) shipped on hand-written CSS in `src/styles/theme.css`
(587 lines). `ADR 0002` chose that path and the implementation followed.
The current FE work — Today redesign, Alerts redesign, the new Profile screen —
needs to add a hero card, three new form sections, and type-colored alert
icons against a prototype. The decision is whether to keep building on the
existing pure-CSS system or migrate to Tailwind.

Two findings drove the change:

1. **AI agents are noticeably stronger at Tailwind than at hand-written CSS.**
   Vercel v0, Cursor, and the dominant UI-generation tools ship Tailwind as
   their default styling layer. The training-data dominance shows up in
   first-pass output quality. M3 (the model used in this repo's AI agents)
   is no exception.
2. **v4 closes the training-data gap the right way.** v4 is CSS-first
   (`@theme` directive in CSS, no `tailwind.config.js`), uses native CSS
   variables, and integrates with `@tailwindcss/vite` for Vite. It is what
   every new Tailwind tutorial, shadcn/ui default, and v0 generation ships
   on. Adopting v3 in 2026 means migrating to v4 within a year.

The non-trivial cost: the existing `theme.css` is 587 lines of working CSS
with a settled design-token layer (`--brand`, `--emergency`, `--font`,
`data-theme="dark"`, etc.). Rewriting it for Tailwind is not free.

## Decision

**Adopt Tailwind v4 (CSS-first) for the FE, keeping `theme.css` `:root`
tokens as the single source of truth for raw color values.**

Concrete shape:

- `@tailwindcss/vite` plugin in `frontend/vite.config.ts`. No PostCSS config.
- One new file: `frontend/src/styles/theme.css` becomes the merged token +
  Tailwind layer file. Existing `:root` vars stay as-is (light + dark +
  `data-theme="dark"` overrides). Add a non-inline `@theme` block that
  references those raw vars via `var()`.
- `@custom-variant dark (&:where(.dark, .dark *))` so `dark:` utilities
  work alongside the existing `data-theme` toggle.
- Existing utility rules in `theme.css` (`.risk-card`, `.metric-list`,
  `.alert-row`, `.hospital-row`, `.note`, etc.) become either `@utility`
  blocks or get deleted in favor of Tailwind utilities used directly in
  the JSX. Decision per rule; default is "delete and use utilities."
- Dark mode runtime switching stays working because tokens are raw CSS
  vars (not `@theme inline` — the v4 pitfall that breaks dark mode).
- `@apply` is **not** used. It is deprecated in v4.
- No component library (no shadcn/ui, no daisyUI) — the existing
  hand-rolled component structure is preserved; only the styling layer
  changes. shadcn can be added later for specific complex primitives
  (Dialog, DropdownMenu) without rewriting the rest.

For AI-agent safety, the `ofershap/tailwind-best-practices` skill is
installed and a one-paragraph note is added to `frontend/AGENTS.md`
(merged into the root `AGENTS.md` if no frontend-specific one exists).
The note lists the renamed utilities (`bg-linear-to-r`, `bg-black/50`,
etc.) and the four anti-patterns (v3 config, `@tailwind` directives,
`@apply`, `dark:` for tokens).

## Alternatives rejected

- **Stay on hand-written CSS.** Rejected because the AI-agent output
  quality gap is real and the team is one person (Ismoiljon on the FE
  lane). The training-data advantage compounds across every component.
- **Tailwind v3.** Rejected because v3 is the deprecated line and the
  agents are *better* at v3, not v4 — adopting v3 now means doing this
  migration twice.
- **Tailwind v4 with `@theme inline`.** Rejected because `@theme inline`
  bakes token values into utilities at build time, which breaks runtime
  dark-mode switching. The project already has a `data-theme="dark"`
  toggle (`TopHeader.tsx` cycle); preserving it is non-negotiable.
- **shadcn/ui or daisyUI on top of Tailwind.** Rejected for v1. Both
  rewrite the existing hand-rolled components (`.risk-card`, `.alert-row`,
  etc.) and add a library dep the team has not agreed on. They can be
  added later for specific components without rewriting the rest.
- **Move tokens entirely into `@theme`.** Rejected because raw CSS vars
  in `:root` are needed for non-utility CSS (PWA manifest `theme_color`,
  any inline `style` that touches colors). Two-layer with `:root` + a
  non-inline `@theme` keeps both paths working.

## Consequences

- ` `frontend/package.json` adds `tailwindcss` and `@tailwindcss/vite` as
  dev dependencies. No PostCSS, no autoprefixer (v4 handles it).
- `frontend/vite.config.ts` adds `tailwindcss()` to the plugins array.
- `frontend/src/styles/theme.css` shrinks by approximately half (the
  utility rules migrate to JSX) and grows by a `@theme` block + a
  `@custom-variant dark` line + a `@import "tailwindcss"` at the top.
- All existing pages (`LoginPage`, `RegisterPage`, `TodayPage`,
  `AlertsPage`, `ChatPlaceholderPage`, `TopHeader`, `BottomNav`,
  `AppShell`) get their `className` strings rewritten to Tailwind
  utilities. No visual regression acceptable.
- The existing tests (`vitest` + Testing Library) must stay green.
  Tests assert class names like `riskClass(env.risk)` returning
  `"emergency"`; that still works because `riskClass()` keeps returning
  the same string, used as part of `className={"... " + riskClass(env.risk)}`.
- `ADR 0002`'s sentence *"No UI kit: styling is hand-written CSS using
  the tokens from `prototype.html`"* is partially superseded. ADR0003
  becomes the source of truth for the styling layer; ADR0002 stays
  authoritative on the rest (Vite + React + PWA stack choice).
- The plan file at `.hermes/plans/2026-09-11_120000-fe-today-profile-alerts.md`
  is amended to reflect the Tailwind choice; its pure-CSS assumptions
  in the Foundations (F1–F3) are replaced with Tailwind equivalents.

## Migration commit plan

The migration is split into ~12 small commits to keep the gate green at
every step (`pnpm install --frozen-lockfile && oxlint && pnpm build &&
pnpm test`):

1. `docs(adr): record tailwind v4 as the FE styling layer`
2. `docs(agents): add tailwind v4 context note for AI agents`
3. `chore(frontend): install tailwind v4 + @tailwindcss/vite`
4. `chore(frontend): wire @tailwindcss/vite into vite.config.ts`
5. `feat(frontend): restructure theme.css for tailwind v4 (import + @theme + custom-variant)`
6. `refactor(frontend): migrate AppShell + TopHeader + BottomNav to tailwind`
7. `refactor(frontend): migrate LoginPage + RegisterPage to tailwind`
8. `refactor(frontend): migrate TodayPage to tailwind (baseline, not yet redesigned)`
9. `refactor(frontend): migrate AlertsPage to tailwind (baseline, not yet redesigned)`
10. `refactor(frontend): migrate ChatPlaceholderPage + AuthContext (no visual change)`
11. `refactor(frontend): delete dead .css rules now covered by tailwind utilities`
12. `feat(frontend): start vertical A — Today redesign with tailwind + prototype parity`

After migration, the three verticals (Today redesign, Profile, Alerts
redesign) proceed per the existing plan, rewritten for Tailwind.

## Notes for the agent

Tailwind v4 anti-patterns to avoid in this repo:

- `tailwind.config.js` — does not exist; v4 is CSS-first.
- `@tailwind base;` / `@tailwind components;` — replaced by `@import "tailwindcss"`.
- `@apply` — deprecated in v4; use utilities directly in JSX.
- `dark:bg-foo` for token-driven colors — use `@custom-variant dark` + raw `:root` vars, then `dark:bg-foo` works automatically without `dark:` variant on the token.
- `bg-gradient-to-r` — use `bg-linear-to-r`.
- `bg-opacity-50` — use `bg-black/50`.
- `text-color-primary` without defining `--color-primary` in `@theme`.

Read `frontend/AGENTS.md` before styling work.