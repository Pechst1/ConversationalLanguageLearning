# Structural packages · 9 Nov 2026

Six packages for the structural gaps that have no pull request yet. Read from `origin/main` at `ec60ae44`, the 9 Nov walk reports and the open issues. Each package names the mechanism that keeps producing findings, the structure that replaces it, the stages, and a guard that fails on today's main.

These files are untracked in the shared checkout. Nothing was committed.

| | Package | Replaces | Root causes |
|---|---|---|---|
| S1 | [One day brief](S1-one-day-brief.md) | nine separate choosers of today's rule and words | #146, #280, #576 |
| S2 | [One stored day plan](S2-one-stored-day-plan.md) | two day models, four meanings of «done», three sources of minutes | #143 |
| S3 | [Learner text contract](S3-learner-text-contract.md) | many language resolvers, stored text without a language, instructions guessed from shape | #522, #542 |
| S4 | [The frame](S4-the-frame.md) | hard-coded entries and gates, no error path, one hard-wired mail | none filed |
| S5 | [Season rollover as a job](S5-season-rollover-as-a-job.md) | a writer inside the request, one attempt, guards that drift from their data | findings of #649 |
| S6 | [Return numbers and front door](S6-return-numbers-and-front-door.md) | quality known only from walks, a README for another product | none filed |

## Already covered by draft pull requests (not repeated here)

- What counts as right, failed checks, unverified corrections (#174, #250, #333): the verdict stack #642, #646, #648, #650, #652, #654.
- Scene state and the cast registry (#145, #147): the story-truth stack #635–#645, #647, #651, #653.

Those stacks touch `daily_journey.py`, `living_story.py`, `missions.py` and `pages/atelier.tsx`. S1 and S2 touch the same files.

## Order

1. **Can start now, independent of the open stacks and of each other:** S5 stage 1, S4 stages 1–2, S6 stage 1, S3 stage 1.
2. **After the verdict and story-truth stacks land (or stacked on them):** S1, then S2. S2 reads S1's brief, and both rewrite parts of `daily_journey.py`, so they run one after the other, not side by side.
3. S3 stages 2–4 after S1 stage 1 (they touch the same payloads). S5 stages 2–4, S4 stages 3–5 and S6 stages 2–3 whenever a slot is free.

## Rules for the implementing agent

- Model: Opus 5.5, medium effort. One package stage per pull request, in its own worktree cut from `origin/main`. Draft PRs; nothing merges without the owner.
- Write the failing guard first and show it failing on main in the PR text.
- Fix the mechanism the package names. A finding listed as a child is closed by the guard passing, not by a special case.
- Before handing over, play a full A1 `de` day and a full B1 `en` day end to end; green tests are not enough.
- Each package ends with owner decisions. Where one is open, build the proposal stated there and say so in the PR.
- No new fonts, colours, mascots, rounded geometry, social features or pronunciation scoring.
- A season data change needs a lexicon rebuild; run the suite with `TZ=UTC`.
