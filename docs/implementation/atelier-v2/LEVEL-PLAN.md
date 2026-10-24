# Level plan — the exact level, what is left, and what it costs

2026-10-24. Owner: «we always know exactly at which level the learner is currently so that
he also knows that exactly and knows what he has to do and how much time he has to invest
to advance further».

## 1. The problem

* **Three surfaces, three numbers.** The stored CEFR payload is a snapshot, written when a
  day, an épreuve or a recompute ends. A word the learner settled in the deck since, or a
  rule La Forge held, was missing from it until the next one. WP-130 A made the grammar
  counts live on the read; the words and the forecast were not, so Home, the Dossier and
  Fortschritt could print different counts for the same learner on the same minute.
* **A percent, not a plan.** Fortschritt printed the band, a percent and one forecast line.
  It did not say which rules the band still needs, what each one is missing or when it can
  be held at the soonest, how many words are already on their way in the reviews, what the
  days ahead cost in minutes, or how much time the learner has already put in.
* **A forecast that ignored the learner's plan.** Before seven active days WP-L8's prior
  read the rhythm's intake (`PRIOR_INTAKE`), so a learner who picked «Schnell» on the Tempo
  sheet read Régulier's forecast. And the range's low end could fall before the day the
  «Tenue» rules make possible at all.

## 2. What shipped

### 2.1 One live level — `cefr_progress.live_level`

Every read runs the engine's own arithmetic without writing (`recompute(persist=False,
track=False)`): `GET /progress/cefr`, `GET /atelier/today` (Home), the Dossier's level
belief (`learner_model._level_belief`) and the new plan. They agree with each other and
with the last answer. `write_first=True` keeps the old lazy first payload for a learner who
has none yet; the Dossier and the plan pass `False` and never write. A failed recompute
falls back to the stored payload with the live grammar (WP-130 A), then to `current`.

### 2.2 The plan — `GET /api/v1/progress/level`

`app/services/level_plan.py::build_level_plan`, schema `LevelPlanResponse`. Read-only.

| Block | What it says | Source |
|---|---|---|
| `band`, `percent`, `label`, `verified` | the band in force and its percent | `live_level` (the same payload as `/progress/cefr`) |
| `ladder` | every band: passed (épreuve), credited, below the start, current, ahead; the goal marked | `level_checkpoint.rows_by_band`, `cefr_target_level` |
| `rules` | held / required / total, practising, introduced, not met; each unit with its stage, what «Tenue» still lacks, the soonest it can be held, whether today owes it an opportunity, when a new one arrives at the planned intake | `concept_life.held_missing`, `earliest_held_at`, `held_opportunity` |
| `words` | known / required / total; on their way (a card, not known yet); still to meet, and the days that takes at the plan's words a day; known from reading | `level_coverage.lemma_states` |
| `epreuve` | locked, ready (in the story when WP-94 stages it), failed with its retake day, passed | the band's checkpoint view |
| `time` | the estimate, its basis, the rules' floor, the minutes a day and the hours that makes, the pace | §2.3 |
| `invested` | the practice time measured in the band, split scenes / La Forge / words, and the recent minutes a day | `practice_time` |
| `goal`, `skills` | the goal's words and rules left with its ETA; how far the words alone and the rules alone reach | the band word lists and unit bands |
| `evidence` | what turns a declared or placed level into a measured one (40 marked answers in two weeks) | WP-45 D-5 |

### 2.3 The time model

* **Estimate.** WP-L8's forecast, unchanged in shape. The prior (fewer than seven active
  days) is now the learner's own plan, `level_forecast.planned_intake`: the Tempo sheet's
  pace, else the words-a-day setting, else the rhythm. After seven active days it is
  measured, as before. Units already on their way spend the part of their hold lag they
  have already lived (`pending_elapsed_days`, now filled in).
* **Floor.** `level_forecast.earliest_cover_days`: every opportunity taken and every answer
  right, the soonest the band can be covered and its épreuve taken. A unit on its way is
  held when its last «Tenue» condition opens (`concept_life.earliest_held_at`: the spaced
  success 14 days after the introduction and 20 h after the last contact, the second free
  use 7 days after the first); a new unit arrives at the planned weekly intake and is held
  14 days later; a new word is met at the day's quota. The range never starts before it,
  and the card says so: «not before …, however much you practise».
* **Cost.** The estimate's days times the minutes a day: the learner's measured average
  over the last two weeks once the forecast is measured, else the minutes the plan takes
  (the Tempo sheet's arithmetic, `daily_session.pace_option`). Shown as an hours range.
* **Time put in.** `practice_time` counts each minute once: the journey recap's active
  seconds, standalone La Forge séances (`forge_metrics.active_seconds`, idle-capped), and
  the word deck's time between answers (two answers more than 120 s apart are a break)
  outside the stretches those two clocks counted (`journey_events.active_windows`,
  `forge_metrics.active_windows`). A review made while a scene was paused is the deck's,
  not lost in the scene's span. Le Courrier and Le Papier are not timed yet, and the card
  says so.

### 2.4 The card — Fortschritt «Le cours»

`web-frontend/components/releve/LevelPlanCard.tsx` (view model `level-plan-model.ts`, copy
`level-plan-copy.ts` in English, German and French, styles `.av2 .nb-lv*` in
`CahierV2.tsx`). Top to bottom: the band and its percent with the ladder; what the next
band still needs (rules, words, the épreuve) and what today can move; how long, what it
costs a day and the pace, with «Change pace» opening La Une's own Tempo sheet (the plan is
read again after a change); then, folded, the band's rules one by one, the time put in, and
each criterion on its own. The Relevé keeps its previous level block as the fallback when
the plan cannot be read.

## 3. Honesty rules

1. **WP-25.** A declared or placed level gets no gauge, no forecast, no hours and no goal
   date. The card shows the counts as «so far in the app», the evidence line (40 marked
   answers in two weeks, N so far) and says that a time comes once the level is measured.
2. **An estimate is labelled one.** «Estimate from your plan» before seven active days,
   «at your pace» after, with its basis line; a capped forecast promises neither a date
   nor hours.
3. **No write on a read.** `GET /progress/level`, `GET /progress/cefr` (after the first
   payload) and the Dossier write no history row, no checkpoint row and no payload
   (`tests/test_level_plan.py`).

## 4. Tests

* `tests/test_level_plan.py` (20): every surface prints the same band and percent and the
  plan writes nothing; a unit held since the snapshot moves the level on the next read;
  WP-25 for a declared level; each unit's stage, missing evidence, soonest day, owed today
  and arrival; the words split; `earliest_held_at`, `earliest_cover_days` and the range
  floor; `practice_time` counting each minute once (a review in a paused scene is the
  deck's); measured and planned minutes; the capped and missing forecasts; the ladder,
  the goal and the criteria.
* `tests/test_wp_l8_forecast.py`: the prior's range follows the plan and starts no sooner
  than the floor.
* `web-frontend/components/releve/level-plan.test.js` (18): the view model in all three
  languages, WP-25, the time lines, the rules list, number and date formatting.

## 5. Open

* Le Courrier and Le Papier time is not measured yet; once it is, `practice_time` adds it.
* Once the forecast is measured, the minutes a day are the last two weeks' average: after
  a pace change they follow over the next two weeks, not at once.
