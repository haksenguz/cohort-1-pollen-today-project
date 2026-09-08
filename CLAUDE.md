# Allergy AI Companion — working rules for Claude

> [AGENTS.md](AGENTS.md) is the contract every agent follows, and the spec is
> [docs/pollen_documentation.md](docs/pollen_documentation.md). Read both first.
> How we keep agents on-spec: [docs/GOVERNANCE.md](docs/GOVERNANCE.md). Where
> AGENTS.md and this file disagree, AGENTS.md wins.

## Git push identity — MANDATORY LAW

Every commit and push in this repo goes out as **ismoiljon1101**. No exceptions.

- Author name: **Ismoiljon**
- Author email: **ismoiljonedu@gmail.com**
- Push target: only remotes under **github.com/Ismoiljon1101/**. In this repo
  that is the `mine` remote. **Never** push to `origin` (haksenguz upstream) or
  any other account.
- **Never** commit or push as Claude. **Never** add a `Co-Authored-By` trailer
  or any Claude/AI attribution to commits or PRs here.

Before any `git push`, verify:

```bash
git config user.name    # -> Ismoiljon
git config user.email   # -> ismoiljonedu@gmail.com
git remote get-url mine # -> https://github.com/Ismoiljon1101/...
```

If identity or remote is wrong, fix it before pushing.

## Project

- Backend: FastAPI + SQLModel (`backend/`). Package manager for Python: `uv`.
- Data model: `docs/erd/allergy_ai.dmm` (Luna Modeler) is the ERD. Regenerate it
  and `schema.sql` from `docs/erd/gen_dmm.py`.
- Frontend is a phone-first **PWA**, designed and built separately. Do not
  scaffold or build frontend UI here unless asked.
- Safety-critical rule: the LLM only does conversation + extraction; the
  deterministic engine in `backend/app/services/triage.py` owns every safety
  decision. Keep its tests green.
