# Rules for implementing a pilot package (read fully before starting)

You implement one work package for «L'Atelier», a French-learning app built on a daily serial: FastAPI backend in `app/`, Next.js frontend in `web-frontend/`, GitHub repo reachable with `gh`.

## Read first
- The package plan: `/Users/vincentpechstein/Downloads/Pixel-lab/ConversationalLanguageLearning/.claude/worktrees/experience-review-1117/docs/implementation/pilot-2026-11-17/README.md` — the header, the decisions table and your package's section. Line numbers there are from `origin/main` at `d1486e6c`; verify them.
- The evidence: `…/experience-review-1117/docs/ops/walks/2026-11-17-experience-review.md` (the finding your package names) and, where useful, the verbatim play logs in `…/docs/ops/walks/2026-11-17-experience-review/logs/`.
- Owner decisions: 1 = **15** new words a day on «Normal»; 6 = story writer **Sonnet 5.5**; the Quartier is to be switched on and be a major part of the app. Every other decision in the table is still open: **build the proposal stated in the table and say so at the top of the PR body**, so the owner can reverse it.

## Standing rules of this product (do not break them)
- No new fonts, colours, mascots, rounded/soft geometry, social features or pronunciation scoring. Stay inside the existing «av2» design system and copy tables (every learner-facing string exists in fr, de and en).
- Everything that is not fiction is in the learner's language (French interface from B1). Fiction stays French.
- No solution is shown before the learner's retry. No vocative (addressing a character by name) in sentences the learner builds or writes.
- A learner never sees a wrong correction; when in doubt, show nothing.
- Prefer the smallest change that removes the learner-visible fault. Do not redesign neighbouring systems. Do not touch `app/services/daily_journey.py` unless your task says you may.

## How to work
- The main checkout `/Users/vincentpechstein/Downloads/Pixel-lab/ConversationalLanguageLearning` is shared with another tool: never switch branches, stash or edit files there. Create your own worktree and branch as your task says (`git -C /Users/vincentpechstein/Downloads/Pixel-lab/ConversationalLanguageLearning fetch origin` first), and work only inside it.
- Guard first: write tests that fail on your base and pass after your change; show the failing lines in the PR body.
- Python: `/Users/vincentpechstein/Downloads/Pixel-lab/ConversationalLanguageLearning/venv/bin/python`. Tests from your worktree: `TZ=UTC PYTHONPATH=. SECRET_KEY=test-secret <python> -m pytest tests/<file> -q -p no:randomly`. Frontend: symlink `web-frontend/node_modules` to `/Users/vincentpechstein/Downloads/Pixel-lab/ConversationalLanguageLearning/.claude/worktrees/batch-2026-11-09/web-frontend/node_modules` (never commit the symlink), then `node --test <file>`, `npx tsc --noEmit -p web-frontend`, `npx eslint <files>`. Run ONLY the tests of the modules you touched plus `ruff check` / eslint on changed files — the owner does not want the long suite locally; CI runs it. There is no `timeout` binary on this Mac.
- No paid model calls and no network services: fake providers and fixtures only. Do not start dev servers.
- A change to season data (`app/data/season/…`) needs a lexicon rebuild — avoid season data unless your task requires it.
- Open draft PRs that touch nearby code (read their diffs with `gh pr diff N` if your files overlap; keep your edits mergeable with them): 869 level floor (`cefr_progress.py`), 870 stored fault (`journey_conversation.py`), 871 render.yaml switches, 872 Courrier (`missions.py`, `pages/missions.tsx`), 873 hook (`living_story.py`, `story_split.py`, `story_teaser*.py`, `episode-headline.ts`, `JourneyTodayCard.tsx`, `TomorrowLine.tsx`), 874 night run (`story_split.py`, `living_story.py`, `journey_latency.py`).
- Commit messages end with the line `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Push your branch and open a **draft** PR against `main` (`gh pr create --draft`), or against the branch you were told to stack on. PR body: which decision proposals you built (top), the fault with the observed example, the mechanism, the change, the guard failing on the base, what you ran, what is NOT verified (nothing has been played on real model output — say so), then `🤖 Generated with [Claude Code](https://claude.com/claude-code)` as the last line. Never merge, enable auto-merge or mark ready. Do not write bare `#123` or `@name` unless it is a real reference you mean.
- If the code differs from the plan, follow the code and say so. If a clean fix needs more than the package describes, stop at the smallest correct change and write the rest up in the PR.

## Final message (under 250 words)
PR URL(s), branch, files changed, decision proposals built, guard results on base vs. branch, what you chose not to do, what is unverified.
