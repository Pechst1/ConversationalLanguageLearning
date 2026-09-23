# Work packages — 2026-09-23 (learning): a ten-minute day that actually teaches

Owner brief (2026-09-23): the daily session should take **8–10 minutes**; a learner can choose a
**longer session and reach the higher CEFR levels faster**; check how level progression, grammar
teaching, spaced repetition and the weaving of new concepts into the exercises work today, and
rework what needs it.

Numbering: **WP-L1 … WP-L9** (L for learning), so they never collide with Codex's WP-86/87 or the
design packages WP-D1…D8. WP-L5 and the checkpoint half of WP-L7 touch the story engine and are
planned **with Codex**.

## 1. Verdict

The story day is good, but it is not yet a curriculum. Four things hold it back:

1. **The day is locked at five minutes.** `BudgetSeconds = Literal[300]`
   (`app/schemas/daily_journey.py:56`), and the planner fails the day if scene + reply + ending
   go over it. The learner's «Time per edition» setting (`daily_goal_minutes`, Réglages) changes
   nothing in the journey. The planner has a per-learner pace model but is always called with
   `pace=None` (`daily_journey.py:2327`).
2. **The level cannot rise past A2.1 by measurement.** A2.2 needs 75 mastered grammar concepts and
   B1.1 needs 110 (`cefr_progress.py:23-32`), but only 54 concepts are active (12 per level
   A1–B2, 6 at C1). The other 314 legacy rows are inactive. The word thresholds (300 / 700 /
   1200 / 2000) count any progress row, while the core lexicon has 821 lemmas and only 118 at B1.
   There is no checkpoint, and the owner's goal «20 min/day for 50 days → A1.2» is not backed by
   anything.
3. **The daily journey never introduces grammar.** A new concept can only come from the legacy
   Atelier drill session, which is now the side surface «Plus de pratique». The story engine
   receives no grammar at all: the director sees errata hints and vocabulary, never a concept.
   So the scene cannot showcase a new form or ask a question that needs it.
4. **Grammar memory is leaky.**
   - Journey targets use the concept's **English** catalogue name as the French label
     (`journey_learning.py:341-348`, `unified_srs.py:609`).
   - Errors in story replies become errata **without a concept**, so a mistake never makes a
     concept due.
   - Journey credit ignores history and always gets the first-review interval.
   - Grammar has no stored ease: SM-2 ease is always 2.5.
   - Mastered concepts are excluded from every due query, so they are never reviewed again
     (`grammar.py:275-278`).
   - The cold-start picker can re-serve a studied concept as "new" (`atelier.py:1736-1758`).
   - Prerequisites are never read.

What already works and stays:
- the story-first day, the four-shape plan and the Seal;
- the deterministic no-spoil item builders (`journey_planner.py:923-986`), the three gates for
  generated sets, and the errata memory (retires after 3 repairs on separate days);
- the unified queue (vocabulary, grammar, errata, conjugation in one list);
- `measure_journey_duration` (active time from events, pauses removed);
- the x-ray sentences and marks already in the grammar TSV.

## 2. The model

### 2.1 The séance: four movements, sized by the learner's rhythm

The four shapes stay the day's plan (WP-D1). Each movement gets a share of the budget, so a longer
rhythm makes the movements longer, not more numerous.

| Movement | Shape | What happens | Share of the budget |
| --- | --- | --- | --- |
| **Rappel** | yellow square | Mixed spaced reviews: due words, due concepts, one erratum repair. Quick deterministic items, interleaved. | ≈ 35 % |
| **Scène** | blue circle | The episode. On an introduction day the scene carries the new form 2–3 times, highlighted, followed by a 30-second rule card and 3–4 guided items built from the scene's lines. | ≈ 30 % |
| **Réponse** | red triangle | The conversation turns. The character's question **needs** today's new or due concept. | ≈ 25 % |
| **Bouclé** | ink square | One retrieval of today's new word and form (the end-of-session test), the ending, the Seal. | ≈ 10 % |

The Rappel moves to the front on purpose: retrieval first, story second, and the day ends on the
story's teaser and not on drills.

### 2.2 Rhythm: the learner chooses minutes, the minutes buy intake

A longer session is only faster if it teaches **more new material** and the reviews keep up. So
the rhythm sets both the budget and the intake:

