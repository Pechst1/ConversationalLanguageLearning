---
name: e-4-split-monoliths
description: E-4 · split one oversized module (living_story, missions, atelier.tsx, daily_journey, journey_planner, journey_conversation) into cohesive modules without changing behaviour. One module per agent run; name the module in the task.
model: opus
effort: xhigh
---

You split **one** module per run (the task names which) — **E-4 · Split
the monoliths, safely**. Never work on a module another agent is splitting.

Targets and seams:
- `app/services/living_story.py` (5.8k): director / actor / checks / memory & bookkeeping / scoring
- `app/services/missions.py` (5.7k): Courrier letters / corrector / chains / legacy missions
- `web-frontend/pages/atelier.tsx` (5.7k): the WP-16 split proposal (Home, legacy Séance, controllers)
- `app/services/daily_journey.py` (4.8k): lifecycle / steps & attempts / snapshot / story bridge
- `app/services/journey_planner.py` (4.1k): pricing / candidates / day shapes / assembly
- `app/services/journey_conversation.py` (4.1k): authored grading / live replies / feedback policy

Method (strict):
1. Read the whole module and its tests. Write a short seam plan (which
   functions go where, which import cycles to avoid) at the top of your report.
2. Pin behaviour at the public functions with tests if the existing suites do
   not already cover them.
3. Pure moves: each commit moves code without editing it and passes the full
   suite; the old module re-exports every public name so callers keep working.
4. Only then small cleanups, each in its own commit.
Never mix a behaviour change into a move.

**Done when:** the module is under 2,000 lines, all suites and the E-3 walk (if
present) are unchanged, and `git log --follow` finds each moved function.

## Ground rules (every E-agent)

- Spec: `docs/implementation/atelier-v2/WORK-PACKAGES-2026-09-29-engineering.md`,
  section §3 · E-4. Read it first; it is the contract. §1 says why, §2 which model.
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
