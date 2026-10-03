# ADR 0004 — shadcn/ui is adopted for new screens, under the carve-out ADR 0003 left open

- Status: accepted
- Date: 2026-10-02
- Deciders: Ismoiljon (Tech Lead)
- Amends: [ADR 0003](0003-tailwind-v4-frontend-styling.md)

## Context

[ADR 0003](0003-tailwind-v4-frontend-styling.md) adopted Tailwind v4 as the
styling layer on 2026-09-11 but was never implemented: no `tailwindcss`
dependency, no `@tailwindcss/vite`, no `@import`. The migration plan it
listed was not started.

ADR 0003 rejected shadcn/ui, scoped to "for v1", on the grounds that it
rewrites existing hand-rolled components and adds an unagreed dependency.
It closed with: *"They can be added later for specific components without
rewriting the rest."*

The chat screen (J5) needed a production-grade agent chat UI. Rather than
hand-roll one, it was built on `assistant-ui`, a MIT-licensed React library
with a documented path for custom SSE backends. That worked without a
component library. The next ask was Profile and Settings screens, where
the same reasoning applies: composing forms, cards, switches and selects
by hand is exactly the work that reads as generic and under-designed.

The remaining screens also had to move to Tailwind regardless, because
`shadcn init` pulls in preflight, a global reset that changes how the
existing hand-written CSS renders.

## Decision

**Adopt shadcn/ui, on the Radix base with the Nova preset, for new
screens. Migrate the existing screens to Tailwind utilities so the app
ends with one styling layer rather than two.**

This uses the carve-out ADR 0003 left open rather than reversing it. The
constraint ADR 0003 attached, that the existing hand-rolled components
must not be rewritten, is met by migrating them to Tailwind utilities
rather than to shadcn components: the screens keep their own structure and
their own design, and only the styling mechanism changes.

Concretely:

- `frontend/components.json` records style `radix-nova`, `rsc: false`,
  Tailwind v4, CSS variables, Lucide icons.
- Components live in `frontend/src/components/ui/`, added as source via
  the CLI, never vendored by hand.
- The `@/` alias is declared in `tsconfig.json` and `tsconfig.app.json`
  and mirrored in `vite.config.ts`. No `baseUrl`: TypeScript 6
  deprecates it and `./src` paths resolve without it.
- The shadcn semantic layer (`--background`, `--primary`, ...) is defined
  as aliases onto the existing raw tokens, not as new colors. The app
  palette is unchanged; shadcn reads it.
- The `@theme` block stays **non-inline** per ADR 0003, so the
  `data-theme="dark"` override keeps repainting utilities at runtime.

## Alternatives rejected

- **Hand-write Profile and Settings.** Same reason the chat screen went to
  assistant-ui. The forms are the generic part; the brand is the tokens,
  and the tokens are already ours.
- **Adopt shadcn and skip the Tailwind migration.** Preflight would land
  and restyle five working screens with no rewrite behind them, shipping a
  visual regression. Rejected.
- **Use a different base (Base UI or React Aria).** Radix is the
  long-standing default with the widest compatibility record on React 19.
  Revisit if Radix causes trouble.
- **Take the preset's font.** Nova pairs with Geist. The app's typefaces
  are self-hosted Fraunces and Hanken Grotesk and were not being replaced
  three days before a release.

## Consequences

- Five screens (AppShell, TopHeader, BottomNav, Login, Register, Today,
  Alerts) plus the chat screen get their `className` strings rewritten to
  Tailwind utilities. theme.css shrinks as rules are no longer referenced.
- The shadcn CLI wrote `import { cn } from "cn"` in every component it
  added, instead of `@/lib/utils`. Every added file needs that import
  corrected; check for it after any `add`.
- `lucide-react` enters the dependency tree as the icon library for
  shadcn components. The existing hand-rolled icons in
  `components/icons.tsx` are left alone.
- `clsx`, `tailwind-merge`, `class-variance-authority` and `radix-ui` are
  runtime dependencies now.
- oxlint reports `only-export-components` warnings on the added files,
  because shadcn exports `buttonVariants` and friends next to the
  components. This is upstream's own pattern and is left as a warning.
