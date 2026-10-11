# WP-133b — run manifest (prepared 2026-10-05)

**Approval.** The owner approved a cap of **US$4 in all** on 2026-10-05. Media generation is excluded.

**When.** The read runs on the `exp/wave3-integration` head once WP-124b (recovery and bridges) and WP-132B (the epilogue) have merged, together with any owner-approved story proposals. The commit and the proposals applied are named in the results.

**Harness.**
- `tests/test_wp133a_live_read.py`. It wraps the owner's season report and records the guard reasons and grammar-weave compliance per draft.
- Production configuration:
  - the real model for the director, critic and reply lanes, with two drafts;
  - the grammar catalogue at v2;
  - the practice day on.
- Correction LLM, panel art and audio are off.
- Learner replies are the harness's scripted lines.

**Runs.** Each run is a fresh learner with its own hard cap, enforced across every `LLMService` call, retries included. The caps total US$4.00. A seeded start uses `SEASON_REPORT_START`, which calls `season.admin.jump_to_day` with the default flags, so a seeded learner's earlier choices are the defaults. That is stated as a limitation of runs 5–8.

| # | Band | Season days | Covers | Cap |
|---|---|---|---|---|
| 1 | A1.1 | 1–10 | T1, g1, T2 | 0.60 |
| 2 | B1.1 | 1–10 | T1, g1, T2 | 0.60 |
| 3 | C1.1 | 1–10 | T1, g1, T2 | 0.60 |
| 4 | A2.1 | 1–10 | regression against the 2026-09-30 read (3 of 8 lost) | 0.50 |
| 5 | B1.1 | 25–32 | T4, g4 | 0.40 |
| 6 | A1.1 | 33–41 | T5, g5 | 0.40 |
| 7 | C1.1 | 42–50 | T6, g6 | 0.40 |
| 8 | B2.1 | 51–62 | T7, g7, the T8 finale, and the start of the epilogue (WP-132B) | 0.50 |

**Stop conditions.**
- When a run reaches its cap it stops, and its report is marked incomplete. Nothing is retried past a cap, and an unspent cap is never moved to another run.
- If a run shows a continuity break, such as a stranger scene, a reset or the Berlin season, the remaining runs still go ahead. The break is recorded as a blocking finding.
- If two runs in a row lose every generated day, the read stops early and the root cause is investigated first.

**What is reported for each run.**
- **Generated days:** attempted and lost, with the guard reason for each loss and the recovery that was served (reprise, bridge or next tentpole).
- **Provider failures, counted separately from recoveries:** the provider failure rate and the successful recovery rate are two numbers, not one.
- **Rule in scene:** the units introduced and the share of drafts that weave the day's unit.
- **The critic:** how often it refused a draft twice and the draft was served anyway.
- **Cost and calls.**

**Rubric for the hand read.** Each criterion is scored pass or concern per generated day, with a quote:
1. continuity with the season: the cast, «tu», no strangers, no resets;
2. the premise is not repeated across days;
3. no teacher-like character dialogue;
4. causal progress: the day's events change something;
5. the level fits: the language matches the band;
6. reactions to varied learner answers are natural;
7. the rule in the scene sounds natural and is not forced.

**Pilot (not part of the paid read).** The protocol for a small observed pilot, from beginners to advanced learners, is to be written separately. It covers:
- a full chosen routine, with actual active time measured by WP-128's `estimate_error` digest;
- comprehension and perceived challenge;
- whether learners come back voluntarily.

The pilot needs real participants and consent, so this session cannot run it.

**Done when (package doc).**
- On an identified candidate, the evaluated cases show no continuity breaks and no false grading.
- Every provider failure recovers honestly.
- The sampled prose passes the rubric.
- Recurring material defects are fixed and checked again.
- Counts, costs and the remaining uncertainty are published, with a cohort recommendation.
- A sample with zero failures is not a guarantee of production reliability.
