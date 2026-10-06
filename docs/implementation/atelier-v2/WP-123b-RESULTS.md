# WP-123b: walk coverage, a year of reviews, and a data audit (2026-10-06)

**Branch.** `exp/wp123b`, built on `d3486fa`, the Wave 3 head. WP-123b gates nothing.

## Summary
- **La Forge is in the walk now.** `WALK_FORGE=1` plays it from the after-day chip, at the drill's cadence. Its first run found four defects, one of them serious:
  - **A placed learner is demoted once they have about 40 graded attempts.** From then on, the placement floor gives way to the measured level. Six of 15 lives fell from A2.1–C1.1 to A1.1–B1.1 between day 3 and day 5. One example: a C1 learner was shown «A1.1 · 45 %».
  - The 5-minute chip lasts 5–14 minutes on the walk's clock.
  - German C1 learners read English instructions in La Forge: 20–52 % of their items.
  - A give-up («je ne sais pas») is graded «partial». When it is a transform, it comes back days later as a journey repair.

  Forge play is therefore **opt-in** until these are fixed. The default walk stays the Wave 3 walk and is green.
- **Forced outages** run as a documented command: `WALK_FAIL_RATE=1 … -k b1-en-average`. That life passes, and the season reaches the epilogue on day 28. Every letter in the walk already goes through the Courrier's provider-off path.
- **The forecast after day 14 is now real.** Seven evidence timestamp columns now take the app's clock (no migration). Before, every life showed the 730-day cap from day 15 on. Now lives show 46–432 days, and the struggling learners' slower pace is visible. The fix found a second artefact, which is outside my lease, so I wrote a patch for it: the first fortnight counts the vocabulary check's credits as intake (≈200 words/day at B2).
- **The 365-day workload.** A learner who clears the whole pile never sees more than 150 words due, with one exception (one day for C1 struggling). Keeping up costs 2–7 minutes a drill day for strong learners and 3–10 for average ones. Struggling learners need 11–28 minutes per drill day by month 12, and they drill every other day.

  The app shows one 30-card session. With that cap, the pile grows without bound:
  - for a fresh A1 learner, from month 9;
  - for every placed learner (A2–C1, the credit's light checks), from month 2–3 when average.

  The throttle never engages: it assumes about 135 reviews a day of capacity. A usability target is proposed below.
- **The data question.** Two of the three defect classes cannot exist in a database deployed from `origin/main`:
  - the band-check credit flood: `band_check` and the `provenance` column are not on `main`;
  - the WP-125A omission errata: the code that writes them **is** on `main`, so production can hold them;
  - the review-fix-7 errata: possible, but mostly unprovable from the stored metadata.

  `scripts/audit_experience_review_rows.py` answers the question read only, on any database. It is proven on a disposable fixture.

## 1. Coverage

### 1.1 La Forge in the life walk
Each day, `tests/experience_walk.py` reads the after-day `forge` entry that Home shows. If the entry is not folded and `WALK_FORGE=1` is set, the quality plays it at the drill's cadence: strong and average every day, struggling every other day.

Each séance is played the way `pages/atelier.tsx` drives it:
- `POST /atelier/sessions` with the chip's concept and budget (`origin=after_day`);
- every item the forge names, answered right at the quality's accuracy;
- `POST …/complete`.

The walk records the séance and times it on the journey's clock (`time_forge`). Wrong answers are a distractor (tap rounds) or «je ne sais pas» (typed rounds).

**Checks** (`tests/walk_checks_wp123b.py`, unit-tested in `tests/test_walk_checks_wp123b.py`, wired in `test_experience_walk.py`). All are no-ops without Forge play:
- the séance opens, every answer is graded, it ends and it is filed;
- the séance works on the rule the chip names;
- it takes ≤ 1.5 × its budget;
- no English reaches a German learner;
- a give-up is never graded correct.

**The run.** `WALK_FORGE=1`, all 15 lives: **15 failed**. I ran it twice. The second run was alone and took **33 min 51 s**, against about 18 min for the default walk. It reproduced every finding below: the same six demotions and the same day-30 levels within noise. The failures, counted over the records offline:

| Problem | Lives | Owner |
|---|---|---|
| La Forge over 1.5× its 5-min budget (2–24 séances a life) | 15 / 15 | La Forge length (`forge.seance_length` × `seconds_per_item`) |
| English instructions for German C1 learners (`Use the target grammar visibly in your answer.`, `Rewrite 'Je pratique' as …`; 20–52 % of their items) | 3 / 3 C1 | La Forge's C1 exercise sets (legacy, English-authored) |
| Level demoted after ~40 graded attempts (cascades into the journey checks below) | 6 / 15 | `cefr_progress` release rule, owner (WP-134) |
| A Forge give-up came back as a journey repair «Schreib das richtig auf Französisch: je ne sais pas» (`check_repairs`) | a2 strong | atelier/forge erratum path: review fix 7 was applied to the journey only |
| Knock-on journey checks: interleaving below 30 % (b1/b2/c1 struggling), words above band (4 lives), one A1 day over budget | 7 | follow from the demotion and the changed learner state; re-check after the fixes |

In every life, the give-ups typed in output rounds were graded «partial» (11–60 a life). None was graded «correct».

| Life | séances | items / séance | ≤ 2 items | min / séance (mean · max) | answers graded correct | give-ups graded «partial» | level on day 30 (with La Forge → without) |
|---|---:|---:|---:|---|---:|---:|---|
| a1-de-fresh-average | 30 | 13.3 | 1 | 7.3 · 12.8 | 70% | 47 | A1.1 · 34 % → A1.1 · 34 % |
| a1-de-fresh-strong | 30 | 10.2 | 0 | 4.9 · 8.6 | 86% | 17 | A1.1 · 42 % → A1.1 · 40 % |
| a1-de-fresh-struggling | 15 | 17.4 | 1 | 10.2 · 14.9 | 44% | 53 | A1.1 · 13 % → A1.1 · 12 % |
| a2-de-placed-average | 30 | 11.7 | 2 | 6.7 · 12.0 | 68% | 60 | A2.1 · 29 % → A2.1 · 36 % |
| a2-de-placed-strong | 30 | 9.5 | 1 | 5.0 · 8.5 | 88% | 18 | A2.1 · 35 % → A2.1 · 25 % |
| a2-de-placed-struggling | 15 | 17.9 | 1 | 11.1 · 17.2 | 45% | 45 | A1.1 · 45 % → A2.1 · 7 % |
| b1-en-average | 30 | 16.6 | 0 | 7.6 · 12.3 | 70% | 59 | B1.1 · 31 % → B1.1 · 30 % |
| b1-en-strong | 30 | 15.9 | 0 | 6.7 · 11.1 | 89% | 21 | B1.1 · 38 % → B1.1 · 30 % |
| b1-en-struggling | 15 | 19.2 | 0 | 13.8 · 22.6 | 48% | 43 | A1.1 · 45 % → B1.1 · 8 % |
| b2-en-average | 30 | 18.7 | 0 | 7.5 · 11.0 | 74% | 31 | B1.1 · 45 % → B2.1 · 23 % |
| b2-en-strong | 30 | 13.2 | 0 | 4.8 · 9.2 | 91% | 21 | B2.1 · 31 % → B2.1 · 26 % |
| b2-en-struggling | 15 | 23.2 | 0 | 10.7 · 13.9 | 49% | 12 | A1.1 · 45 % → B2.1 · 12 % |
| c1-de-average | 30 | 20.9 | 0 | 9.4 · 11.9 | 76% | 39 | B1.1 · 45 % → C1.1 · 22 % |
| c1-de-strong | 30 | 14.5 | 0 | 5.5 · 10.7 | 89% | 23 | C1.1 · 25 % → C1.1 · 25 % |
| c1-de-struggling | 15 | 23.2 | 0 | 11.8 · 15.9 | 51% | 11 | A1.1 · 45 % → C1.1 · 15 % |

**The demotion, traced.** Every demoted life changes on the day its graded attempts pass about 40. For example, `b2-en average` moves from day 3 to day 6 as `B2.1 · 0 % (placement)` → `A2.1 · 45 % (measured)` → `A2.2` → `B1.1`. The cause is `cefr_progress._release_floor`: a level that stands only on a placement is «a floor until 40 attempts, then the evidence decides». A placed learner's evidence closes no band in a week, so the level falls to the highest band the evidence closes. The strong lives were not demoted. The average and struggling lives at A2+ were. This is a claims question (WP-134) for the owner. The walk without La Forge never reaches 40 attempts in 30 days, which is why it never showed.

**Reproduce:** `WALK_FORGE=1 WALK=1 EXPERIENCE_OUT=<dir> $PY -m pytest tests/test_experience_walk.py -m walk`.

**To wire once fixed:** flip the default in `test_experience_walk.py` to `WALK_FORGE = os.environ.get("WALK_FORGE", "1") == "1"`. The checks are already wired.

### 1.2 Provider outages
- **The story.** WP-124b's `WALK_FAIL_RATE` refuses every scene draft on the days it picks. The documented forced-outage life is `WALK_FAIL_RATE=1 WALK=1 … -k "b1-en-average"`: it **passed** (59 s, because no generation runs). The season advanced through all seven gaps, each recorded as shortened, and reached the epilogue (`e1.a`) on day 28.
- **The letters.** `ATELIER_LLM_ENABLED` is off in tests, so every letter in every life already runs on the Courrier's provider-off path: authored letters and the deterministic corrector. There is no separate letter-outage switch to add.
- **The command set** is now in `tests/test_experience_walk.py`'s docstring. It covers 15 lives, the PR three, the forced outage, La Forge and `LIFE_DAYS`.

### 1.3 Timestamps that follow the test clock
`server_default=func.now()` is the database's clock, and `app.core.test_clock` cannot move it. The columns that feed the forecast, the CEFR signals (active days, recent errors and scores, today's activity) and the reading-known words now also take a Python-side default, `app.db.models._clock.app_now()`. The test clock swaps it like any `app.*` module's `datetime`. `server_default` is unchanged, so there is **no migration**. In production the two clocks agree.

