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
- **Status (2026-09-23): delivered behind a flag, content is an LLM draft awaiting review.**
  - `ATELIER_GRAMMAR_CATALOG_VERSION` (default `v1`) selects the catalogue. Nothing changes
    until the owner sets it to `v2`.
  - Grammar catalogue `fr-core-v2`, `templates/french_core_grammar_v2.tsv`: 153 units, all
    `review_status=draft`.

    | Sub-band | A1.1 | A1.2 | A2.1 | A2.2 | B1.1 | B1.2 | B2.1 | B2.2 | Total |
    | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
    | Units | 18 | 16 | 18 | 16 | 20 | 20 | 22 | 23 | **153** |
    | Band | A1 34 | | A2 34 | | B1 40 | | B2 45 | | |

    - Every unit has: a sub-band; prerequisites and contrast partners (acyclic, always earlier
      in the teaching order); a detector (146 regex, 7 `llm:`); a name and a rule of at most
      20 words in en/de/fr (jargon-free at A1–A2); and a ✗→✓ trap as the first trap.
    - `is_foundation` now means "another unit depends on it" (99 units).
    - A1 follows the communicative order in due diligence §2.4, and the §2.3 misplacements
      are fixed.
    - C1 is out of scope for v2. The six v1 C1 concepts map to their nearest B2 unit.
  - **Loader**:
    - `FrenchCoreGrammarCatalog(db, version)` stores v2 prerequisites as concept ids and the
      syllabus fields in `source_refs.syllabus`, with helpers `concept_sub_band` and
      `detector_matches`.
    - It writes real en/de/fr rows to `grammar_concept_localizations`.
  - **Migration rule** (`templates/french_core_grammar_v1_to_v2.tsv`, which covers all 54 v1
    ids):
    - The first listed v2 unit, the foundation child, inherits the learner's v1 row
      (score, reps, state, reviews). The other children start fresh.
    - On merges, the strongest row wins (score, then reps, then latest review).
    - Existing v2 progress is never overwritten.
    - v1 rows are copied, not moved. Switching back to v1 restores v1 unchanged.
    - v1 concepts are archived with `replacement_external_id`.
  - **Prerequisites** in `select_today`:
    - A unit is introduced only once its prerequisites have progress rows.
    - A prerequisite in a CEFR level below the learner's own counts as known.
    - v1 has no prerequisites, so its picks are unchanged.
  - **Lexicon** `fr-core-lexicon-v2`:

    | Sub-band | A1.1 | A1.2 | A2.1 | A2.2 | B1.1 | B1.2 | Total |
    | --- | --- | --- | --- | --- | --- | --- | --- |
    | Lemmas | 384 | 322 | 398 | 396 | 543 | 541 | **2,584** |

    - Irregular forms: 3,599.
    - The content is an LLM draft; no dataset was copied.
  - **Can-dos** (`app/data/syllabus/fr_core_can_dos_v2.json`): 58 tasks, 7–8 per sub-band.
    Each lists its unit ids and lemma ids.
  - **Tests**: `tests/test_wp_l2_syllabus.py`.
  - **Before flipping to v2** (open):
    - Human review of the TSV, lexicon and can-dos.
    - Authored séance challenges for v2 units. `seance_curriculum` and
      `app/data/seance_challenges.txt` are v1-only, so v2 units use the generic fallback
      prompts.
    - The "20 generated sets pass all three gates" sample.
    - Decide whether errata (`user_errors.concept_id`) on v1 concepts should be remapped to v2.
      Today they drop out of the due list once v1 is archived.

