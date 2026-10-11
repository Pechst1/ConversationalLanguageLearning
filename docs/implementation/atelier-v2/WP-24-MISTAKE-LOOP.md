# WP-24 — Close the mistake loop end to end

2026-09-10. The cascade *errata → due → generation prompt* already existed. What
did not exist was a way out of it, a scheduler behind it, a deliberate choice of
tomorrow's scene from it, or a word to the learner about it.

Four defects, from the 2026-08-31 audit, and what each one is now.

| | Before | After |
|---|---|---|
| **(a)** | A `UserError` could never reach `mastered`. `review_error` wrote `review` or `relearning` and nothing else, so every mistake a learner ever made stayed in the queue for the life of the account | Three states — `open → repairing → mastered` — with a real exit and a real reopen |
| **(b)** | `grammar.calculate_next_review` was a five-branch day table (30/14/7/3/1). `app/core/srs/sm2.py`, a complete SM-2 implementation, was imported by nothing | One scheduler, `app/core/srs/schedule.py`, wrapping `sm2.review_card`. Errata and grammar concepts both use it |
| **(c)** | The planner ranked whatever candidates it was handed; a mistake reached a later scene only by luck | `app/services/journey_errata.py` ranks the learner's due errata and `plan_journey(errata_targets=…)` merges them in front, stamping `target_reason` |
| **(d)** | Nothing told the learner why today's scene was this scene | Home's because-line: « Cette scène reprend une faute notée : … » |

## 1. The lifecycle

```
        record                repair (spaced, distinct day) ×3
  ─────────────►  open  ──────────────────────────────────────►  mastered
                   │  ▲                                              │
      repair ──────┘  │                                              │
        │             └──────────── recurrence ───────────────┐      │
        ▼                                                     │      │
    repairing ◄────── failed repair / recurrence ─────────────┴──────┘
```

* **`open`** — recorded, never repaired since it was last made.
* **`repairing`** — repaired at least once, not yet proven. A failed repair and a
  recurrence both land here.
* **`mastered`** — `MASTERY_REQUIRED_REPAIRS` (3) correct repairs on **distinct
  days**, with no recurrence in between. The only state `due_error_records`
  refuses to hand back.

Two deliberate rules:

* **Spaced means distinct days.** Three correct answers in one sitting advance the
  streak once. Retention is measured across nights, and `last_correct_date` is
  what enforces it.
* **A recurrence destroys the evidence, it does not pause it.** `mastery_streak`
  goes to zero, `mastered_at` is cleared and the ease drops. Three spaced repairs
  followed by the same mistake did not prove anything.

Backwards compatibility: the legacy vocabulary (`new`/`learning`/`review`/
`relearning`) is read, never trusted blindly. `normalize_error_state()` folds it,
and the migration relabels stored rows. **`review` becomes `repairing`, not
`mastered`** — a row that was merely scheduled forward has not demonstrated
anything, and retiring it would silently delete errata the learner never fixed.

## 2. The scheduler

`app/core/srs/schedule.py` — a pure function over a state tuple, so the caller
owns the storage:

* `schedule_next(now=…, quality=0-4, state=ScheduleState(…), min_interval_days=1)`
  → `ScheduleDecision(due_at, interval_days, ease_factor, reps, lapses, phase)`.
* `interval_for_score(score_0_10, previous_interval_days=…, reps=…)` → `timedelta`,
  the drop-in for the old grammar lookup.

Properties the day tables did not have: the interval compounds through the SM-2
ease factor, a lapse resets it to one day *and* costs ease, and five is a pass
(the pass mark everywhere else in the product), not a lapse.

One compatibility concession, written down rather than hidden: **a first review
still grants the historic seed interval** (30/14/7/3/1 by score). SM-2 has no
history to work from on review one either, and changing it would re-date every
concept every learner has ever met for no measurement gain. Every review after
the first compounds.

## 3. Errata targets

`app/services/journey_errata.py`:

* `errata_targets_for_user(db, user, limit=3)` → ranked `ErrataTarget`s.
* `ErrataTarget.as_candidate()` → a `LearningCandidate` carrying
  `metadata["target_reason"] = "erratum:<id>"`.
* `ErrataTarget.as_because()` → `{"kind", "reason", "label", "example"}`, the
  structured because-line payload. **Never a rendered sentence** — the French
  lives in the component that prints it.

Ranking is small and explainable: state (a repair in progress outranks an
untouched mistake), lapses, occurrences, overdue days, severity — each term
bounded so none can dominate. Deduplication is **per concept** where a concept is
known: three gender slips on three nouns are one lesson.