| Model | Columns |
|---|---|
| `UserVocabularyProgress` (`progress.py`) | `created_at`, `updated_at` (+ `onupdate`), `first_seen_date` |
| `UserGrammarProgress` (`grammar.py`) | `created_at`, `updated_at` (+ `onupdate`) |
| `UserError` (`error.py`) | `created_at`, `updated_at` (+ `onupdate`) |
| `AtelierAttempt` (`atelier.py`) | `created_at` |
| `RealWorldMissionAttempt` (`mission.py`) | `created_at` |
| `GraphicNovelAttempt` (`graphic_novel.py`) | `created_at` |
| `WordInteraction` (`session.py`) | `created_at` (the reading-known words need ≥ 3 distinct days) |

The regression test is `tests/test_wp123b_clock_defaults.py`. `ReviewLog.review_date` and `DailyJourney.completed_at` are always set by the app, so they needed nothing.

**The measured forecast, before → after.** «Before» is the Wave 3 record (`w3b`); «after» is this branch's default walk. Each cell shows the forecast's days to the next sub-band and the measured words a day:

| Life | day 14 before → after | day 15 before → after | day 20 before → after | day 30 before → after |
|---|---|---|---|---|
| a1-de-fresh-average | 179 · 8.3 w/d → 76 · 8.9 w/d | 163 · 9.4 w/d → 76 · 8.1 w/d | 730 (cap) · 0.0 w/d → 88 · 8.3 w/d | 730 (cap) · 0.0 w/d → 143 · 8.1 w/d |
| a1-de-fresh-strong | 91 · 8.3 w/d → 60 · 8.9 w/d | 91 · 9.4 w/d → 60 · 8.8 w/d | 730 (cap) · 0.0 w/d → 60 · 8.4 w/d | 730 (cap) · 0.0 w/d → 46 · 7.9 w/d |
| a1-de-fresh-struggling | 412 · 3.5 w/d → 368 · 3.6 w/d | 412 · 3.6 w/d → 184 · 3.0 w/d | 730 (cap) · 0.0 w/d → 226 · 2.7 w/d | 730 (cap) · 0.0 w/d → 144 · 2.7 w/d |
| a2-de-placed-average | 131 · 48.3 w/d → 139 · 48.9 w/d | 131 · 49.4 w/d → 133 · 8.6 w/d | 730 (cap) · 0.0 w/d → 184 · 8.3 w/d | 730 (cap) · 0.0 w/d → 114 · 8.4 w/d |
| a2-de-placed-strong | 122 · 48.4 w/d → 69 · 48.9 w/d | 95 · 49.5 w/d → 69 · 8.0 w/d | 730 (cap) · 0.0 w/d → 79 · 8.1 w/d | 730 (cap) · 0.0 w/d → 69 · 7.9 w/d |
| a2-de-placed-struggling | 364 · 21.7 w/d → 198 · 21.5 w/d | 400 · 22.0 w/d → 198 · 21.4 w/d | 730 (cap) · 0.0 w/d → 169 · 3.1 w/d | 730 (cap) · 0.0 w/d → 387 · 2.9 w/d |
| b1-en-average | 124 · 112.1 w/d → 162 · 111.9 w/d | 124 · 112.7 w/d → 162 · 7.6 w/d | 730 (cap) · 0.0 w/d → 118 · 7.7 w/d | 730 (cap) · 0.0 w/d → 126 · 7.5 w/d |
| b1-en-strong | 109 · 112.3 w/d → 72 · 112.2 w/d | 85 · 112.9 w/d → 72 · 7.6 w/d | 730 (cap) · 0.0 w/d → 62 · 7.7 w/d | 730 (cap) · 0.0 w/d → 51 · 7.6 w/d |
| b1-en-struggling | 142 · 76.9 w/d → 125 · 76.8 w/d | 116 · 77.2 w/d → 138 · 3.7 w/d | 730 (cap) · 0.0 w/d → 209 · 3.4 w/d | 730 (cap) · 0.0 w/d → 226 · 2.4 w/d |
| b2-en-average | 125 · 206.7 w/d → 135 · 207.3 w/d | 157 · 207.9 w/d → 177 · 7.4 w/d | 730 (cap) · 0.0 w/d → 125 · 7.4 w/d | 730 (cap) · 0.0 w/d → 116 · 7.4 w/d |
| b2-en-strong | 90 · 206.9 w/d → 85 · 207.4 w/d | 113 · 208.0 w/d → 85 · 7.4 w/d | 730 (cap) · 0.0 w/d → 79 · 7.4 w/d | 730 (cap) · 0.0 w/d → 69 · 7.4 w/d |
| b2-en-struggling | 231 · 77.4 w/d → 123 · 77.2 w/d | 231 · 77.8 w/d → 147 · 76.6 w/d | 730 (cap) · 0.0 w/d → 228 · 3.3 w/d | 730 (cap) · 0.0 w/d → 208 · 2.9 w/d |
| c1-de-average | 109 · 318.4 w/d → 182 · 319.0 w/d | 123 · 319.6 w/d → 182 · 7.4 w/d | 730 (cap) · 0.0 w/d → 133 · 7.4 w/d | 730 (cap) · 0.0 w/d → 122 · 7.4 w/d |
| c1-de-strong | 109 · 318.5 w/d → 92 · 319.1 w/d | 121 · 319.6 w/d → 135 · 7.4 w/d | 730 (cap) · 0.0 w/d → 130 · 7.4 w/d | 730 (cap) · 0.0 w/d → 120 · 7.4 w/d |
| c1-de-struggling | 223 · 150.4 w/d → 144 · 150.2 w/d | 223 · 150.8 w/d → 118 · 149.6 w/d | 730 (cap) · 0.0 w/d → 270 · 3.9 w/d | 730 (cap) · 0.0 w/d → 432 · 2.4 w/d |