- **Owner decisions (2026-09-23):**
  - **Errata are remapped** when v2 is active. Each open erratum moves to the v2 unit whose detector matches its correction, falling back to the first mapped unit. The v1 id is kept in `error_metadata.v1_concept_id`, and switching back to v1 restores it. Retired errata are untouched.
  - **The B2 normative calls are accepted:** laisser + infinitive has no agreement (1990 reform), après que + subjonctif is marked wrong, and au cas où + indicative is marked wrong.
  - **Compound numbers are in the lexicon:** 98 lemmas covering 17–99 in traditional and 1990 hyphenation, plus hundreds and thousands in 1990 spelling. They are A1.1 below 70 and A1.2 from 70 up.

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
- **Status (2026-09-23): landed.**
  - **Model** — `app/core/srs/memory.py`: stability/difficulty/lapses moved by the vocabulary
    scheduler's own formulas (`FSRSScheduler`, retention 0.9, so interval = stability in days);
    a lapse comes back in 1 day; **no interval exceeds 60 days** (stability keeps growing to 365).
  - **Migration** `d1f3a5c7e9b2` (after `c4d6e8f0a2b3`, additive) adds the three columns to
    `user_grammar_progress`, seeded from the SM-2 fields: S = `next_review − last_review` in days
    (≥ 1; without that pair the old seed table for the score: ≥9→30, ≥7→14, ≥5→7, ≥3→3, else 1;
    cap 365); D = clamp(5 + (5 − score)·0.6, 1, 10); lapses = 1 if score < 5. `score`/`state`
    unchanged (display, CEFR counts). A row without stability is read with the same formula.
  - **Evidence → rating** (one table, `grade_evidence`; `assisted` = one step down; the weight
    scales the rating's stability gain):

    | step | evidence | right | wrong |
    | --- | --- | --- | --- |
    | 0 | recognise, assisted | Good × 0.25 | Hard |
    | 1 | recognise (choice / classify / fill) · guided, assisted | Good × 0.5 | Hard |
    | 2 | guided (tiles / word bank / build) · transform, assisted | Good × 1.0 | Hard |
    | 3 | transform · production, assisted | Easy × 0.75 | Hard; **production: Again (lapse)** |
    | 4 | free production in a reply | Easy × 1.0 | **Again (lapse)** |
    | — | mention in context | no schedule change | — |
    | — | self-rated Rappel card | its own rating | — |

    Every grammar credit path goes through `apply_grammar_evidence` (Atelier `record_review`
    with the session's strongest format, journey `_apply_grammar_credit`, erratum-linked credit,
    live-session replies, Rappel cards, mentions); a test pins it as the only writer of
    `next_review`.
  - **Errata** use the same model (`ErrorMemoryService.review_error`; a recurrence collapses S as
    an Again); three correct repairs on separate days still retire them. The daily-practice error
    card's private interval table is gone.
  - **One queue** — `UnifiedSRSService.plan_review_items(user_id, budget_seconds=, now=)`: all
    due vocab / grammar / errata / conjugation, interleaved in blocks of 6 with ≥ 3 sources when
    available, never the same concept back to back (an erratum counts as its concept), sized in
    `RAPPEL_ITEM_SECONDS` (vocab 10 s, grammar 40 s, erratum 25 s, conjugation 20 s). A due
    concept's contrast partner (`contrast_partners` column or `source_refs["contrast_partners"]`,
    ids or external ids — WP-L2 fills them) joins when both are introduced and it was not seen for
    7 days; no data → no-op. «Plus de pratique» (interleaved mode) uses the same interleaver. The
    journey's candidate pool is unchanged (it re-ranks by scene); WP-L6 wires the planner.
  - **Simulation** (`app/core/srs/simulation.py`, seeded; 1 new item/day introduced as a guided
    item + a use in the reply; every due item reviewed on its day with a format that scales with
    stability; fixed accuracy). Reviews per day **per new item per day**:

    | accuracy | days 30–60 | days 60–90 | **days 90–120** | days 335–365 | lapses (120 d) |
    | --- | --- | --- | --- | --- | --- |
    | 70 % | 8.5 | 12.5 | **13.5** | 28.8 | 52 |
    | 85 % | 5.9 | 6.5 | **8.1** | 14.4 | 30 |
    | 95 % | 4.0 | 4.9 | **5.9** | 10.6 | 9 |

    Self-rated cards (right → Good, wrong → Again), days 90–120: 22.6 / 10.6 / 8.0. Intervals never
    shrink on a success, fall to 1 day on every lapse, and over 365 days the longest gap is exactly 60.
    **For WP-L6:** the load does not plateau — the 60-day cap puts a floor of 1/60 review per day
    under every item ever learned, so it keeps rising slowly (at 85 %, ≈ +0.8 review/day per new
    item/day each further month). At 85 % and 40 s a grammar review, one new concept a day costs about
    5½ minutes of Rappel a day by month four.

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
- **Status (2026-09-24): landed** (v1 default and v2 flag; `tests/test_wp_l4_concept_life.py`).
  - **Intake** — `concept_life.introduction_for_today`: the rhythm's weekly quota (Léger 1,
    Régulier 2, Soutenu 3, Intensif 4; `intake_throttle_factor` applied), spread out
    (`7 // quota` days apart), picked by `AtelierScheduler.next_new_concepts` — the Atelier's
    cold-start picker, now shared (band walk, teaching order, prerequisites). Practice days only.
  - **Stages** — migration `f2a4c6e8b0d1` (after `e1f3a5b7c9d2`) adds `introduced_at`,
    `free_use_first_at`, `free_use_last_at`, `spaced_success_at`, `held_at` to
    `user_grammar_progress`. `apply_grammar_evidence` calls `note_concept_evidence` for every
    observation. Advancing the Règle step introduces the unit. WP-L7 reads `concept_stage`
    (`new · introduced · practising · held`), `held_concept_ids` and `introduced_concept_ids`.
  - **Tenue** — correct, unassisted free use in a reply on two days ≥ 7 apart, plus one correct
    spaced item (recognise / guided / transform / rated) ≥ 14 days after `introduced_at`.
    `held_at` is written once and never cleared (demotion stays invisible).
  - **Introduction day** (practice day) — scene → `StepKind.RULE` (the WP-L10 card; authored
    for v1 ids, else built from v2 `rule_short` per locale, x-ray sentence with marks, anchors
    as rows, first ✗/✓ trap; headline swapped for a scene line the detector recognises) →
    3–4 guided items from `grammar_items` (recognise: which sentence uses the rule · choose:
    the ✗/✓ pair · build: word bank with the ✗ word as spare chip · transform: correct the ✗
    sentence, second pair when there is one) → the day's other builds → the reply, whose
    first grammar target is the unit. The card and items are reserved first; items drop from
    the strongest end before the introduction is given up. At Régulier with a 16-item queue:
    ≈ 550 s of 600 (rule 33 s, guided items ≈ 63 s); Léger fits 300 s.
  - **Evidence** — recall observations carry `task_format`: choice → recognise, tiles /
    word bank → guided, transform → transform; the reply → free production. One success a day
    moves the schedule (later ones that day fold, but still feed the life); failures always
    land (a wrong guided item is a Hard, not a lapse).
  - **Emploi** — `concept_evidence.with_concept_evidence` runs after any grader (authored,
    conversation, story engine), no extra model call: the unit's regex detectors (v1 borrows
    its v2 replacements') → `correct` (free production) · `error` (a correction touches the
    form: one NOT_YET observation, and the correction's erratum is handed the same unit, so
    the lapse is booked once) · `avoided` (neutral, recorded in `concept_evidence`).
    `llm:` detectors are not run: those 7 v2 units (and the two v1 concepts with no regex
    replacement) get reply evidence from corrections only (`undetected`).
  - **Rappel** — due grammar joins the pool from `plan_review_items` (1/2/3/4 units by
    rhythm), each with its brief; one warm-up per unit, format by stability (< 3 d: choose /
    recognise; < 10 d: transform / build; ≥ 10 d: no item, the unit becomes a reply target —
    Réemploi, ≤ 2 grammar targets a reply).
  - **21-day run** (both catalogues): introduced day 0 (4 guided items + free use), Rappel
    choice on days 2, lapse in the reply day 3, repair + Rappel day 4, choices days 5–9,
    second free use day 10, transform day 17 → held on day 17.
  - **Deferred** — the x-ray highlight of the form inside the scene reader (Rencontre);
    WP-L5's `grammar_plan` (the director writing the form 2–3× and a question that needs
    it); the `concept_evidence` field in the reply grader's own schema for `llm:` units;
    the auto-throttle itself; Home/Dossier surfaces for the stages (WP-L7).

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
- **Status (2026-09-23, first half landed):** the rhythm is `users.daily_goal_minutes`
  (5 / 10 / 20 / 30; older values map ≤7 Léger, ≤14 Régulier, ≤25 Soutenu, else Intensif;
  new learners start on Régulier) and the server sizes the day from it — the client no
  longer sends a budget. `rhythm_caps()` in `journey_contracts.py` scales the practice day
  (warm-ups, guided items, retrieval after the reply, candidate pool); the five-minute row is
  the WP-78 envelope unchanged. Measured pace feeds the planner after 3 measured days
  (`journey_events.measured_pace`). «Nouveaux mots par jour» is one intake pool
  (`vocabulary_pace.py`). «Encore 5 minutes» is the word drill in reviews-only mode
  (`/vocabulary/review?encore=1`). Still open: the auto-throttle
  (`vocabulary_pace.intake_throttle_factor` is the hook, returns 1.0 until WP-L3), folding the
  Atelier drills into Soutenu/Intensif's Scène, a third reply turn and Intensif's letter or
  listening block, the WP-L8 forecast on the cards, and the rhythm question in onboarding
  (no natural step after the first win yet: the taste leads to sign-up, then straight into
  day one).

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
- **Status (2026-09-24): landed (backend + web); the épreuve episode itself is Codex's.**
  - **Coverage** — `app/services/level_coverage.py`. Units of a band: v2 by `sub_band` tag; v1 by
    CEFR level, halved by teaching order (`difficulty_order`, id). Words: the lexicon's lemmas of the
    sub-band minus closed-class words (articles, pronouns, prepositions… taught by the units):
    A1.1 316, A1.2 302, A2.1 398, A2.2 396, B1.1 543, B1.2 541; B2 has no word list, so units only.
    Known = retrievability ≥ 0.85 on a card seen ≥ 2 times and not relearning. Held =
    `held_unit_ids(db, user)` — **a temporary fallback** (stability ≥ 21 d, last review not a
    lapse) that WP-L4's Tenue rule replaces in that one function. A unit once held stays counted in
    its band (kept on the band's checkpoint row), so a lapse brings it back without uncovering the
    band. The percent («A1.1 · 60 %») = 45 % units + 45 % words (each capped at its threshold) +
    10 % épreuve: coverage without the épreuve reads 90 %.
  - **Checkpoint** — `app/services/level_checkpoint.py`, table `user_level_checkpoints`
    (migration `f2a4c6e8b0d1`). `locked → ready` when coverage is met; `ready → passed` (band
    closed, level + 1) or `failed` (`retry_after` = + 7 days, then ready again); `credited` closes a
    band without an épreuve. Readiness is never taken back. API: `GET /progress/cefr/checkpoint`
    (fresh, read-only; `checkpoint_ready`, the band's can-dos), `POST /progress/cefr/checkpoint`
    `{band, passed, episode_id?, evidence?}` (409 on wrong band / not ready / retry too early /
    closed); in-process `current_checkpoint(db, user)` and `record_checkpoint_result(...)`.
  - **Promotion** — `CEFRProgressService`: the level is one above the highest closed band.
    `CEFR_THRESHOLDS` is gone; its performance half is `PERFORMANCE_GATES`, used only after 40
    attempts to decide how much of a placement / declaration the evidence confirms (confirmed →
    the band below is credited `prior_confirmed`). Prior floor below 40 attempts and the down-step
    smoothing unchanged. Release day: a level the old walk *measured* (payload v1 `measured`, or no
    payload and above the prior) is kept as `release_floor` and credited `release_grandfather`.
    Payload `cefr-progress-v2` adds `level_label`, `coverage`, `checkpoint`, `forecast`,
    `rhythm_priors`; `breakdown.vocabulary/grammar` now count words known / units held against
    the band. The journey finish refreshes the payload and the checkpoint row every day.
  - **Web** — Home's masthead: «A1.1 · 60 %» as one label line (journey on). Dossier: the band
    headline, units held x / y, words known x / y, the épreuve's state, the rule, the forecast.
  - **Tests** — `tests/test_wp_l7_level_coverage.py`.

#### WP-L8 · An honest forecast
- Before 7 active days: the §2.3 prior for the learner's rhythm, as a range.
- After 7 active days: remaining band units and words ÷ measured intake, scaled by measured
  retention and bounded by the checkpoint, as a range.
- It is shown when choosing a rhythm («À ce rythme : A1 terminé vers mars»), in the Dossier, and
  at the Seal once a week. It is never shown as a promise before it has been measured.
- The unbacked «20 min/day for 50 days → A1.2» goes. By the prior, A1.2 at 20 min/day is about
  1.5 months of intake plus the checkpoint.
- **Done when:** the forecast matches WP-L9's simulation within ±20 %.
- **Status (2026-09-24): landed.** `app/services/level_forecast.py`.
  - **Formula** — to the end of the band in force (coverage + the épreuve):
    `words_days = words_needed / (words_per_day × retention)`; units: the band is covered when
    the *needed-th* unit in flight is first held, each unit's lag drawn from the memory model at
    the learner's accuracy (`hold_lag_samples`, 41 days on a clean run; units already introduced
    keep the lag they have spent), median of 200 seeded trials; `base = max(words, units,
    checkpoint floor) + 1 day`; shown as `[0.8·base, 1.3·base]`, capped at 730 days.
  - **Prior** (before 7 active days; journeys count as active days): §2.2's intake per rhythm,
    retention 0.9. **Measured**: words and units introduced over the last 14 days, retention =
    share of items introduced 7–60 days ago that stuck (units shrunk toward words while the sample
    is small). A failed épreuve's week is the floor.
  - **Rhythm priors (catalogue v1 → A1)**: Léger 7–12 months, Régulier 4–6, Soutenu 3–5,
    Intensif 3–5 (v2: 7–12 / 4–7 / 3–6 / 3–5). A1.1 alone at Régulier: 78–126 days (v2 91–148).
  - **Simulation** (`simulate_band_coverage` in `app/core/srs/simulation.py`): Régulier at 85 %
    on A1.1 (18 v2 units, 316 words): median coverage day ≈ 128, the day-14 measured forecast's
    median ≈ 124 (within 5 %); across rhythms and 70/85/95 % the medians agree within ~±20 % (the
    6-unit v1 half is noisier: all six must be held).
  - **Shown** — Réglages: each rhythm card «Estimation : A1 en 4 à 6 mois à ce rythme.»
    (en/de/fr). Dossier: «Estimation avant mesure …» / «Estimation sur vos quatorze derniers
    jours …». Relevé: «Estimation : 60 à 95 jours à ce rythme.» (was one number).
  - The «20 min/day for 50 days → A1.2» claim never reached product copy (grep of `app/`,
    `web-frontend/`, `mobile/`); the payload's `daily_minutes` fallback of 20 is now the rhythm's
    10. **Not yet**: the weekly forecast line at the Seal.
  - **Tests** — `tests/test_wp_l8_forecast.py`.

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
- **Status (2026-09-23, timing half landed):** `daily_journey_steps.started_at` (migration
  `e1f3a5b7c9d2`) is set when a step becomes current; the daily rollup's `active_duration`
  gains `by_rhythm` (p50 / p90 of measured active seconds, rhythm read from the journey's
  budget). The 126-day harness per rhythm is still open.

#### WP-L10 · The rule card v2: readable and beautiful
- Spec and findings: `GRAMMAR-DUE-DILIGENCE-2026-09-23.md` §3.
- Today's card is an English rule set as the Garamond headline, with French labels, a typed
  ASCII formula, and no forms, glosses, audio or contrast pair.
- v2:
  - a French example is the one headline, marked with the x-ray marks and gender shapes;
  - a rule of at most 20 words in the learner's language, with no jargon at A1–A2;
  - the pattern drawn from tokens, or a mini conjugation table;
  - one ✗/✓ contrast pair;
  - «Pourquoi ?» for more.
- Content columns per unit and locale (en / de / fr): `rule_short`, `rule_more`, `glossary`,
  `contrast_pair`, `forms`, `pattern_tokens`. Authored with WP-L2, drafted by an LLM and
  reviewed by a person.
- It can start before WP-L2 on the current 54 concepts, so the card improves now.

## 4. Order

1. **WP-L1** now; **WP-L10** can start in parallel on the current catalogue. Small and independent; everything later assumes the loop is honest.
2. **WP-L2 and WP-L3 in parallel**: the syllabus content and the memory model.
3. **WP-L6** (composer and rhythm) once WP-L3's queue exists. **WP-L9**'s timing half goes with
   it, so the 8–10 minutes is measured, not asserted.
4. **WP-L4**, then **WP-L5** with Codex. The engine needs the `grammar_plan` contract first.
5. **WP-L7 and WP-L8** last: they need the syllabus, the memory and real measurements.

The simulator walk at the end of each step covers both themes, three learner languages and all
four rhythms.

## 5. Owner decisions (2026-09-23)

1. **Rhythms approved:** Léger 5 / Régulier 10 (default) / Soutenu 20 / Intensif 30.
   **Plus a separate vocabulary pace** («Nouveaux mots par jour», up to 20+), independent of the
   rhythm, and reconciled with the séance (added to WP-L6):
   - **one intake pool**: a word is introduced once, whether by the word drill or a scene, and the
     day's quota counts both;
   - **scene words prefer words drilled but not yet held**, so the story doubles as review and
     the reply gives them strong evidence;
   - **word reviews live mostly in the word drill**; the séance's Rappel takes only the words
     that fit today's scene, so the 10-minute séance never overflows;
   - **honest cost**: the setting shows the steady-state review load (≈ 150–200 reviews / 15–20
     min a day at 20 new words), and the throttle slows intake when reviews pile up.
2. **One episode per day** on every rhythm: approved.
3. **The level check is a special, finale-like episode.** A season is **not** one grammar topic:
   it maps to a sub-band (≈ 15 units, ≈ 300 words, the band's can-dos), about 2.5–3 months at
   Régulier, close to a season's length (≤ ~88 days). Because Soutenu/Intensif learners finish a
   band before the season does, the checkpoint is **decoupled from the calendar**: the engine
   stages a finale-style «épreuve» episode as soon as the band's coverage is met. At Régulier it
   usually coincides with the season finale; otherwise it is its own event (WP-L7).
4. **Syllabus authoring:** LLM drafts plus human review; open frequency list OK (check licence).
5. **Honest forecast:** approved, even when it is slow.
