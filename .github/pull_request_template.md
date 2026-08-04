## What and why

<!-- One or two sentences. What changes, and which slice/milestone item it serves. -->

Slice: <!-- A Forecast / B Analytics / C Alerts / Shared -->
Closes: <!-- issue or milestone task -->

## How to verify

<!-- Exact steps a reviewer runs. Not "it works" — the command and the expected output. -->

```bash
```

## Definition of Done

- [ ] `pnpm build`, `pnpm typecheck` and `pnpm lint` pass locally
- [ ] `pnpm test` passes locally
- [ ] New behaviour has a test; bug fixes have a regression test
- [ ] No hardcoded regions, thresholds, URLs, dates, or secrets — env or `@pollen/contracts` only
- [ ] Contract change? Both other slice owners approved in writing (see `docs/adr/`)
- [ ] Docs updated if setup, env vars, or architecture changed

## Notes for the reviewer

<!-- Anything you are unsure about, or specifically want challenged. -->