It reads the same queue Le Relevé and the Cahier read, and **reading never
reschedules** (pinned by a test).

## 4. Planner wiring

`plan_journey(..., errata_targets=[…])`. Omitted, the plan is byte-identical to
what it was before this package.

The reason does **not** travel in the public step prompts: `JourneyModel` is
`extra="forbid"`, and adding a key would be a wire-contract change owned by the
integration lead. Instead:

* the plan's `rationale` names the reason (operators, telemetry);
* `plan_target_reasons(plan, candidates)` → `{identity: reason}` for targets the
  plan actually kept;
* `plan_because(plan, candidates, errata_targets)` → the because payload.

`journey_errata` is imported by the planner **under `TYPE_CHECKING` only** — the
planner is contractually a pure function over its arguments, and
`test_the_planner_imports_no_ladder_and_no_scheduler` now fails if that import
escapes the guard.

## 5. Hooks needed from other owners

These are outside this package's lease. Nothing was edited in them.

**`app/services/daily_journey.py`** (daily-journey owner) — two lines where the
plan is built, and one where the envelope is assembled:

```python
from app.services.journey_errata import errata_targets_for_user
from app.services.journey_planner import plan_because, plan_journey

errata = errata_targets_for_user(db, user)          # 1. read the ranked errata
plan = plan_journey(                                 # 2. hand them to the planner
    scenario=scenario,
    candidates=candidates,
    pace=pace,
    input_mode=input_mode,
    errata_targets=errata,
)
because = plan_because(plan, candidates, errata)     # 3. dict | None
# ... put `because` on the /atelier/today envelope (a nullable object field),
#     and pass it through pages/atelier.tsx to <HomeScreen because={…} />.
```

Until that lands, the because-line renders nothing (its prop is optional and it
returns `null` without one) and the planner behaves exactly as before.

**`app/services/living_story.py`** (story-engine owner) — the director context
already takes learning targets. `ErrataTarget.label`, `.example`
(«une homme → un homme») and `.why` are the three fields worth putting in the
scene-draft prompt so the generated situation actually needs the repaired form.
No change is required for correctness; this is the quality half of (c).

## 6. Migration

`alembic/versions/b5c6d7e8f9a0_user_error_mastery_lifecycle.py`, down-revision
`a3b4c5d6e7f8`. Adds `mastery_streak`, `mastered_at`, `last_correct_date`,
`ease_factor` to `user_errors` (all nullable, with server defaults), then
relabels the legacy states. **Existing rows are not re-dated**, only relabelled.
`downgrade()` reverses both.

Two notes:

* The column adds are idempotent (`_has_column`), so a partially applied
  migration re-runs cleanly.
* **`alembic heads` currently reports two heads**, and only one is this
  package's: another in-flight branch added
  `b4c5d6e7f8a9_add_placement_sessions.py` re-using a revision id that already
  exists (`b4c5d6e7f8a9_add_real_world_missions.py`), which alembic warns about.
  That collision is that package's to resolve; `b5c6d7e8f9a0` chains cleanly off
  `a3b4c5d6e7f8`.

## 7. How to verify

```bash
TZ=UTC .venv/bin/python -m pytest tests/test_wp24_mistake_loop.py -q     # 34 tests
TZ=UTC .venv/bin/python -m pytest tests/test_journey_planner.py \
  tests/test_atelier.py tests/test_journey_learning.py \
  tests/test_srs_review_cycle.py tests/test_unified_srs.py -q
cd web-frontend && npm run type-check && npm run lint && npm run test:journey
```

`tests/test_wp24_mistake_loop.py` covers, one test per claim: each transition,
the same-sitting rule, the recurrence reopen, legacy-state folding, a NULL-state
legacy row still being due, interval compounding, lapse cost, the seed intervals,
the ranking, the per-concept dedup, "reading does not reschedule", the planner's
`target_reason`, the absence of a reason when nothing is owed, the wire contract
staying clean, and a source scan proving Home renders the French because-line.

Manual check once the daily-journey hook lands: make the same mistake twice, then
open Home the next day — the line under the primary action should read
« Cette scène reprend une faute notée : … », and the scene's targets should
include that erratum.

## 8. Known limits

* Mastery is measured per `UserError` row, not per concept. `UserErrorConcept`
  has its own SRS columns and is still only an occurrence counter; folding the
  two is a larger piece of work and is not in this package.
* The because-line is dark until the daily-journey hook (§5) lands.
* `MASTERY_REQUIRED_REPAIRS = 3` and the ranking weights are chosen, not
  measured. WP-22's five-learner study is the first data that could move them.
