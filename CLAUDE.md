# Allergy AI Companion — working rules for Claude

> [AGENTS.md](AGENTS.md) is the contract every agent follows, and the spec is
> [docs/pollen_documentation.md](docs/pollen_documentation.md). Read both first.
> How we keep agents on-spec: [docs/GOVERNANCE.md](docs/GOVERNANCE.md). Where
> AGENTS.md and this file disagree, AGENTS.md wins.

## Git push identity — MANDATORY LAW

Every commit and push goes out as **ismoiljon1101**. No exceptions.

- Author name: **Ismoiljon**
- Author email: **ismoiljonedu@gmail.com**
- **Team repo** is `origin` = **github.com/haksenguz/cohort-1-pollen-today-project**.
  Ismoiljon works on `feat/ismoiljon`, Jack works on `feat/jack`, both merge
  into `main`.
- **Push workflow (revised 2026-09-11).** Ismoiljon has write access to
  `origin`. Push `feat/ismoiljon` directly to `origin` — no PR round-trip
  for the lane-1 work. The `Ismoiljon1101` fork (`mine`) is **not** kept in
  sync by the agent; if Ismoiljon says "push to mine" and `mine` is behind
  `origin`, **treat that as a misroute** — push to `origin` and flag the
  wording in the response so Ismoiljon knows.
- **Never** commit or push as Claude. **Never** add a `Co-Authored-By` trailer
  or any Claude/AI attribution to commits or PRs.
- **Never** force-push `main` on either remote.

Before any `git push`, verify:

```bash
git config user.name    # -> Ismoiljon
git config user.email   # -> ismoiljonedu@gmail.com
git remote -v           # origin -> haksenguz (team), mine -> Ismoiljon1101 (fork)
```

If identity is wrong, fix it before pushing.

## How we work — two people, two lanes

Owners and the current task list live in [TASKS.md](TASKS.md). The contract
between the lanes is [docs/API_CONTRACT.md](docs/API_CONTRACT.md); change it
only by agreement, because the other lane builds against it.

- **Ismoiljon** (tech lead) → `feat/ismoiljon`. Triage, environment, hospitals,
  auth, notifications, and the frontend shell.
- **Jack** (AI engineer) → `feat/jack`. The conversation vertical end to end:
  the agent graph, the chat endpoint, the chat screen.

Rules that keep the lanes apart:

- Jack never edits `backend/app/services/triage.py` or `risk.py`.
- Ismoiljon never edits `backend/app/agents/`.
- `backend/app/main.py` and `backend/pyproject.toml` collide no matter how we
  split, so **Ismoiljon owns both**. Jack asks for additions.
- Rebase on `main` before merging, so conflicts get resolved locally rather
  than in the merge: `git fetch origin && git rebase origin/main`.
- `main` stays green. Run the gate before you merge:

```bash
cd backend && uv run ruff check . && uv run ruff format --check . && uv run pytest -q
```

## Project

- Backend: FastAPI + SQLModel (`backend/`). Package manager for Python: `uv`.
- Data model: `docs/erd/allergy_ai.dmm` (Luna Modeler) is the ERD. Regenerate it
  and `backend/db/init/01_schema.sql` from `docs/erd/gen_dmm.py`.
- Frontend is a phone-first **PWA** in `frontend/` (prototype only for now).
  Do not scaffold or build frontend UI there unless asked.
- Safety-critical rule: the LLM only does conversation + extraction; the
  deterministic engine in `backend/app/services/triage.py` owns every safety
  decision. Keep its tests green.
