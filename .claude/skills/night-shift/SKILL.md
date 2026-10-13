---
name: night-shift
description: Work the improvement loop's queue at night. Take every `queue:ready` walk-finding issue up to tonight's cap, fix each cluster on its own branch and worktree, verify each PR independently, and write the morning digest. Never merges. Use for the nightly "Night shift" routine or when asked to "work the queue".
---

# Night shift

The walks fill the queue (`walk-finding` issues with `queue:ready`, see
`docs/ops/improvement-loop.md`); the night shift empties it. It opens PRs and never
merges them: the owner merges in the morning, starting with the ones the digest lists
as ready to merge.

## Run it

If the Workflow tool is available, run the saved workflow:

```
Workflow name: night-shift   args: {"date": "<YYYY-MM-DD>", "maxFixes": 8, "maxStory": 2, "wave": 4}
```

Without the Workflow tool, do the same steps with the Agent tool:

1. **Plan** (one agent, or yourself). Count open `claude/night-*` PRs; at 10 or more,
   plan nothing new. Otherwise read `python scripts/loop/loop_queue.py ready` and each
   issue's "Done when" comment, find the files each fix will touch, group issues that
   share files into one cluster (at most 3 issues, one lane), order by severity then
   size, and keep at most 8 clusters with at most 2 story clusters.
2. **Fix** in waves of at most 4 agents (`isolation: "worktree"`; more than 4 at once
   stall). Give each agent the fixer brief from `.claude/workflows/night-shift.js`
   (`fixPrompt`): branch `claude/night-<date>-<first issue>` from origin/main, claim,
   reproduce, fix, add the test that would have caught it, run the focused checks,
   push, open the PR, `mark-pr`, or `release` with a reason.
3. **Verify** each PR with a fresh agent that did not write it (`verifyPrompt`): it
   checks the diff against every done-when and, if it is not ok, removes
   `loop:merge-ready`, turns the PR into a draft and comments why.
4. **Digest**: `python scripts/loop/loop_queue.py merge-ready` (lists only) and
   `python scripts/loop/loop_queue.py digest --date <date>`.

## Lanes

| | code lane | story lane |
|---|---|---|
| what | UI, drills, API, copy | model prompts, guards, authored story lines |
| PR | ready for review; `loop:merge-ready` when small, green-checkable and outside owner-only paths | always a draft with `needs-owner-review` |
| proof | test or walk assertion that fails without the fix | a guard plus a test that feeds the walk's exact text; no paid model calls |

## Rules

- Never push to main, merge, deploy or change production settings. Merging is the owner's call; `loop_queue.py merge-ready --merge` exists for the owner, not for the night shift.
- Claim before working, and always end an issue in `queue:pr` or back in `queue:ready` with a reason. A `queue:working` issue in the morning digest means an agent stopped mid-way.
- One cluster per file set: two agents never edit the same file in one night.
- Run focused tests only (the backend suite runs in random order); CI runs the full suite.
