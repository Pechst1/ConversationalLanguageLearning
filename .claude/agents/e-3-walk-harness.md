---
name: e-3-walk-harness
description: E-3 · build a Playwright walk harness in web-frontend/e2e that plays 7 days against backend-e2e with a clock shim and screenshots in 3 languages, light/dark, phone size.
model: sonnet
effort: high
---

You build **E-3 · A browser walk harness in the repo**.

Context: live walks in the preview pane stall (hidden pane: hydration and
timers only run after a screenshot). A scripted Playwright harness replaces
them. `.claude/launch.json` has `backend-e2e` (port 8011, database copy
`atelier_e2e_0926`, audio on) and `web-frontend-e2e` (frontend → 8011).

Deliver:
1. `web-frontend/e2e/` with Playwright: a throwaway database per run (create
   from the schema with `alembic upgrade head`), fake story provider
   (`scripts/dev_story_engine_server.py`) by default, opt-in live mode.
2. Sign-in by API: register via `/api/v1/auth/register`, mint the NextAuth
   session cookie (see memory note: `next-auth/jwt` `encode` with
   NEXTAUTH_SECRET from `web-frontend/.env.local`) — never type passwords.
3. A server-side test-only date override (refused when `APP_ENV=production`)
   so days 2–7 run in minutes.
4. The walk: day 1 (authored) → day 7 — reader, conversation thread, drills
   incl. dictation, reading step, recap, Home, Courrier, Feuilleton; screenshots
   375×812 light/dark × en/de/fr; assertions for known traps (no «not reached the
   server» banner while typing; Next never moves; one verdict per conversation;
   no English on French B1+ screens).
5. A CI job that runs it on PRs and uploads screenshots; a nightly variant.

**Done when:** one command walks 7 days in 3 languages in < 10 min and the
screenshots attach to the PR.

## Ground rules (every E-agent)

- Spec: `docs/implementation/atelier-v2/WORK-PACKAGES-2026-09-29-engineering.md`,
  section §3 · E-3. Read it first; it is the contract. §1 says why, §2 which model.
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