Before, every life read the 730-day cap from day 15, because the 14-day window held no card. After:
- the strong and average lives settle at 46–143 days;
- the struggling lives at 144–432, because their intake drops to 2–4 words a day.

The 15 default lives with the fix **pass** (5 + 10 in two runs). Their other day-30 numbers match Wave 3 within noise:
- 8 tentpole headlines everywhere;
- rules 7–16;
- new words 55–239;
- due peak 18–45.

**A second artefact, outside my lease (patch below).** Days 1–14 of a placed learner read 46 (A2) to 319 (C1) «words a day». `level_forecast.measured_intake` counts the vocabulary check's credited cards as intake, and a week later as a perfectly retained sample. From day 15 the credit leaves the window, so the forecast jumps. Patch: [`WP-123b-forecast-credit.patch`](WP-123b-forecast-credit.patch), described in §5.

## 2. Workload: 365 days of the word drill
`scripts/simulate_workload_365.py` simulates the drill on the app's own rules:
- **scheduler:** `VocabularyFSRS`, retention 0.87;
- **session:** the drill's session (30 due + 8 new; struggling every other day);
- **throttle:** the intake throttle (`intake_throttle.decide` / `intake_factor` against Régulier capacity);
- **credit:** the WP-127 credit on day 1 with `band_check.credit_schedule`, for the sub-bands each quality passed in the walk. That is 572 (A2) to 4,364 (C1) cards.

The seconds per card are the walk's measured means: 8.6 / 9.8 / 12.5 s. There are two retention assumptions:
- **`walk`:** the walk's accuracy. Drill 92 / 80 / 62 %; a credited word's light check 97 / 92 / 78 %.
- **`fsrs`:** recall = FSRS retrievability × 1.0 / 0.92 / 0.75.

