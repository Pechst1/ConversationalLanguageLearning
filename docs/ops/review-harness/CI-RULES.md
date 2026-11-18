# Getting a draft PR's CI green (read fully)

Repo: «L'Atelier» (FastAPI `app/`, Next.js `web-frontend/`), GitHub via `gh`. Last night Opus agents opened draft PRs, running only focused local tests. CI's full suite and browser walks now show failures. Your job: for the PRs named in your task, make CI green **without weakening what the PR is for**.

First read the «How to work» and «Standing rules» sections of `/private/tmp/claude-501/-Users-vincentpechstein--claude-spares-spare-8BRKzU/24979350-c568-4d32-a313-976ff75f7f81/scratchpad/PACKAGE-RULES.md`.

Method, per PR
1. `gh pr view N` (read the body: what the PR is for) and `gh pr checks N`. For each failed check get the failing tests: `gh run view --job <job id from the details URL> --log-failed | grep -E "FAILED|Error|assert|✘|not ok|stuck|expected" | head -80` (walk jobs: read the walk's own summary lines; artifacts may hold screenshots — `gh run download <run id>` into your scratch space if you need them).
2. Decide for each failure, with evidence, which it is:
   - **Not this PR:** it also fails on `main` or on an unrelated PR at the same time. Known: (a) the check «PostgreSQL · migrations + row locks» fails everywhere since about 00:30 UTC on 18 Nov with `pg_restore: error: … unrecognized configuration parameter "transaction_timeout"` in `tests/test_production_recovery_pg.py::test_current_schema_dump_restores_and_is_verified` — a CI environment change (a newer pg_dump writing a setting the older server rejects); only the agent whose task says so fixes it, everyone else ignores it. (b) «Browser walk on main» is failing on main itself — compare a walk failure with main's latest walk run before blaming the PR. (c) Walk runs that cross 23:00 UTC fail on the day turnover; a single such failure is re-run (`gh run rerun <run id> --failed`), not diagnosed.
   - **A test that pinned the old behaviour** the PR changes on purpose: update the test to the new behaviour, and say so in the PR body under «tests changed on purpose».
   - **A real regression** the PR introduced: fix the code. If the fix would undo the PR's purpose, stop and describe the conflict instead.
3. Work in the PR's existing worktree (`git -C /Users/vincentpechstein/Downloads/Pixel-lab/ConversationalLanguageLearning worktree list` shows them; branch names are in `gh pr view N --json headRefName`). Reproduce each failing test locally before and after (`TZ=UTC PYTHONPATH=. SECRET_KEY=test-secret /Users/vincentpechstein/Downloads/Pixel-lab/ConversationalLanguageLearning/venv/bin/python -m pytest <file>::<test> -q -p no:randomly`; frontend as the rules file says). CI runs tests in random order (pytest-randomly): a test that passes alone and fails in the shard may be order pollution — check whether it fails on main's runs too before changing anything.
4. Commit (message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`), push to the same branch, add a short «CI fixes» section to the PR body (`gh pr edit N --body-file`, keeping the rest). Keep it a draft. Never merge, never enable auto-merge, never mark ready. For a PR stacked on another PR's branch, fix the lower one first and merge the lower branch into the upper (`git merge`, no force-push, no rebase of pushed commits).
5. Do not wait for CI to finish after pushing (it takes 15–30 minutes). Report what you pushed and what you expect.

No paid model calls. Do not start dev servers. Do not run the full Python suite locally (shards take 10 minutes each in CI) — run the failing tests and the files of the modules you touch.

Final message (under 250 words): per PR — each failed check, its cause class (not this PR / pinned old behaviour / regression), what you changed, the commit sha; anything you could not resolve.
