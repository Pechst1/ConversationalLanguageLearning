---
name: night-shift
description: Work the improvement loop's queue at night. Take every `queue:ready` walk-finding issue up to tonight's cap, fix each cluster on its own branch and worktree, verify each PR independently, and write the morning digest. Never merges. Use for the nightly "Night shift" routine or when asked to "work the queue".
---

# Night shift

The walks fill the queue (`walk-finding` issues with `queue:ready`, see
`docs/ops/improvement-loop.md`); the night shift empties it. It opens PRs and never
merges them unless the routine passes `autoMerge: true`: then the digest merges the
verified small code fixes onto a green main, and the owner reviews the story lane.

## Run it

If the Workflow tool is available, run the saved workflow:

```
Workflow name: night-shift   args: {"date": "<YYYY-MM-DD>", "maxFixes": 15, "maxStory": 3, "maxRootCauses": 3, "wave": 5}
```

**GitHub access:** cloud sessions block GraphQL, so `gh issue …` and `gh pr …` fail.
Use `scripts/loop/loop_queue.py` (REST through `gh api`): `show N`, `comment N`,
`open-night-prs`, `pr-create`, `pr-diff N`, `pr-unready N`, plus the queue verbs below;
or the GitHub MCP tools.

**Test environment:** the SessionStart hook (`scripts/loop/session_start.sh`) prepares
it in every cloud session. In a new worktree run `bash scripts/loop/setup_env.sh && source
~/.venvs/atelier/bin/activate` (seconds: the venv is shared, node_modules is linked), then
`python -m pytest` from the worktree root.

**Proof:** `python scripts/loop/red_green.py --base origin/main` in a checkout of the PR
branch. PROVEN means the PR's tests fail with its other changes reverted to main and
pass with them. The fixer runs it before opening a PR, the verifier runs it again.

Without the Workflow tool, do the same steps with the Agent tool:

1. **Plan** (one agent, or yourself). Count open `claude/night-*` PRs
   (`loop_queue.py open-night-prs`); at 30 or more, plan nothing new. Root-cause issues
   come first: up to 3, each its own cluster with its ready children. Otherwise read `python scripts/loop/loop_queue.py ready` and each
   issue's "Done when" comment, find the files each fix will touch, group issues that
   share files into one cluster (at most 3 issues, one lane), order by severity then
   size, and keep at most 15 clusters with at most 3 story clusters.
2. **Fix** in waves of at most 5 agents (`isolation: "worktree"`; more at once
   stall). Give each agent the fixer brief from `.claude/workflows/night-shift.js`
   (`fixPrompt`): branch `claude/night-<date>-<first issue>` from origin/main, claim,
   reproduce, fix, add the test that would have caught it, run the focused checks,
   prove red/green, push, open the PR, `mark-pr`, or `release` with a reason.
3. **Verify** each PR (never skip this) with a fresh agent that did not write it (`verifyPrompt`): it
   checks the diff against every done-when and re-runs `red_green.py`. Only the verifier
   adds `loop:merge-ready`, and only when it is ok; otherwise `loop_queue.py pr-reject`
   closes the PR and gives its issues back to the queue with the notes. A PR whose verify did not finish never carries the label.
4. **Digest**: `python scripts/loop/loop_queue.py merge-ready` (lists only) and
   `python scripts/loop/loop_queue.py digest --date <date>`.

## Lanes

| | code lane | story lane |
|---|---|---|
| what | UI, drills, API, copy | model prompts, guards, authored story lines |
| PR | ready for review; `loop:merge-ready` when small, green-checkable and outside owner-only paths | always a draft with `needs-owner-review` |
| proof | test or walk assertion that fails without the fix | a guard plus a test that feeds the walk's exact text; no paid model calls |

## Rules

- Never push to main, deploy or change production settings. Merge only through the digest's `merge-ready --merge`, and only when the routine's args say `autoMerge: true`.
- A fix without a test that fails first is not a fix. Never "fix" a walk failure by loosening the walk driver.
- Claim before working, and always end an issue in `queue:pr` or back in `queue:ready` with a reason. A `queue:working` issue in the morning digest means an agent stopped mid-way.
- One cluster per file set: two agents never edit the same file in one night.
- Run focused tests only (the backend suite runs in random order); CI runs the full suite.
