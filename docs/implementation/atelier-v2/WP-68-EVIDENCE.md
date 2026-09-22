# WP-68 — La preuve: six packages, played together for four months

WP-62..67 landed on 2026-09-21 in one shared checkout, each with its own suite and
its own evidence note. None of them had been played **with the others** over a
horizon long enough for the seams to show. This is that run, what it proved, what
it broke, and what it could not prove.

Deliverables: `tests/test_long_horizon_evidence.py` (17 tests, ~30 s),
`scripts/long_horizon_report.py` (a readable season timeline), one sample report
in `evidence/long-horizon-A-2026-09-21.md`, and the prepared — **not run** — paid
review commands in §6.

---

## 1. What the harness actually runs

Two learners, **126 simulated days each**, through the assembled system: the real
daily-journey router and state machine, `build_default_adapters()`, the real
planner and its day shapes, the real living-story engine, and the real Courrier —
`GET /missions/today`, `POST /missions/{id}/submit`, `POST /missions/{id}/complete` —
against one SQLite database. Both learners are played from an identical script, so
**everything that differs between the two lives comes from their seeded dice and
nothing else**.

Stubbed: only the model. `living_story._client` is the scripted fake
`tests/test_living_story_longitudinal.py` already uses (with WP-62's `long_memory`
and WP-63's `season_engine` compliance flags on), and `missions._safe_llm` returns
`None`, so the Courrier takes its own authored fallback path. **No provider was
called and nothing was spent.**

### One clock for six packages

The run patches `daily_journey._utcnow` and the module-level `datetime` / `date`
names in `missions`, `story_correspondence`, `error_memory`, `journey_errata`,
`journey_learning` and `unified_srs`. Without that, a simulated week is a week to
the journey and an instant to everything else: the errata queue is never due
again, the ISO week never turns, and a letter's soft deadline never arrives. See
L-4 below — the fact that six modules have to be patched is itself a finding.

One clock it cannot reach: `real_world_missions.created_at` is a SQL
`func.now()` server default. `_align_letter_to_the_clock` restamps a freshly
created letter and recomputes `expires_at` through the production
`courrier.expiry_for`, which is seeded on the user and the mission — so the letter
gets exactly the deadline production would have given it.

### The dice are spied on, not re-derived

`daily_journey.choose_day_shape` is wrapped so the run records the exact
`DayShapeInputs` the planner was called with and the `DayShapeDecision` it got
back. Reproducibility is then tested by replaying **the production function with
the production inputs**, not by re-implementing the roll.

---

## 2. What the run asserts, and what holds

| # | Claim | Test |
|---|---|---|
| 1 | A day-100 and a day-126 director context still carry a sentence said inside week one; the chronicle block stays under `CHRONICLE_PROMPT_CHARS` and the consequence/plant projections inside their limits | `test_day_one_hundred_still_answers_for_the_first_week` |
| 2 | A callback offered in the second month or later reaches **≥ 30 days** back (observed: 101 and 76 days); a `branch` the learner made true inside the first 20 days is still on the ledger at day 126; all four consequence kinds, a paid plant, moved secrets | `test_an_early_consequence_is_still_offered_back_after_a_hundred_days` |
| 3 | The cast's agendas tick; every `meanwhile` row has witnesses and **never** the character whose week it was | `test_the_cast_has_a_life_between_the_chapters_and_only_witnesses_hear_it` |
| 4 | The season's long questions move `open → developing → closed`; the archive is all closed | `test_the_seasons_long_questions_move_through_their_states` |
| 5 | Finale → interlude → season 2, with chronicle, consequences, secrets and `world_flags` carried over; **no day is ever served with `suggested_arc=None` while the phase is `running`**; some arc was gated (`blocked_by`) | `test_the_season_ends_then_begins_again_with_the_memory_intact` |
| 6 | ≥ 4 chapter shapes, never the same shape twice running (finale and interlude excepted — those are forced) | `test_chapter_shapes_vary_and_never_twice_in_a_row` |
| 7 | A completed letter's `events[]` row (witness = the correspondent) and its mood step are in the **next day's** director context — proven on ≥ 5 letters per life | `test_a_finished_letter_is_a_fact_in_the_next_days_scene` |
| 8 | A lapsed letter is `ignored`, has **no** attempt, and writes exactly one ignored event per letter | `test_a_lapsed_letter_cools_the_correspondent_once` |
| 9 | A chain of ≥ 3 letters with one correspondent, contiguous indices, climbing `stakes_level`, a deadline on every instalment | `test_a_chain_of_three_letters_progresses` |
| 10 | Every «jour de lettre» carries a letter on its respond step; a letter answered inside the day has **exactly one** `mode="journey"` attempt, is `completed`, carries a `kept\|partial\|missed` outcome and the measured debrief | `test_a_letter_day_finishes_its_letter_exactly_once` |
| 11 | ≥ 4 day shapes dealt and served, **none above 50 % of the deal**, no two identical shapes dealt on consecutive days, and every difference between the deal and the served day has a recorded reason | `test_a_horizon_of_days_does_not_repeat_itself` |
| 12 | A «jour d'écoute» never poses a format that cannot be taken down by ear | `test_the_listening_day_never_poses_a_format_that_cannot_be_heard` |
| 13 | Two lives, two arc orders, two months of day shapes, two hands of chapters, two sets of agenda timings, two first weeks of post | `test_two_lives_diverge` |
| 14 | Every day's deal replays identically through the production `choose_day_shape` with the recorded inputs; each life's callback sequence is reproducible and the two differ | `test_each_deal_is_reproducible` |
| 15 | The day-126 prompt payload is ≤ 1.6× the day-20 one; the event tail, the consequence ledger and the plant ledger stay inside their caps | `test_the_prompt_does_not_grow_with_the_horizon` |

The two-attempt 75 s budget test is untouched: `tests/test_living_story_budget.py`
→ **9 passed**.

### The numbers this run produced

(`evidence/long-horizon-A-2026-09-21.md` is the full reading copy.)

| | learner A | learner B |
|---|---|---|
| days played | 122 / 126 | 122 / 126 |
| chapters | 31 | 30 |
| finale · interlude | j73 · j78 | j75 · j80 |
| season reached | 2 | 2 |
| letters | 68 (1 lapsed, 5 answered inside the day) | 68 (2 lapsed, 7 inside the day) |
| day shapes served | standard 48 % · reprise 34 % · listening 11 % · letter 4 % · court 3 % | standard 44 % · reprise 27 % · listening 20 % · letter 6 % · court 3 % |
| recall formats | tiles 119 · transform 44 · classify 13 | tiles 96 · transform 56 · classify 36 |
| consequence ledger | 60 (capped) | 60 (capped) |

---

## 3. Defects found and fixed

Each is minimal and carries a regression test.

### D-1 — WP-63's chapter shape never reached WP-66's day shape

`daily_journey._day_shape_inputs` read the chapter and the chapter shape off the
**top level** of `brief.story_context`:

```python
chapter = story.get("chapter") …
chapter_shape = chapter.get("shape") or story.get("chapter_shape") or draft.get("shape")
```

A living-story brief is `{"version", "source", "draft", "generation_usage", …}`
(`living_story.py`, the `ScenarioBrief(...)` construction): the director context —
including WP-63's `chapter_shape` projection and the chapter itself — is under
`source`. None of the three keys that function looked at exists on a real brief, so
`chapter_shape` was **always `None`**. WP-63 dealt 5–8 letter chapters per life in
this run and not one of them ever dealt «jour de lettre»; the only reason the shape
appeared at all was the seeded dice.

Fixed in `app/services/daily_journey.py`: read `story["source"]["chapter_shape"]["shape"]`
and `story["source"]["chapter"]["shape"]` as well, through two small helpers
(`_mapping`, `_shape_name`) so a key holding the wrong type is an absent key rather
than a 500. The shape is passed **only on the chapter's own letter beat**
(`chapter_shape["letter_beat"]`, which WP-63 ships for exactly this): a chapter that
asked for one letter must not spend four. After the fix the reason
`chapter_letter_shape` appears in the run.

Regression: `tests/test_journey_letter_day.py::test_the_day_reads_the_chapter_shape_where_the_engine_actually_writes_it`.

### D-2 — the letter-chapter override ignored the no-repeat rule

`journey_day_shapes.choose_day_shape` documents as its second rule «no two
identical shapes on consecutive days», and the resolution-beat override has always
deferred to it (`previous is not DayShape.REPRISE`). The letter-chapter override
did not, so a letter chapter whose turn beat landed the morning after a letter day
dealt the same day twice. D-1 is what made this reachable; the harness hit it on
day 20 of learner A.

Fixed with one condition (`previous is not DayShape.LETTER`). Regression:
`tests/test_journey_letter_day.py::test_a_letter_chapter_does_not_deal_two_letter_days_running`.

### D-3 — a seed-flaky test in WP-63's own suite

`tests/test_living_story_longitudinal.py::test_a_chapter_closes_after_three_resolved_commitments_without_the_model_saying_so`
failed about **one run in six**, on the working tree *and* at `148d2e6`. WP-63 deals
each chapter its own length and a three-beat two-hander reaches its resolution beat
on day three — before the commitment limit the test is about can fire. Whether the
learner's seeded dice deal one is luck.

Fixed in the test: `engine.chapter_shape` is pinned to `DEFAULT_SHAPE` for that
test, so the assertion is about the commitment limit and nothing else. No
production code changed.

---

## 4. Defects left — documented, not built

### L-1 — under the living-story engine the planner has no affordances at all

`journey_planner._affordances_for` resolves `journey_content.scenario_target_affordances(scenario.scenario_key, …)`,
which looks the key up in the **authored** scenario families. A living-story brief's
`scenario_key` is a generated situation id, matches no authored variant, and the
function returns `[]` — by its own design («a scenario family with no authored data
simply affords nothing»).

Two of the six recall formats are built out of those affordances:

* `choice` needs `_distractors` — scene phrases that are plausible but not the answer;
* `word_bank` needs `_extra_chips` — at least one single word from the scene that is
  **not** part of the answer, without which «the chip row is the answer written down
  in the wrong order and a learner can solve it by counting».

So for every learner on the story engine, `choice` and `word_bank` **can never be
posed**, and `scenario_fit` is 0 for every candidate. Over 244 learner-days this run
posed exactly three formats: `tiles`, `transform`, `classify`. WP-66's «≥ 5 of the
six formats» is true of the planner in isolation (`test_a_month_of_plans_poses_at_least_five_of_the_six_formats`,
which hands the planner an authored brief) and **not reachable end to end today**.
`test_every_recall_format_posed_is_one_the_contract_knows` asserts what actually
holds (≥ 3, both of WP-66's affordance-free additions present) and names this note.

Why it is not fixed here: the honest fix is for the director to *emit* affordances —
a new `SceneDraft` field, prompt work and a paid re-validation — or for the brief to
carry short French the learner could reach for. Feeding the planner whole dialogue
sentences would give `word_bank` plausible chips and `choice` a set of sentence-long
distractors, which is a worse screen than no `choice` at all. That is a product
decision about what a generated scene affords, not a plumbing bug.

### L-2 — the errata queue crowds vocabulary out of the daily loop

A learner who answers a Courrier letter every other day files errata faster than
the journey's ≤ 2 recall slots can repair them. Errata outrank due vocabulary in
candidate selection (WP-24, deliberately), and an erratum's repair format is `tiles`
unless its correction happens to contain `tu`/`vous`. The measured result is
`tiles` at 55–65 % of every recall step posed, and due words that wait weeks. The
brief's «no format above 50 %» is therefore not achievable end to end **whatever**
L-1 does, unless the ranking learns to interleave.

### L-3 — a downgraded shape lands entirely on the standard day

`journey_planner.plan_journey` downgrades a shape it cannot fill to `standard` with
`shape_reason="shape_needs_a_recall_step"` — honest, recorded, and the right call
for the learner's day. But it happened **12–30 times per 122 days** here, all of it
onto `standard`, and it is invisible to tomorrow's dice: `_day_shape_inputs` reads
yesterday's *stored* shape, so after a downgrade the dice exclude `standard` and can
deal the same shape that already failed. The consequences, both asserted:

* the served distribution can pass 50 % for `standard` where the deal never does
  (the test asserts the difference equals exactly the number of downgrades);
* two identical **served** days in a row are possible, and always sit next to a
  downgrade.

A fix worth considering: on a downgrade, fall back to the *next* eligible shape the
dice would have dealt rather than always to `standard`.

### L-4 — the Courrier's week is the wall clock, and nothing can be told otherwise

`missions.ensure_weekly` reads `date.today()`, `story_correspondence.story_letter_candidate`
and `open_chain_step` read `datetime.now(UTC)`, `error_memory` schedules against
`datetime.now(UTC)`, and `real_world_missions.created_at` is a SQL server default.
None of them accepts an injected clock at the call site the scheduler uses, so no
test can simulate a fortnight without patching six modules' `datetime` names (§1).
`lapse_overdue_letters` already takes `now=`; threading the same parameter through
`ensure_weekly`, `story_letter_candidate` and `_ensure_ad_hoc_letter` would make the
Courrier testable over time without a monkeypatched `datetime`.

### L-5 — no side stories in 126 days

WP-63 records a chapter that claims no arc stage as a `side_story`. With a fully
compliant director, **zero** appeared in either life: the gates (`entry_requires`,
`min_episodes_between_stages`) never blocked long enough for a chapter to claim
nothing. WP-63's own 200-day test does see them, so this is about how long it takes,
not about whether the mechanism works. Worth a look if side stories are meant to be
a normal part of a season rather than a rarity.

### L-6 — carried forward from the packages' own notes

`min_episodes_between_stages` is measured in `day_index` (settled exchanges), not
calendar days (WP-63 §6); the debrief's correspondent mood is one letter stale on a
payload written before the writeback (WP-65) — that one has since been closed in
`complete()` by `correspondent_mood_after`, which this run sees.

---

## 5. What was run

| Command | Result |
|---|---|
| `pytest tests/test_long_horizon_evidence.py` | **17 passed, ~30 s** (five consecutive clean runs) |
| `pytest tests/test_journey_letter_day.py` | 23 passed |
| `pytest tests/test_journey_planner.py tests/test_journey_contract_parity.py` | 149 passed |
| `pytest tests/test_journey_end_to_end.py` | 53 passed |
| `pytest tests/test_living_story_longitudinal.py` | 30 passed |
| `pytest tests/test_living_story_budget.py` | 9 passed — the two-attempt 75 s budget is untouched |
| `pytest tests/test_missions.py tests/test_story_correspondence.py tests/test_journey_story_outcomes.py tests/test_daily_journey_{api,state,concurrency,fixtures,migration}.py` | passed |
| `ruff check` on every changed file | clean |
| `python -m scripts.long_horizon_report` | two reports, ~29 s, no provider call |

Per file, never the whole suite (~35 min). No live provider call was made and
**nothing was spent**.

---

## 6. The paid live review — prepared, not run

These are the commands for the owner-consented paid review of the *prose* with the
new ledgers on. **Nothing here has been run.** The owner consents before any spend.

```bash
# A2 — fourteen days with the long memory, the season horizon and the day shapes
venv/bin/python -m scripts.review_living_story --live \
    --level A2 --days 14 --attempts 2 --seed wp68-A2-2026-09-21 \
    --max-requests 60 \
    --output var/reviews/atelier-story-review-A2-wp68.json

# B1 — the same fortnight one band up (register and the cast projection both
# depend on the band, so A2 says nothing about B1)
venv/bin/python -m scripts.review_living_story --live \
    --level B1 --days 14 --attempts 2 --seed wp68-B1-2026-09-21 \
    --max-requests 60 \
    --output var/reviews/atelier-story-review-B1-wp68.json
```

**Cost estimate.** `review_living_story.py` spends one request per draft and one per
turn, plus retries inside `--attempts 2`; `--max-requests 60` is the hard cap and
the script raises `review_request_limit` rather than exceeding it. The documented
comparators: WP-14's eight bounded runs were ~90 requests for about **US$0.15**
(`ENGINE-IMPLEMENTATION.md`), four bounded A1 runs came to **US$0.031**
(STATUS.md, 2026-09-08), and the 2026-09-17 calibration was **under US$0.15** for
33 calls (`CALIBRATION-2026-09-17.md`). At roughly **US$0.0017 per request**, a
14-day run of 30–60 requests is **≈ US$0.05–0.10**, and the two runs together
**≈ US$0.10–0.20** — worst case US$0.21 if both hit the cap. Each report's
`summary.estimated_cost_usd` is the actual spend; stop and report rather than
re-running if a run ends `stopped_early: review_request_limit`.

**What to read in the reports.** WP-62/63 changed what the director is *told*, so
the questions this review answers are new: does a callback to an old chapter read
as a memory or as a non sequitur; does the finale feel like an ending built from
this life; does the interlude read as a pause rather than a second ending; does a
`meanwhile` line sound like gossip from somebody who was there. The existing WP-17
acceptance thresholds (accepted days, distinct locations and characters, chapters,
median request time) still apply and are in `ENGINE-IMPLEMENTATION.md`.

---

## 7. Reading the season

`scripts/long_horizon_report.py` plays **this** harness — not a second
implementation of it — and writes `var/reviews/long-horizon-<seed>.md`: the season
at a glance, the rhythm of the days as one character per day, the chapter list with
its shape and whether it moved the season, what the chronicle kept from the very
beginning, the season's long questions and their state, the cast's off-screen weeks
with their witnesses, every letter with its chain position, deadline and outcome,
and the heaviest things the learner made true.

```bash
python -m scripts.long_horizon_report                 # both learners, 126 days
python -m scripts.long_horizon_report --days 60 --seeds A --out-dir var/reviews
```

There is no `--live` and there is nothing to pay for. The sample committed with
this package is `evidence/long-horizon-A-2026-09-21.md`.

## 7. The paid live review, first pass — 2026-09-21 (owner-consented)

Both §6 commands were run once. **Spend: US$0.158** (A2 US$0.127 for 29 requests, B1
US$0.031 for 7). The §6 estimate was wrong by ~3×: with the WP-62/63 ledgers a director
request is 10–12k tokens, **≈ US$0.0044 per request**, not US$0.0017. A capped 60-request
run is therefore ≈ US$0.26, and a full fortnight at two bands ≈ US$0.40–0.55.

| run | accepted | stopped on | verdict |
|---|---|---|---|
| A2 | 7 of 14 days | day 8, `repeated_situation` | guard **right**, director under-informed |
| B1 | 1 of 14 days | day 2, `repeated_premise_triple` | guard **wrong** (false positive) |

**B1, day 2 — fixed in `2512b68`.** The complication beat of an open chapter was refused
as a "repeat" of its own setup: same person, same café (a chapter is exactly that), and B1
objectives share their boilerplate ("…and give a short reason (one or two sentences)"), which
alone clears the 0.4 Jaccard bar. The open chapter's own scenes are now exempt from the
triple guard; the premise-twin, novelty-key and three-in-a-row rotation guards still hold them.

**A2, day 8 — fixed in `f0bbbc4`.** Measured offline against the accepted days: two of the
three refused resolution drafts re-asked day 7's task (objective overlap 0.83 — "choose 9h and
ask how the technician will enter"). The director only ever learned that from a rejection.
`chapter.already_asked` now goes out with the *first* draft, with the instruction to start from
the consequence. The final `StoryUnavailable` also carries every attempt's refusal as its hint
and the review script stores it (`reason_feedback`), so the next lost day explains itself.

**What the seven A2 days read like** (`var/reviews/atelier-story-review-A2-wp68.json`):
- Day-to-day coherence holds: chapter 1 (Marin's ring) runs setup → complication (Augustin's
  joke) → turn → resolution over four days, each scene starting from the previous answer;
  a learner who walks out on day 2 gets a *colder* Marin. Arc stages advance only on claimed
  content (`spark` → `near_confession` → `tentpole`), the season thread moves to `developing`,
  Marin's secret goes `hinted`, and chapter 2 is dealt the `letter` shape.
- Weak: chapter 2 repeats one stage direction three days running («Romy a le direct dans dix
  minutes», same newsroom) — under the 0.6 premise-twin bar, so no guard sees it; on day 4
  Augustin's reply parrots the learner's advice back as if advising himself; chapter 1's
  "resolution" settles the joke, not the proposal (fine for a season arc, but the learner is
  not told the proposal is still open).
- Not observable in 7 days: callbacks, plants paid, agendas/`meanwhile`, finale. Those need the
  full fortnight at least; none of the new ledgers produced a refusal.

Not re-run: the corrected cost exceeds the figure the owner consented to.

## 8. The paid live review, second pass — 2026-09-21/22 (owner-consented, 90-request cap)

Spend **US$0.350** (A2 US$0.143 / 33 requests, B1 US$0.207 / 46). Running total US$0.508.

| run | accepted | stopped on | cause |
|---|---|---|---|
| A2-b | 6 of 14 | day 7, `objective_too_complex` (+ triple) | guard counted the director's own «(one sentence, max two short clauses)» as extra asks; **and** the review script never stamped `chapter_title_fr`, so §7's two fixes were not exercised by the script at all |
| B1-b | 10 of 14 | day 11, `mixed_address_register` (+ triple) | same unstamped-chapter harness gap |

Fixed in `0110e0c` (parentheticals ignored by the A2 objective guard; the script stamps
chapters and projects `already_asked` exactly as production) and `7e3ec46` (below). Production
always stamped its rows — the harness gap inflated the script's loss rate, not the app's.

**What ten B1 days read like** (`var/reviews/atelier-story-review-B1-wp68-b.json`):
- Three chapters, three people, four places. Romy's Montréal-or-Paris chapter ends on a promise
  (the learner will come to Monday's pitch). Marin's ring chapter surfaces Lila's **Berlin
  envelope** — her secret entering through his arc, not dumped — and the `letter` shape really
  produces a note that falls out of the portrait and a written reply. Gus's chapter plants a
  Créteil postcard on day 9 and uses it on day 10. Plants are recorded; moods go colder on a
  refusal. This is the first run where the season reads like one life rather than a list of scenes.
- **Monotony of act** — nine of ten objectives were «tell X whether they should A or B, and
  give a reason». Settings rotate; what the learner *does* never did. `7e3ec46`: `speech_act`,
  `variety.recent_acts` / `act_rule` sent with every draft, a −1.5 score term on a third advice
  ask, and the director line. No hard guard on purpose: every lost day so far was a guard.
- Still weak, not fixed: objectives switch between French and English inside one run (the
  control language is not enforced); day 2's reply has Romy say «si tu préfères rentrer à
  Montréal» to the learner (role slip); `secret_shift: hinted` is re-emitted every scene; no
  setup used the offered callback in ten days (it is only rewarded on dual drafts).

## 9. The paid live review, third pass — 2026-09-22 (owner-consented, 90-request cap)

Spend **US$0.416** (A2 US$0.256 / 58 requests, B1 US$0.160 / 35). Running total **US$0.924**.
These runs loaded the engine at `7e3ec46`; the fixes after it (`2acf022`, `ba62a77`,
`4ddd656`, `3ef8434`) are not in them.

| run | accepted | fallbacks | stopped on |
|---|---|---|---|
| A2-c | **14 of 14** — the first full fortnight | 0 | — |
| B1-c | 7 of 14 | 1 (day 7 turn, critic: invented reply) | day 8, `mixed_address_register` ← `objective_too_thin` ↔ `repeated_situation` |

**A2-c reads like a life**: four chapters, five people, five places. Marin's ring (Lila's
secret goes `revealed` on day 4, the season thread `closed`) → the radiator repair with Romy
(a letter chapter: a note from the syndic, a written reply, Margaux hands over the repairer's
note on the resolution) → Gus's «Méthode» lesson at the brocante with the Créteil parcel
(his secret, not yet surfaced) → Lila's hidden portrait and Berlin letter. Weakness: once advice
was discouraged, eleven of fourteen objectives became *arrange a time* — fixed in `3ef8434`
(`speech_act` now knows `scheduling`, and the rule is generic: two same acts in a row → a
different one). Marin's ring resolves as «Marin, vas-y» — the proposal itself never lands.

**B1-c regressed on variety**: seven days, all Romy, five in the learner's flat; chapter 2
replays chapter 1 (the Montréal visitor on Sunday) and claims an earlier arc stage than chapter 1
reached. The day-5 callback worked, but pulled the new chapter back into the old one. Fixed in
`4ddd656`: a callback is a line, never a replay; `variety.previous_lead` and a −1.0 score term
on a setup led by the last chapter's lead. Day 8 was the guard pincer again — one "will you
stay with her" promise reworded until `objective_too_thin` and `repeated_situation` refused
every draft.

Open, not fixed: arc stages can be *claimed* backwards (`arc_stage_id` earlier than the stage
already reached — the writers ignore it, the prompt does not know); the B1 guard pincer (thin ↔
repeat) has no exit except a new situation; `secret_shift: hinted` is re-sent every scene.
