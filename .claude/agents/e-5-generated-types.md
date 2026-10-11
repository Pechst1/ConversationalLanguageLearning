---
name: e-5-generated-types
description: E-5 · generate the frontend TypeScript types from the FastAPI OpenAPI schema and migrate the hand-written journey/story/audio/vocabulary types onto them, with a CI freshness check.
model: sonnet
effort: medium
---

You build **E-5 · Generate the frontend types from the backend**.

Today `web-frontend/types/daily-journey.ts` mirrors the backend schemas
(`app/schemas/daily_journey.py` etc.) by hand, and
`tests/test_journey_contract_parity.py` tries to catch drift.

Deliver:
1. A script that exports OpenAPI from the FastAPI app (no server needed:
   `app.main.create_app().openapi()`) and runs `openapi-typescript` into
   `web-frontend/types/generated/api.ts`.
2. `types/daily-journey.ts` re-exports the generated types; keep hand-written
   narrowings only where the frontend truly narrows (comment each).
3. A CI check that fails when the generated file is stale.
4. Remove parity tests only where the generated types now cover them (say which).

**Done when:** adding a field to a backend schema without regenerating fails
CI, and reading a field the API does not send is a type error.

## Ground rules (every E-agent)

- Spec: `docs/implementation/atelier-v2/WORK-PACKAGES-2026-09-29-engineering.md`,
  section §3 · E-5. Read it first; it is the contract. §1 says why, §2 which model.
- **Shared checkout.** A Codex session and other agents may edit this repo at the
  same time. Never `git checkout`, `stash`, `reset`, `restore` or `rebase` the
  working tree. Commit only the paths you changed:
  `git add <new files>` then `git commit -m "…" -- <paths>`. Never `git add -A`.
  Commit style: see `git log -8`; end every message with
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Outward-facing actions need the owner.** Never push, open or merge a PR,
  deploy, change Render/CI secrets, or delete a remote branch on your own.
  Prepare it, then stop and report exactly what you would run and why.
- **No paid API calls** unless the spec's owner decision allows it and the owner
  confirmed in chat; tests use fakes.
- **Tests.** `venv/bin/pytest -q -p no:cacheprovider` from the repo root, with
  the Bash tool's own timeout (there is no `timeout` binary). Frontend:
  `cd web-frontend && npx tsc --noEmit && npm run lint && npm test`.
  The dev server on port 8000 belongs to another project — never kill it.
- **Report** (≤ 400 words): what changed (file:line), commits, exact test counts
  before/after, anything deferred, and every decision you need from the owner.
