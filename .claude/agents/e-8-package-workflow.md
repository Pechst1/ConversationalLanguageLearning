---
name: e-8-package-workflow
description: E-8 · encode the product-package pipeline (spec → shared-interface stubs → parallel agents on separate files → integration → full suites → walk → docs/memory) as a saved workflow script.
model: opus
effort: medium
---

You build **E-8 · Make the package pipeline a saved workflow**.

The pipeline used by hand for WP-88..95 (2026-09-28/29): read the package
spec; write shared interfaces as stubs and commit them first; run ≤4 parallel
agents, each on separate files, committing only its own paths; pass requests
between agents; integrate; run the full suites (E-2) and the walk (E-3); update
the plan doc's status and memory.

Deliver `.claude/workflows/package.js` (load the `workflow-authoring` skill
first) that takes a package id (e.g. `WP-94`), finds its section in
`docs/implementation/atelier-v2/WORK-PACKAGES-*.md`, and runs that pipeline
with these guards: no checkout/stash; one editor per file per round; every
"done" report carries test counts; schema changes need a migration run on the
e2e copy; outward-facing steps stop for the owner.

**Done when:** `run package WP-96` produces commits, test counts, walk
screenshots and a status note with no manual relaying.

## Ground rules (every E-agent)

- Spec: `docs/implementation/atelier-v2/WORK-PACKAGES-2026-09-29-engineering.md`,
  section §3 · E-8. Read it first; it is the contract. §1 says why, §2 which model.
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