Words reviewed inside the journey and La Forge are not modelled, and neither are grammar or errata (the Rappel). So the real pile is somewhat smaller.

Month 1 agrees with the walk. The walk's due peak is 16–45 (p90 ≈ 25–30 for average); the simulation's month-1 p90 is 10–27 and its max 10–33. The tests are in `tests/test_wp123b_workload_sim.py`: deterministic, the credit is exactly the walk's sub-bands, no credited word comes back before its window, the session cap and cadence hold, and an uncapped learner clears the pile.

**A. True due words a day, median / p90 / max** — walk retention, WP-127 credit, one 30-due session a day (today's product):

| Life | credited | M1 | M2 | M3 | M4 | M5 | M6 | M7 | M8 | M9 | M10 | M11 | M12 |
|---|---:|---|---|---|---|---|---|---|---|---|---|---|---|
| A1 strong | 0 | 8 / 10 / 10 | 16 / 18 / 20 | 19 / 21 / 24 | 19 / 21 / 23 | 20 / 22 / 23 | 20 / 22 / 23 | 19 / 21 / 23 | 20 / 22 / 26 | 22 / 31 / 33 | 28 / 31 / 34 | 28 / 34 / 36 | 29 / 33 / 33 |
| A1 average | 0 | 9 / 12 / 15 | 17 / 22 / 23 | 19 / 23 / 26 | 21 / 23 / 25 | 23 / 27 / 32 | 24 / 28 / 31 | 25 / 30 / 36 | 23 / 29 / 32 | 28 / 49 / 55 | 52 / 59 / 65 | 48 / 56 / 70 | 85 / 93 / 100 |
| A1 struggling | 0 | 10 / 14 / 15 | 12 / 17 / 23 | 16 / 24 / 26 | 20 / 27 / 29 | 28 / 38 / 41 | 30 / 41 / 45 | 54 / 65 / 67 | 62 / 77 / 82 | 66 / 77 / 78 | 69 / 78 / 79 | 98 / 113 / 119 | 109 / 117 / 119 |
| A2 strong | 572 | 9 / 14 / 17 | 22 / 28 / 29 | 25 / 29 / 36 | 21 / 25 / 26 | 22 / 26 / 33 | 22 / 24 / 26 | 22 / 26 / 32 | 20 / 25 / 27 | 24 / 32 / 38 | 32 / 39 / 44 | 36 / 44 / 61 | 64 / 78 / 86 |
| A2 average | 572 | 10 / 16 / 20 | 23 / 31 / 33 | 33 / 42 / 44 | 28 / 46 / 56 | 34 / 61 / 64 | 39 / 55 / 59 | 37 / 54 / 56 | 33 / 51 / 56 | 44 / 58 / 62 | 128 / 145 / 152 | 103 / 133 / 149 | 120 / 148 / 161 |
| A2 struggling | 259 | 9 / 14 / 15 | 13 / 21 / 27 | 27 / 40 / 41 | 34 / 53 / 55 | 50 / 64 / 76 | 68 / 92 / 102 | 84 / 94 / 102 | 75 / 84 / 86 | 66 / 87 / 94 | 80 / 85 / 92 | 108 / 120 / 126 | 125 / 133 / 140 |
| B1 strong | 1465 | 9 / 16 / 17 | 26 / 32 / 34 | 29 / 34 / 37 | 25 / 35 / 39 | 27 / 30 / 37 | 25 / 32 / 36 | 25 / 31 / 35 | 22 / 27 / 32 | 29 / 51 / 62 | 86 / 93 / 98 | 58 / 65 / 70 | 108 / 194 / 208 |
| B1 average | 1465 | 11 / 20 / 23 | 36 / 51 / 55 | 65 / 85 / 91 | 72 / 81 / 89 | 63 / 109 / 120 | 70 / 109 / 122 | 68 / 115 / 123 | 78 / 151 / 161 | 84 / 145 / 166 | 124 / 169 / 179 | 119 / 125 / 132 | 205 / 217 / 227 |
| B1 struggling | 1031 | 9 / 12 / 15 | 19 / 34 / 40 | 42 / 63 / 65 | 74 / 98 / 101 | 122 / 160 / 165 | 180 / 192 / 203 | 158 / 198 / 206 | 137 / 146 / 151 | 134 / 139 / 144 | 164 / 200 / 206 | 221 / 249 / 260 | 270 / 278 / 287 |
| B2 strong | 2801 | 9 / 22 / 28 | 37 / 74 / 81 | 107 / 117 / 135 | 72 / 130 / 138 | 35 / 51 / 53 | 131 / 182 / 194 | 119 / 171 / 177 | 54 / 93 / 94 | 174 / 236 / 242 | 155 / 191 / 198 | 114 / 139 / 147 | 110 / 141 / 187 |
| B2 average | 2801 | 10 / 22 / 25 | 50 / 119 / 144 | 220 / 233 / 236 | 139 / 210 / 240 | 105 / 118 / 123 | 134 / 268 / 291 | 218 / 262 / 289 | 92 / 134 / 148 | 132 / 144 / 157 | 292 / 308 / 319 | 290 / 298 / 305 | 227 / 276 / 302 |
| B2 struggling | 1031 | 11 / 15 / 16 | 12 / 18 / 22 | 16 / 23 / 25 | 30 / 42 / 50 | 66 / 75 / 83 | 85 / 108 / 120 | 141 / 154 / 156 | 171 / 177 / 183 | 179 / 199 / 201 | 234 / 266 / 274 | 334 / 371 / 381 | 392 / 403 / 406 |
| C1 strong | 4364 | 9 / 24 / 27 | 63 / 112 / 115 | 181 / 210 / 214 | 140 / 154 / 165 | 178 / 202 / 211 | 166 / 183 / 195 | 125 / 163 / 175 | 156 / 165 / 173 | 162 / 222 / 234 | 205 / 233 / 241 | 290 / 307 / 313 | 265 / 277 / 284 |
| C1 average | 4364 | 11 / 22 / 27 | 50 / 133 / 154 | 246 / 268 / 284 | 259 / 292 / 296 | 236 / 242 / 246 | 240 / 288 / 306 | 296 / 312 / 320 | 248 / 264 / 275 | 220 / 232 / 241 | 260 / 315 / 334 | 372 / 441 / 450 | 450 / 478 / 496 |
| C1 struggling | 2048 | 10 / 13 / 15 | 11 / 16 / 21 | 15 / 22 / 24 | 82 / 121 / 137 | 154 / 171 / 180 | 206 / 232 / 246 | 316 / 345 / 359 | 408 / 442 / 460 | 472 / 493 / 502 | 509 / 565 / 582 | 658 / 683 / 689 | 742 / 796 / 816 |
The learner who **clears the whole pile every drill day** (table B in the script's output) stays far below that, all year. Strong and average learners stay at or under a monthly median of 63 due. Struggling learners reach 113 as a median, 142 at p90 and 153 at most, the latter on one day of C1 struggling. The pile in table A is the 30-card cap, not the scheduler.

**C. Review minutes a drill day to keep up (B), median / p90:**

| Life | credited | M1 | M2 | M3 | M4 | M5 | M6 | M7 | M8 | M9 | M10 | M11 | M12 |
|---|---:|---|---|---|---|---|---|---|---|---|---|---|---|
| A1 strong | 0 | 1.1 / 1.4 | 2.4 / 2.6 | 2.7 / 3.0 | 2.7 / 3.0 | 2.8 / 3.2 | 2.8 / 3.2 | 2.7 / 3.0 | 2.9 / 3.2 | 3.2 / 4.3 | 4.0 / 4.4 | 4.0 / 4.3 | 4.2 / 4.6 |
| A1 average | 0 | 1.5 / 2.0 | 2.8 / 3.6 | 3.1 / 3.8 | 3.4 / 3.8 | 3.8 / 4.4 | 3.8 / 4.7 | 3.9 / 4.6 | 4.1 / 4.9 | 4.6 / 6.0 | 5.2 / 6.2 | 5.6 / 6.4 | 5.9 / 6.7 |
| A1 struggling | 0 | 2.3 / 2.9 | 2.9 / 4.6 | 4.0 / 5.4 | 5.0 / 5.8 | 6.0 / 7.1 | 6.5 / 7.9 | 7.7 / 8.3 | 8.3 / 10.4 | 8.5 / 10.2 | 10.4 / 12.1 | 10.2 / 11.7 | 11.4 / 12.9 |
| A2 strong | 572 | 1.3 / 2.0 | 3.1 / 4.0 | 3.6 / 4.0 | 3.0 / 3.6 | 3.2 / 3.4 | 3.2 / 3.6 | 3.0 / 3.7 | 2.9 / 3.6 | 3.4 / 4.3 | 4.3 / 4.7 | 4.4 / 5.2 | 4.4 / 5.4 |
| A2 average | 572 | 1.7 / 2.6 | 3.8 / 5.1 | 4.7 / 5.7 | 4.4 / 5.2 | 4.6 / 5.2 | 4.7 / 5.7 | 4.4 / 5.6 | 4.6 / 5.6 | 5.5 / 6.4 | 5.9 / 7.5 | 6.2 / 7.2 | 6.7 / 7.8 |
| A2 struggling | 259 | 1.9 / 2.9 | 3.1 / 5.0 | 6.0 / 7.1 | 6.7 / 8.3 | 8.1 / 9.6 | 10.0 / 11.5 | 8.8 / 11.0 | 9.4 / 10.6 | 9.6 / 10.6 | 10.4 / 11.7 | 12.3 / 14.0 | 11.8 / 14.2 |
| B1 strong | 1465 | 1.3 / 2.3 | 3.6 / 4.3 | 4.0 / 4.6 | 3.6 / 4.2 | 3.9 / 4.2 | 3.4 / 4.3 | 3.6 / 3.9 | 3.4 / 3.7 | 3.7 / 5.0 | 4.7 / 5.3 | 4.4 / 5.4 | 4.9 / 6.0 |
| B1 average | 1465 | 1.8 / 3.3 | 4.2 / 5.7 | 5.6 / 6.5 | 5.5 / 6.0 | 5.6 / 7.2 | 5.1 / 6.4 | 5.6 / 6.7 | 6.0 / 6.7 | 5.8 / 7.2 | 6.8 / 7.7 | 7.1 / 8.2 | 7.4 / 8.8 |
| B1 struggling | 1031 | 2.1 / 2.5 | 4.8 / 7.3 | 6.9 / 8.5 | 9.4 / 10.4 | 11.5 / 13.1 | 12.9 / 15.2 | 12.5 / 15.2 | 13.8 / 15.4 | 16.7 / 18.3 | 17.9 / 20.0 | 19.4 / 20.4 | 18.3 / 21.5 |
| B2 strong | 2801 | 1.3 / 3.2 | 4.2 / 5.2 | 4.9 / 5.4 | 4.4 / 5.0 | 4.4 / 5.0 | 4.4 / 6.2 | 4.0 / 5.7 | 4.1 / 5.0 | 4.9 / 5.9 | 5.2 / 6.7 | 5.3 / 6.5 | 5.7 / 7.3 |
| B2 average | 2801 | 1.6 / 3.6 | 5.6 / 6.9 | 6.9 / 7.8 | 6.3 / 7.4 | 6.4 / 7.5 | 7.0 / 7.8 | 6.3 / 8.3 | 6.1 / 7.7 | 7.0 / 8.8 | 8.6 / 10.1 | 7.8 / 9.0 | 8.2 / 10.5 |
| B2 struggling | 1031 | 2.5 / 3.1 | 2.9 / 4.2 | 4.0 / 5.0 | 6.7 / 7.3 | 8.8 / 9.4 | 11.0 / 12.5 | 12.1 / 13.8 | 14.4 / 15.8 | 15.0 / 18.3 | 16.5 / 17.7 | 18.8 / 20.4 | 20.5 / 22.9 |
| C1 strong | 4364 | 1.3 / 3.4 | 4.6 / 5.7 | 5.4 / 5.9 | 5.0 / 5.9 | 5.3 / 6.0 | 5.4 / 6.6 | 4.6 / 6.5 | 4.9 / 6.2 | 5.1 / 6.7 | 6.0 / 7.7 | 6.2 / 7.7 | 6.6 / 8.0 |
| C1 average | 4364 | 1.8 / 3.6 | 5.5 / 7.0 | 7.6 / 8.8 | 7.3 / 8.3 | 8.2 / 9.3 | 8.2 / 9.6 | 8.2 / 9.8 | 8.2 / 10.3 | 8.7 / 10.0 | 9.5 / 10.5 | 10.3 / 12.2 | 10.3 / 12.7 |
| C1 struggling | 2048 | 2.1 / 2.7 | 2.5 / 3.5 | 3.5 / 4.8 | 10.0 / 11.0 | 11.0 / 12.1 | 14.0 / 15.6 | 15.6 / 17.3 | 18.1 / 21.5 | 19.2 / 20.6 | 21.2 / 24.0 | 25.0 / 26.9 | 28.1 / 30.4 |
*Struggling learners drill every other day: halve their minutes for a per-calendar-day figure.*

**D. Without the WP-127 credit** (30-due session), true due median / p90 / max:

| Life | credited | M1 | M3 | M6 | M9 | M12 |
|---|---:|---|---|---|---|---|
| A1 strong | 0 | 8 / 10 / 11 | 17 / 20 / 21 | 20 / 23 / 24 | 22 / 29 / 31 | 32 / 38 / 41 |
| A1 average | 0 | 10 / 11 / 13 | 21 / 25 / 27 | 24 / 28 / 32 | 30 / 50 / 57 | 74 / 101 / 103 |
| A1 struggling | 0 | 11 / 12 / 13 | 16 / 22 / 24 | 42 / 52 / 55 | 52 / 64 / 67 | 92 / 106 / 110 |
| A2 strong | 0 | 9 / 10 / 12 | 18 / 21 / 22 | 19 / 22 / 23 | 23 / 30 / 32 | 32 / 46 / 48 |
| A2 average | 0 | 9 / 12 / 13 | 18 / 26 / 30 | 24 / 28 / 30 | 29 / 39 / 44 | 97 / 117 / 124 |
| A2 struggling | 0 | 9 / 12 / 13 | 15 / 21 / 23 | 28 / 36 / 40 | 56 / 64 / 67 | 93 / 99 / 104 |
| B1 strong | 0 | 8 / 9 / 11 | 18 / 21 / 22 | 20 / 22 / 23 | 22 / 30 / 33 | 30 / 36 / 40 |
| B1 average | 0 | 9 / 12 / 13 | 20 / 24 / 27 | 25 / 28 / 29 | 28 / 37 / 41 | 100 / 118 / 123 |
| B1 struggling | 0 | 9 / 16 / 17 | 18 / 24 / 26 | 28 / 34 / 38 | 55 / 63 / 66 | 82 / 92 / 93 |
| B2 strong | 0 | 9 / 11 / 12 | 20 / 21 / 23 | 20 / 23 / 25 | 22 / 28 / 32 | 35 / 64 / 68 |
| B2 average | 0 | 9 / 12 / 12 | 21 / 24 / 29 | 24 / 33 / 36 | 29 / 50 / 60 | 65 / 91 / 94 |
| B2 struggling | 0 | 11 / 15 / 17 | 15 / 23 / 28 | 28 / 40 / 48 | 55 / 67 / 72 | 87 / 101 / 111 |
| C1 strong | 0 | 9 / 11 / 14 | 18 / 21 / 22 | 20 / 22 / 24 | 24 / 29 / 33 | 29 / 50 / 53 |
| C1 average | 0 | 10 / 13 / 15 | 21 / 25 / 26 | 26 / 30 / 33 | 32 / 65 / 74 | 88 / 118 / 129 |
| C1 struggling | 0 | 9 / 12 / 13 | 15 / 20 / 22 | 28 / 52 / 64 | 50 / 61 / 66 | 100 / 116 / 119 |
**E. FSRS retention** (recall = retrievability × 1.0 / 0.92 / 0.75), credit, 30-due session:

| Life | credited | M1 | M3 | M6 | M9 | M12 |
|---|---:|---|---|---|---|---|
| A1 strong | 0 | 9 / 11 / 15 | 20 / 23 / 24 | 22 / 25 / 26 | 28 / 37 / 39 | 59 / 86 / 91 |
| A1 average | 0 | 9 / 11 / 13 | 21 / 25 / 27 | 24 / 27 / 32 | 30 / 44 / 55 | 92 / 116 / 122 |
| A1 struggling | 0 | 11 / 14 / 18 | 15 / 18 / 26 | 23 / 31 / 37 | 54 / 64 / 70 | 102 / 113 / 119 |
| A2 strong | 572 | 9 / 16 / 21 | 32 / 41 / 42 | 26 / 34 / 38 | 28 / 53 / 61 | 68 / 197 / 208 |
| A2 average | 572 | 10 / 14 / 17 | 40 / 60 / 74 | 34 / 42 / 43 | 42 / 66 / 72 | 112 / 125 / 146 |
| A2 struggling | 259 | 8 / 14 / 15 | 23 / 32 / 36 | 74 / 87 / 92 | 54 / 70 / 76 | 112 / 130 / 140 |
| B1 strong | 1465 | 10 / 21 / 23 | 38 / 60 / 79 | 67 / 100 / 106 | 55 / 141 / 147 | 136 / 172 / 181 |
| B1 average | 1465 | 11 / 18 / 19 | 125 / 139 / 142 | 102 / 121 / 125 | 160 / 173 / 179 | 136 / 149 / 153 |
| B1 struggling | 1031 | 10 / 15 / 16 | 26 / 34 / 36 | 228 / 264 / 270 | 286 / 291 / 295 | 436 / 473 / 477 |
| B2 strong | 2801 | 9 / 25 / 28 | 197 / 232 / 237 | 219 / 244 / 248 | 150 / 273 / 316 | 187 / 258 / 279 |
| B2 average | 2801 | 10 / 24 / 33 | 200 / 225 / 235 | 155 / 164 / 167 | 140 / 193 / 198 | 312 / 343 / 367 |
| B2 struggling | 1031 | 10 / 12 / 13 | 12 / 21 / 26 | 90 / 125 / 138 | 278 / 285 / 289 | 493 / 525 / 536 |
| C1 strong | 4364 | 9 / 24 / 33 | 247 / 278 / 281 | 306 / 321 / 327 | 217 / 227 / 236 | 437 / 446 / 450 |
| C1 average | 4364 | 10 / 27 / 33 | 296 / 317 / 322 | 527 / 551 / 575 | 622 / 658 / 672 | 1130 / 1231 / 1242 |
| C1 struggling | 2048 | 10 / 16 / 18 | 14 / 20 / 25 | 269 / 305 / 316 | 642 / 684 / 693 | 1073 / 1164 / 1178 |
**What the year says.**
1. **The scheduler is not the problem; the session cap and the throttle's capacity are.**
   - Keeping up costs a strong learner 3–7 minutes a drill day all year, and an average learner 5–10.
   - The app shows one session of 30 due cards. With 8 new words a session, average learners need 35–60 reviews a day from month 9–10. Credited B2/C1 learners need them from month 2–3, when the 20–90-day light checks of the nearest sub-band land.
   - The overflow accumulates: in A, the B2 average median is 220 due in month 3, and C1 average reaches 450 by month 12.
   - The intake throttle never notices. Its capacity is the Rappel's 210 s plus 10 new words × 10 reviews × 6 s = 810 s ≈ 135 cards, so it engages only above ~200 due.
2. **The WP-127 credit spreads, but does not remove, the checking load.**
   - Under today's session it doubles to quadruples B2/C1 piles. Compare D (no credit) with A: C1 average 88 → 450 median in month 12.
   - Its 90–365-day window keeps adding checks all year: about 1,500–3,000 cards for B2/C1.
3. **Struggling learners pile up whatever the cap.**
   - At 62 % accuracy, every third review lapses.
   - Even clearing everything, they reach 11–28 minutes per drill day (6–14 a calendar day) by month 12, at about 2 new words a day.
4. **The `fsrs` assumption is harsher for average and struggling learners.** Overdue cards are recalled less often, so lapses compound. C1 average reaches 1,130 due in month 12 under the cap.

**The 150-card walk check** (`MAX_DUE_BACKLOG`) is a regression alarm for 30 days and nothing more. Under today's session, every B1–C1 life crosses 150 due on 10–307 days of the year, while no learner who keeps up ever does.

### Proposed usability target (for the owner; not imposed)
> On a Régulier rhythm, over twelve months, a **strong or average** learner's word reviews fit **one drill session on 90 % of days**: p90 true due ≤ 30 cards and p90 review time ≤ 5 minutes. A **struggling** learner's fit **two sessions** (p90 ≤ 60 due, ≤ 10 minutes per drill day). The 150-card walk check stays as the 30-day regression alarm.

How far today's product is from that target (walk retention, credit; months of 12 meeting the due bound, and for the learner who keeps up, the due and minutes bounds together):

| Life | months meeting it, today (30-card session) | first month missed | keeping up: months meeting | first missed |
|---|---:|---:|---:|---:|
| A1 strong | 8 | 9 | 10 | 10 |
| A1 average | 8 | 9 | 8 | 9 |
| A1 struggling | 6 | 7 | 7 | 8 |
| A2 strong | 8 | 9 | 9 | 10 |
| A2 average | 1 | 2 | 1 | 2 |
| A2 struggling | 4 | 5 | 5 | 6 |
| B1 strong | 3 | 2 | 7 | 3 |
| B1 average | 1 | 2 | 1 | 2 |
| B1 struggling | 2 | 3 | 3 | 4 |
| B2 strong | 1 | 2 | 1 | 2 |
| B2 average | 1 | 2 | 1 | 2 |
| B2 struggling | 4 | 5 | 5 | 6 |
| C1 strong | 1 | 2 | 1 | 2 |
| C1 average | 1 | 2 | 1 | 2 |
| C1 struggling | 3 | 4 | 3 | 4 |

From A2 up, the credit's light checks and the average learner's lapses break the target in month 2. A fresh A1 learner meets it until month 8 or 9.

The levers, smallest first, all for the owner:
1. **Make the throttle's capacity the session the learner actually sees.** About 30 due cards plus 8 new is ≈ 5 min, against today's 135 cards. Intake would then halve when the pile passes ~45 instead of ~200. This is one constant in `intake_throttle.review_capacity_seconds`.
2. **Sample the light checks of inferred words** instead of re-checking every inferred card. For example, check 15 % and confirm the rest on a pass. That cuts the B2/C1 credit load by about 5×.
3. **Let the drill offer a second session («Encore») of due cards when the pile exceeds one session.** The review-only «Encore 5 minutes» exists after the Seal; it would be surfaced earlier.

## 3. The data audit
**Can production hold affected rows?** I have no production access. The evidence is from this repository's refs, as last fetched:
- `origin/main` (2026-09-10) has **no** `user_vocabulary_progress.provenance` column and no `band_check` service. The band-check credit flood (fix 13 / WP-127) **cannot exist** in a database deployed from `main`. It exists only where the unpushed branch (the vocabulary check landed 2026-10-03) was deployed or run.
- `origin/main` **does** have the letter path that writes `vocabulary_missing_target` errata with `source_type="mission"` and charges `missed_target` lapses (`missions.py`, `vocabulary_credit.py`). Production **can** hold WP-125A rows if learners answered letters with suggested words.
- `origin/main` has `journey_correction` errata. Rows from practice-miss and give-up errata (fix 7) are possible, but `main` records no `task_type` in their metadata. Most of them are therefore **unprovable**, and the audit leaves them alone.

**The script.** `scripts/audit_experience_review_rows.py` covers five categories. Each is proven by provenance, never by guesswork; the module docstring has every rule.

| Category | Proof | Repair (`--apply` only) |
|---|---|---|
| `band_check_flood` | `provenance` `band_check`/`band_check_inferred`, stability exactly 30 (the fixed schedule's floor is 60), `reps` 2, `lapses` 0, **no review log** | the current `credit_schedule` window for the distance below the learner's band, seeded as `credit()` seeds; **never earlier than the stored due date** |
| `letter_omission_errata` | `vocabulary_missing_target`, `source_type` `mission`, one occurrence, not mastered | removed |
| `letter_omission_lapses` | a `mission` review log rated 0, where the learner's mission payloads carry a `missed_target` for the word and no `produced_incorrect` | **report only**: the pre-lapse stability is not stored |
| `practice_miss_vocab_errata` | `daily_journey` vocabulary erratum, one occurrence, recorded `task_type` is a practice format | removed |
| `give_up_correction_errata` | `journey_correction` from `daily_journey`, one occurrence, the stored text is a give-up (`attempted_answer`), and its `source_key` names a practice step | removed |

The script never touches:
- an erratum that merged several occurrences, or one already mastered;
- a reply's own French;
- a credited card that has been reviewed;
- any card of another provenance, such as an import;
- anything unprovable.

Each of these is counted under «left alone», with its reason. On a database without the newer columns, a category answers «not applicable» and gives the reason.

**Safety.**
- **The dry run is read only.** One transaction, marked `SET TRANSACTION READ ONLY` on PostgreSQL or `PRAGMA query_only` on SQLite, then rolled back. A test proves that a delete inside it fails.
- **`--apply` requires `--backup <file.jsonl>`.** It re-runs the audit inside one write transaction, writes every row it will change, in full, to the backup first, and re-checks the credit proof in the `UPDATE`'s own `WHERE`. It is idempotent.

**Proof on a disposable fixture** (`tests/test_wp123b_audit_rows.py`). A throwaway SQLite file holds one row of every kind to find and one of every kind to leave alone, plus unrelated rows. The test checks that:
- the dry run finds exactly the proven rows and the database is byte-for-byte unchanged;
- `--apply` changes exactly 4 rows (1 rescheduled, 3 removed) and backs them up;
- every other row is identical;
- the rescheduled card lands in the 20–90-day window and not earlier;
- a second `--apply` changes nothing;
- an old schema answers «not applicable».

**For the owner: run it read-only against production.**
```
DATABASE_URL='postgresql://<read-only user>@<host>/<db>' \
  venv/bin/python -m scripts.audit_experience_review_rows --json audit-prod.json
```
- Use a read-only database role if one exists. The script enforces read-only either way.
- Read the table: if every «Affected rows» is 0, nothing more is needed.
- If not, run the repair only after reading the examples, against a fresh backup of the database, and with:
```
venv/bin/python -m scripts.audit_experience_review_rows --apply --backup prod-repair-$(date +%F).jsonl
```

## 4. Commands and results
| Command | Result |
|---|---|
| `pytest tests/test_wp123b_clock_defaults.py tests/test_wp123b_workload_sim.py tests/test_wp123b_audit_rows.py tests/test_walk_checks_wp123b.py` | 4 + 9 + 5 + 8 = 26 passed |
| default life walk, 15 lives (`-k average`, then `-k "strong or struggling"`) | 5 passed (10 min 30 s) + 10 passed (10 min 51 s), run concurrently with other work |
| `WALK_FORGE=1` life walk, 15 lives (twice) | 15 failed on the defects in §1.1; 33 min 51 s alone, against the default walk's ~18 min. The atelier's background pre-generation logs 6,157 harmless failures: it opens the app's real `SessionLocal` (`localhost:5432`), not the test database, a test-isolation item for E-2 |
| `WALK_FAIL_RATE=1 … -k b1-en-average` | 1 passed (59 s) |
| `python -m scripts.simulate_workload_365` | 4 scenarios × 15 lives × 365 days in about 10 s |
| full backend suite | 6,494 passed, 29 skipped, 12 failed in 20 min 7 s. 9 are the baseline (wp69 ×5, revue_relecture, wp96 ×2, wp74). wp78 and wp91 depend on test order and pass alone (as in Wave 2). `test_wp131…season_lexicon_file_is_current` fails on the base's bible and lexicon hash: the lexicon needs `scripts/build_season_lexicon.py` after Wave 3's bible edits. None of the 12 touches this package's files |

## 5. Patches outside the lease (for the orchestrator)
- **[`WP-123b-forecast-credit.patch`](WP-123b-forecast-credit.patch).** It adds a provenance filter to `app/services/level_forecast.measured_intake`, so the check's credited cards are neither intake nor retention, plus its test `tests/test_wp123b_forecast_credit.py`. I proved it in this worktree: the new test passes with the patch and fails without it, and `test_wp_l8_forecast` and `test_wp_l8_seal_forecast` still pass. Then I reverted it.
- **No patch for the four La Forge defects.** Each needs its owner:
  - the séance length against its budget (`forge.py`);
  - French or German cues for the C1 exercise sets;
  - a give-up graded as «partial», and turned into an atelier erratum (the atelier counterpart of review fix 7);
  - the 40-attempt release rule (`cefr_progress.py`, an owner decision under WP-134).