| Rhythm | Minutes | New words / day | New concepts / week | Story |
| --- | --- | --- | --- | --- |
| Léger | 5 | 2 | 1 | 1 episode, 1 reply turn |
| **Régulier (default)** | **10** | 4 | 2 | 1 episode, 2 turns |
| Soutenu | 20 | 8 | 3 | 1 episode, 2–3 turns + the Atelier's drills in the Scène movement |
| Intensif | 30 | 12 | 4 | as Soutenu, plus a letter or listening block |

- **One episode per day on every rhythm.** The daily cliffhanger is the retention hook, and
  engine cost stays flat. Longer rhythms add practice and intake, not story.
- **Auto-throttle.** If the due backlog is more than 1.5 days of review capacity, or review
  accuracy over 7 days falls below 80 %, new intake halves until it recovers. The learner sees
  «Cette semaine, on consolide.»
- **«Encore 5 minutes»** after the Seal: an optional block of reviews only. It never advances
  the story and never counts twice for the streak.
- `daily_goal_minutes` becomes the rhythm (5 / 10 / 20 / 30). Onboarding asks for it after the
  first win (WP-75); Réglages changes it.

### 2.3 What that means for the level (planning prior, to be calibrated)

A1 as proposed in WP-L2 is about 30 grammar units and about 600 words. Intake alone gives the
earliest A1 finish:

| Rhythm | Words (600) | Grammar (30 units) | Earliest A1 finish |
| --- | --- | --- | --- |
| Léger 5 | 300 days | 210 days | ≈ 10 months |
| Régulier 10 | 150 days | 105 days | ≈ 5–6 months |
| Soutenu 20 | 75 days | 70 days | ≈ 3 months |
| Intensif 30 | 50 days | 53 days | ≈ 2 months |

Two consequences:
- **Double the minutes, roughly double the pace**, as long as review accuracy holds.
- **Coverage alone would overclaim.** Classroom norms put A1 at about 60–80 guided hours, and
  Régulier's 5 months is about 25 hours. That is why promotion also needs the band's
  checkpoint (WP-L7), and why the forecast becomes measured as soon as there are 7 active days
  (WP-L8).

### 2.4 A concept's life

| Day | Stage | What the learner does | Evidence written |
| --- | --- | --- | --- |
| N | **Rencontre** | Reads the scene; the new form appears 2–3× and is highlighted (x-ray marks). Tapping it opens the rule. | exposure (no credit) |
| N | **Règle** | 30-second card in the learner's language: one-sentence rule, the pattern drawn in shapes, two examples taken from today's scene, one trap. | — |
| N | **Essai** | 3–4 guided items from the scene's lines: recognise → choose → build (tiles) → transform. | weak / medium |
| N | **Emploi** | The character's question needs the form; the reply grading reports concept evidence (used correctly, used with an error, or avoided). | strong |
| N+1, N+3, N+7 … | **Rappel** | One interleaved item in the Rappel movement, mixed with other concepts and with its contrast partner. Formats get more productive as stability grows. | per format |
| later scenes | **Réemploi** | The director weaves due concepts into scenes and questions (≤ 2 per day). | strong |
| — | **Tenue** | Held = correct free use on 2 separate days at least 7 days apart, plus one correct spaced item after at least 14 days. Held concepts keep coming back on long intervals. | — |

An error in any reply is mapped to its concept. That is a lapse: the concept comes back sooner,
and the next scene gives the learner a chance to repair it.

## 3. Packages

#### WP-L1 · Grammar plumbing: make the existing loop honest (first, small)
- Journey grammar targets: `label_fr` = a French anchor form of the concept (from
  `anchor_examples` or `name_fr`); `label_native` = the localized concept name.
- Errata from journey replies carry `concept_id`: route them through the inference that
  `record_detected_error` already does. A journey-side erratum repair credits the linked concept,
  as the unified queue's repair already does.
- Journey grammar credit uses the concept's history (reps and previous interval), not the
  first-review table.
- Mastered concepts stay in the due query at their long interval.
- The cold-start picker excludes concepts the learner already has progress on, and checks
  prerequisites once WP-L2 stores them.
- `mark_concepts_practiced_in_context` stops distorting the interval: either set `next_review`
  or stop touching `last_review`.
- The critic, when disabled or unreachable, no longer rejects every generated set
  (`atelier.py:2415-2419` requires a verdict for every item, and it returns `[]`). A validator-only
  pass is recorded as such.
- Wire or delete the dead settings: `new_words_per_day`, `daily_goal_xp`, `new_grammar_limit`,
  and the unused frontend `getUnifiedSRSQueue`.
