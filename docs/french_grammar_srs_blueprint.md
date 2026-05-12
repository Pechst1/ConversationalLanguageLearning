# French Grammar SRS Blueprint

## Bottom Line

If you want portability across AIs, the LLM cannot be the memory. The workbook has to be the memory.

I would not store only one score per concept. That is too weak for fast grammar acquisition. You need:

- a stable concept catalog
- a current-state table
- an immutable review log
- an immutable error log
- a session log

Anything less and you lose the ability to recycle exact weak points.

## What I Would Do Differently

I would keep Excel as the canonical ledger, but I would not make the workbook itself "smart" with huge formula logic. That becomes brittle fast.

Better split:

- Excel stores all state
- the LLM reads a pasted extract and returns update rows
- you paste the returned rows back into Excel

If you later want automation, you can add a tiny script. The schema still survives. That is the right portability layer.

## Core Design Principle

Grammar is not vocabulary. A concept is not learned just because you recognized it once.

For each concept, your system has to capture:

- whether you understand the rule
- whether you can choose the right form under pressure
- whether you can produce it freely
- which exact mistake patterns recur
- whether the concept fails only in isolation or also in connected writing

That is why one current score plus one next review date is not enough.

## Concept Granularity

One row must represent one teachable and testable unit.

Good:

- `FR_A1_ART_003` partitive article in affirmative statements
- `FR_A1_ART_004` partitive/article change after negation
- `FR_A2_PRON_005` y replacing `a + thing/place`
- `FR_B1_TENSE_012` imparfait vs passe compose
- `FR_B2_REL_003` `dont` after verbs that require `de`

Bad:

- articles
- pronouns
- past tenses

If a topic produces different mistake families, split it.

## Workbook Sheets

Use these 5 sheets.

### 1. `Concepts`

Static catalog. One row per grammar concept.

Required columns:

- `concept_id`
- `language`
- `cefr_level`
- `category`
- `subskill`
- `concept_name`
- `teaching_order`
- `is_foundation`
- `parent_concept_id`
- `prerequisite_ids`
- `core_rule`
- `main_traps`
- `anchor_examples`
- `exercise_tags`
- `active`

### 2. `Progress`

Current state. Exactly one row per concept.

Required columns:

- `concept_id`
- `status`
- `mastery_score`
- `ease_factor`
- `interval_days`
- `last_review_date`
- `next_review_date`
- `review_count`
- `lapse_count`
- `consecutive_successes`
- `rolling_accuracy_5`
- `free_production_score`
- `last_quality`
- `last_error_types`
- `last_session_id`
- `priority_override`

### 3. `Sessions`

One row per learning session.

Required columns:

- `session_id`
- `session_date`
- `session_type`
- `main_concept_ids`
- `review_concept_ids`
- `recent_error_ids_used`
- `overall_result`
- `summary`
- `next_focus`

### 4. `ReviewLog`

Immutable event log. One row per concept reviewed in a session.

Required columns:

- `review_id`
- `session_id`
- `review_date`
- `concept_id`
- `round_1_quality`
- `round_2_quality`
- `round_3_quality`
- `concept_quality_final`
- `accuracy_percent`
- `confidence_estimate`
- `exercise_types`
- `error_count`
- `repeated_error_count`
- `free_production_ok`
- `old_interval_days`
- `new_interval_days`
- `old_ease_factor`
- `new_ease_factor`
- `next_review_date`
- `notes`

### 5. `ErrorLog`

Immutable mistake history. One row per meaningful error pattern detected.

Required columns:

- `error_id`
- `session_id`
- `review_id`
- `error_date`
- `concept_id`
- `error_type`
- `subskill`
- `severity`
- `recurring`
- `learner_output`
- `correct_target`
- `why_wrong`
- `repair_hint`
- `resolved_after_session_id`

## Minimal Status Labels

Keep status labels simple:

- `new`
- `learning`
- `fragile`
- `stable`
- `mastered`

Do not create ten emotional labels. They add noise.

## Recommended Scoring Model

Use a 0-4 quality score per concept per session.

- `0` failed
- `1` major confusion
- `2` partial grasp, unstable
- `3` mostly correct
- `4` strong and transferable

Why 0-4 instead of 0-10?

- easier for the AI to assign consistently
- easier to map into intervals
- less fake precision

If you want a user-facing 0-100 mastery score, derive it from repeated reviews. Do not ask the AI to hallucinate exact granularity every time.

## Mastery Score

Use `mastery_score` as a smoothed long-term indicator from 0 to 100.

Recommended update:

`new_mastery = clamp(0.65 * old_mastery + 0.35 * target_mastery - error_penalty + production_bonus, 0, 100)`

Map `concept_quality_final` to `target_mastery`:

- `0 -> 10`
- `1 -> 30`
- `2 -> 50`
- `3 -> 75`
- `4 -> 90`

Adjustments:

- `error_penalty = 10` if the same error type repeated at least twice in the session
- `production_bonus = 5` if Round 3 free production was clearly correct

This gives you a stable trend without pretending the model can measure you perfectly in one sitting.

## Ease and Interval Model

Use a modified SM-2 style model because it is simple enough for Excel and portable across AIs.

Starting values:

- `ease_factor = 2.3`
- `interval_days = 0`

Update rules:

- If `quality = 0`:
  - `interval_days = 1`
  - `ease_factor = max(1.3, ease_factor - 0.25)`
  - `consecutive_successes = 0`
  - `lapse_count += 1`

- If `quality = 1`:
  - `interval_days = max(2, round(max(1, old_interval_days) * 0.6))`
  - `ease_factor = max(1.3, ease_factor - 0.15)`
  - `consecutive_successes = 0`
  - `lapse_count += 1`

- If `quality = 2`:
  - `interval_days = max(4, round(max(2, old_interval_days) * 1.1))`
  - `ease_factor = max(1.3, ease_factor - 0.05)`
  - `consecutive_successes = 0`

- If `quality = 3`:
  - `interval_days = max(6, round(max(3, old_interval_days) * ease_factor))`
  - `ease_factor = min(2.8, ease_factor + 0.05)`
  - `consecutive_successes += 1`

- If `quality = 4`:
  - `interval_days = max(8, round(max(4, old_interval_days) * ease_factor * 1.3))`
  - `ease_factor = min(2.8, ease_factor + 0.10)`
  - `consecutive_successes += 1`

Penalties:

- repeated same error pattern in session: `interval_days *= 0.8`
- failed free production in Round 3: `interval_days *= 0.8`
- basic A1-A2 foundation concept with unstable performance: `interval_days *= 0.85`

Bonus:

- fully correct Round 3 production: `interval_days *= 1.1`

Round the final interval to whole days and set `next_review_date`.

## Priority Score For Selecting Concepts

Do not select concepts randomly. Use a priority score.

Recommended formula:

`priority = overdue_points + fragility_points + error_points + foundation_points + manual_override`

Where:

- `overdue_points = max(0, days_overdue) * 5`
- `fragility_points = (100 - mastery_score) * 0.4`
- `error_points = min(20, recurring_errors_last_30d * 4)`
- `foundation_points = 10 if is_foundation = TRUE and mastery_score < 75 else 0`
- `manual_override = priority_override`

Interpretation:

- highest priorities get pulled into the next session
- if backlog is large, skip new concepts
- if foundation errors are recurring, pull those basics back in early

## How To Build Each Session

For a normal mixed session:

- choose 2 highest-priority due concepts
- choose 1 new concept if due backlog is manageable
- if you have recurrent basic failures, replace the new concept with the weak foundation concept

For a review-heavy session:

- choose 3 due concepts
- no new concept

For a repair session after a bad day:

- choose 2 failed concepts from the last 7 days
- choose 1 basic prerequisite concept

## What To Recycle Inside Exercises

Do not only repeat whole concepts. Recycle:

- repeated error types
- wrong auxiliaries
- agreement failures
- article changes after negation
- pronoun ordering mistakes
- tense contrast mistakes

That means Round 2 and Round 3 should not only revisit the concept but the exact failure mode.

## Exercise Progression

Use this progression every session.

### Round 1

Controlled practice:

- fill-in
- choice tasks
- local corrections
- one short production item

### Round 2

More open and contrastive:

- sentence creation
- sentence transformation
- dialog completion
- error discrimination

### Round 3

Short connected text:

- B1 target: usually 90 to 140 words
- require all 3 concepts
- require at least 1 recycled weak point

## Why The Error Log Matters

Without an error log, the AI can tell you what was wrong today but it cannot systematically exploit weak points tomorrow.

The error log is what turns "practice" into "targeted repair."

## Blunt Recommendation

If your real goal is to learn French grammar as fast as possible, do not optimize for elegant theory. Optimize for ruthless reuse of weakness.

That means:

- atomic concepts
- strict correction
- immutable review history
- immutable error history
- conservative recycling of weak basics
- free production every session

If you want, the next practical step is to convert your existing workbook into this schema instead of starting from zero.