- **Done when:** one test per item; `pytest` is green; a journey reply that says «je suis allé
  au le café» makes the articles concept due tomorrow.

#### WP-L2 · The syllabus: teachable units, words and can-dos per sub-band
- **Grammar catalogue v2, about 150 teachable units** (A1 ≈ 30, A2 ≈ 35, B1 ≈ 40, B2 ≈ 45).
  - Built by splitting the 54 coarse concepts (e.g. «Present tense core verbs» becomes -er
    verbs / être-avoir / aller-faire / -ir-re) and mining the 314 inactive legacy rows, which
    are already finer: numbers, time, dates, quantities, contractions and so on.
  - Every unit has: a one-sentence rule in **en / de / fr**, the pattern, 2 anchors, 1 trap, its
    contrast partners, prerequisites, an x-ray sentence and marks, and a **detector spec** (how
    to recognise its use in free text: a deterministic pattern where possible, otherwise an
    LLM-checked description).
  - Every unit is tagged to a sub-band (A1.1 / A1.2 / …).
- **Lexicon to about 2,500 lemmas through B1**, tagged by sub-band, from an open frequency list
  (e.g. Lexique 3; check the licence) plus the story's own world vocabulary.
- **Can-do list per sub-band**: 6–10 functional tasks («commander au café», «proposer un
  rendez-vous», «raconter sa journée d'hier»). The season finale's checkpoint scene tests these
  (WP-L7).
- Authoring runs as LLM drafts with human review against a checklist. Catalogue rows are
  versioned (`catalog_version`), and learners' progress on retired units migrates to the units
  that replace them.
- **Done when:**
  - the catalogue loads and every unit has a localized rule, a detector and a sub-band;
  - counts per sub-band are published in this doc;
  - a sample of 20 generated sets passes all three gates;
  - existing learners' progress maps without loss.

#### WP-L3 · One memory model for everything
- Grammar and errata move to the FSRS-style scheduler that vocabulary already uses
  (`app/services/srs.py`): per-item stability and difficulty. The migration adds the columns to
  `user_grammar_progress` and seeds them from `score` and `reps`.
- Evidence weights by format: recognise < choose / build < transform < free use in a reply.
  Free use is the only way to «Tenue».
- One queue: the unified queue becomes the single source of every day's reviews, for the journey,
  «Encore 5 minutes» and «Plus de pratique».
- Interleaving rules for the Rappel: at least 3 different sources per block, no two items of the
  same concept back to back, and a concept's contrast partner at least once a week once both
  are introduced.
- **Done when:**
  - a scheduler simulation shows intervals growing with success, collapsing on a lapse, and held
    concepts returning at least every 60 days;
  - the review load per new item is measured, as the input for WP-L6's throttle.

#### WP-L4 · The concept's life inside the day
- An **introduction day**:
  - the planner takes the next unit from the intake plan (WP-L6), respecting prerequisites;
  - the Scène movement shows the x-ray highlight, the 30-second rule card (shape-drawn pattern,
    learner's language) and 3–4 guided items built deterministically from the scene's lines;
  - the Réponse requires the form.
- **Concept evidence in reply grading.** Detectors from WP-L2 run first; the existing reply grader
  also returns `concept_evidence[{concept_id, outcome: correct | error | avoided, span}]`, with no
  extra LLM call. «Avoided» is neutral, not a lapse.
- Rappel formats scale with stability: low → recognise / choose, medium → build / transform,
  high → a free-use prompt inside the reply.
- **Done when:**
  - an end-to-end test follows one concept for 21 simulated days: introduced, practised, used,
    lapsed, repaired, held;
  - an introduction day stays inside the Régulier budget.

#### WP-L5 · The story knows the grammar (engine, with Codex)
- The director gets a `grammar_plan`:
  - `introduce` (0–1 unit);
  - `weave` (≤ 2 due units);
  - `allowed` (the introduced set plus the level's scaffolding);
  - `avoid` (above-level structures).
- The scene validator checks that the new form appears at least twice in the character's lines,
  and that above-level grammar stays under an allowance. It repairs or falls back as the no-spoil
  gates already do.
- The character's question is written to need the target concept. Letters get the same plan.
- **Done when:**
  - the 126-day harness reports that at least 90 % of introduction days carry the form in the
    scene and the reply;
  - the above-level rate is below the threshold;
  - engine cost per day is unchanged within 10 %.

#### WP-L6 · The day composer and the rhythm
- `BudgetSeconds` becomes the learner's rhythm (300 / 600 / 1200 / 1800). The four movements get
  their shares (§2.1), and the planner's caps (steps, recalls, warm-ups) scale with the budget.
- The planner is fed the measured pace profile (`pace=None` goes away) once there are 3
  measured days; before that, it uses the priors.
- Intake plan per rhythm (§2.2), with the auto-throttle.
- Soutenu and Intensif fold the Atelier drill machinery into the Scène movement, so «Plus de
  pratique» and the day share one engine and one concept picker.
- «Encore 5 minutes» after the Seal.
- Rhythm choice in onboarding and Réglages: four cards showing minutes, what is in the day and
  the honest forecast (WP-L8). `daily_goal_minutes` becomes the rhythm.
- The mark keeps four shapes at every rhythm.
- **Done when:**
  - planner tests pass per rhythm;
  - the planned Régulier day is 8–10 min at the prior pace;
  - Léger still fits 5 min;
  - no rhythm plans a second episode.

#### WP-L7 · The level: syllabus coverage plus a checkpoint
- Replace the absolute thresholds (`CEFR_THRESHOLDS`) with coverage of the current sub-band:
  - at least 85 % of the band's units held;
  - at least 80 % of the band's words known (retrievability ≥ 0.85);
  - the band's **checkpoint** passed.
- **Checkpoint = the season finale** (with Codex, WP-63 already has finales):
  - a longer scene that asks for the band's can-dos in free replies, graded by concept evidence;
  - failing it is soft: the finale repeats in a new situation after a week of consolidation.
- Home shows the sub-band with its progress («A1.1 · 60 %»), and «Votre dossier» explains every
  number.
- Demotion stays invisible: fragile items simply come back.
- A placement still sets the starting band. The declared or placed prior yields to measurement
  as it does today.
- **Done when:**
  - unit tests cover promotion, the checkpoint and migration of current estimates;
  - no learner's shown level drops on release day.

#### WP-L8 · An honest forecast
- Before 7 active days: the §2.3 prior for the learner's rhythm, as a range.
- After 7 active days: remaining band units and words ÷ measured intake, scaled by measured
  retention and bounded by the checkpoint, as a range.
- It is shown when choosing a rhythm («À ce rythme : A1 terminé vers mars»), in the Dossier, and
  at the Seal once a week. It is never shown as a promise before it has been measured.
- The unbacked «20 min/day for 50 days → A1.2» goes. By the prior, A1.2 at 20 min/day is about
  1.5 months of intake plus the checkpoint.
- **Done when:** the forecast matches WP-L9's simulation within ±20 %.

#### WP-L9 · Measure it
- Each step records when it started. Today only `completed_at` exists; alternatively derive the
  start from the `step_completed` event of the step before.
- The daily rollup reports real session p50 / p90 per rhythm (`measure_journey_duration` already
  computes active time).
- The 126-day harness gains, per rhythm:
  - minutes per day and graded interactions per day;
  - new items per day and review load;
  - the level reached by day 30 / 60 / 90 / 126, with a simulated learner at 70 % / 85 % /
    95 % accuracy.
- **Done when:**
  - the harness report shows all four rhythms;
  - in the pilot, Régulier's real p50 over the first 2 weeks is 8–10 min;
  - Léger's p50 is at most 6 min.

## 4. Order

1. **WP-L1** now. Small and independent; everything later assumes the loop is honest.
2. **WP-L2 and WP-L3 in parallel**: the syllabus content and the memory model.
3. **WP-L6** (composer and rhythm) once WP-L3's queue exists. **WP-L9**'s timing half goes with
   it, so the 8–10 minutes is measured, not asserted.
4. **WP-L4**, then **WP-L5** with Codex. The engine needs the `grammar_plan` contract first.
5. **WP-L7 and WP-L8** last: they need the syllabus, the memory and real measurements.

The simulator walk at the end of each step covers both themes, three learner languages and all
four rhythms.

## 5. Owner decisions

1. Rhythm names and minutes: Léger 5 / **Régulier 10 (default)** / Soutenu 20 / Intensif 30.
2. One episode per day on every rhythm (recommended), rather than more story for Intensif.
3. The season finale as the level checkpoint.
4. Syllabus authoring: LLM drafts plus human review. Who reviews the French, and the licence for
   the frequency list.
5. Showing the forecast honestly, even when it is sobering: A1 at Léger is about 10 months.
