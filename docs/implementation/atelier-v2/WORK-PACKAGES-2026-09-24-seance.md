# Work packages — 2026-09-24 (séance): a grammar engine, not «more practice»

Owner brief (2026-09-24): the séance must not be an optional «more practice» bolted onto the day. It is
the **grammar learning engine**: it actively trains, tracks and consolidates grammar concepts, so learners
master grammar **much faster** than in Duolingo. It should be part of one cohesive learning experience.
Audit it for effectiveness, beauty, fun and creativity first, then propose changes and the integration.

Numbering: **WP-S1 … WP-S8** (S for séance). These packages build on the learning packages
(`WORK-PACKAGES-2026-09-23-learning.md`: L2 syllabus, L3 memory model, L4 concept life, L6 rhythm,
L7 level coverage, L10 rule card).

## 1. Audit (2026-09-24)

Method: I played a full séance as a new A1 learner («Genre et nombre», 22 items) and timed every item. A
code map covered `app/services/atelier.py`, `api/v1/endpoints/atelier.py`, `exercise_generation.py`,
`pages/atelier.tsx` SessionView and `components/epreuve/Epreuve.tsx`. I also queried the local database,
which holds mostly test data, so treat its numbers as indicative only.

### How it works today

- **Session:** up to 3 concepts. The rungs run in a fixed order across all concepts:
  1. recognise (fill-in, then sort, then word bank);
  2. transform;
  3. sentence;
  4. one paragraph for the whole session («produce»);
  5. speak;
  6. conversation.
- **Size:** an LLM set has 15 items per concept; the curated fallback has 7.
- **Adaptive lock:** clean answers skip the rest of a rung.
- **Credit:** once, at the end, as a single piece of evidence per concept.

### Effectiveness — the core problem

| Finding | Evidence |
| --- | --- |
| **One sentence recycled 4–5 times** | The rule card, fill-in, sort, word bank and transform all use «Une petite table blanche…». From the second exercise on, recognition is copying, not retrieval. |
| **Three new rules at once** | A new learner's first séance served gender + definite articles + indefinite articles. The session is padded to 3 concepts from teaching order (`endpoints/atelier.py:1248-1274`). This breaks the rhythm's intake quota and still counts against it (`concept_life.py:107-112`). |
| **Twenty items, three memory updates** | Evidence is written once per concept per session, graded by the strongest format answered correctly. Most of the effort doesn't reach the memory model. |
| **Slow feedback** | Transform, sentence, speak, conversation and produce are graded by a synchronous LLM call. **Transform took 18 s** in my run. The median completed session is 36.8 min (test data). |
| **The fast path serves the same fallback** | The shared cache reads `source=="llm"`, but generation writes `llm_user`, which is never shared (0 shared sets in v11). So the curated 7-item set is served first, identical every time. |
| **No knowledge of the day** | The séance doesn't know which rule the journey introduced today. There are three pickers (`select_today`, `exercise_generation.select_daily_concepts`, the journey's `_practice_href`) and two item builders (the journey's deterministic `grammar_items.py` vs the séance's LLM or curated sets). |
| **Recognition-heavy, weak production** | By mean score, sentence (1.65) and word bank (1.66) are the weakest rungs. Production comes last, after 9+ recognition items, and the session is often abandoned before it (26 % completion). |
| **The chosen rule can be ignored** | An in-progress session is returned whatever `preferred_concept_id` asks for (`endpoints/atelier.py:1209`). |
| **v2 syllabus has no séance content** | `seance_challenges.txt` covers v1 ids only. |

What works and stays:
- the adaptive lock;
- the repair line (recopy the correction) and the retest queue;
- confidence-weighted scoring («sure / not sure»);
- the three quality gates for generated sets;
- the rule card v2 at the start of each concept;
- same-day dedupe with the journey.

### Beauty

- **Layout bugs:**
  - The footer (Check) is narrower than the content, and its divider is cut off.
  - The top bar scrolls away.
  - Scrolling to the correction opens a large empty gap above it.
  - Word-bank tiles have outlines, which breaks the "no strokes" rule.
- **Machine counters:** «Recognize · Fill in · 1/1», «0/22», and a concept title that changes silently mid-session.
- **Mixed language in exercises:** the transform instruction is French with the English catalogue title
  inside («Corrigez « petit » selon la règle « Gender and number basics »»). Situation cues are French
  for an A1 English learner.

### Fun and creativity

- **Situations are generic:** «Vous décrivez une table», «Votre ami demande…». The cast and the story
  only appear in the conversation rung, and even there from the legacy serial.
- **No sense of mastery:** nothing shows a rule becoming yours. The «motif» that assembles as you go has
  no meaning a learner can read.
- **No sound**, and the correct-answer streak is almost invisible. Unchecked answers extend it anyway.
- There's no challenge format (speed, discrimination, boss), and no reason to come back to the séance
  except «more practice».

### Why this is slow, and what "fast" means

Duolingo is slow at grammar for three reasons, and today's séance shares all three:
1. Grammar is implicit; the learner infers it from many exposures.
2. Recognition dominates.
3. Mastery is never measured per rule, so known rules keep being practised and weak ones aren't targeted.

Research gives a faster recipe:
- explicit rules followed immediately by varied retrieval;
- interleaving and contrast between confusable forms;
- desirable difficulty: produce, don't just recognise;
- instant, specific feedback;
- spacing driven by a memory model;
- a test-out for what you already know.

The target: **a rule held in about 2 weeks and about 40–60 quality items**, measured per rule (WP-S8),
instead of the dozens of lessons Duolingo spends on one pattern.

## 2. The model: the séance as the grammar engine («La Forge»)

One engine, three entry moments, one progress:
- **The day** introduces a rule (WP-L4 Règle step, then 3–4 guided items).
- **The séance** forges it: a short, intense, interleaved block that takes today's rule from introduced
  to proficient and keeps due rules held.
- **The level** shows it. WP-L7 coverage counts held rules, and the Home / Dossier map shows each rule's
  shape filling.

A séance (5–8 min at Régulier, sized by the rhythm) is composed, not a fixed ladder:

| Share | What | Source |
| --- | --- | --- |
| ≈ 40 % | **Today's rule, deepened**: the rule the day introduced (or the weakest in-progress rule), climbing its ladder | concept_life stage |
| ≈ 40 % | **Due rules, interleaved**: FSRS-due concepts mixed, never two items of one rule back to back | `plan_review_items` (WP-L3) |
| ≈ 20 % | **Contrast**: minimal pairs between confusable rules (le/la, un/des, passé composé/imparfait, qui/que) | `contrast_partners` (WP-L2) |

**Per-rule ladder (a staircase, not a fixed order).** The rungs are:
1. recognise;
2. discriminate (a minimal pair);
3. build (word bank with spare chips);
4. transform;
5. produce (short, guided);
6. free use (a sentence in a mini-situation).

A correct answer moves the rule up one rung. An error moves it down one rung and schedules a **reprise**:
the same rule comes back 3–5 items later in a different sentence, rather than only a recopy.

**Every item counts, with caps.** Item-level evidence goes through `apply_grammar_evidence` with the
L3 format weights. Within one session, only the first success per rule per rung moves the schedule;
the rest count towards the next rung and towards held status. That makes practice count without
inflating the memory model.

**Test-out («Épreuve de la règle»).** Five mixed items, including production. If passed, the rule is
held at once, like a placement for grammar. Learners never grind what they already know. This is
the biggest time saver against Duolingo.

**No waiting.**
- Everything except free production is graded locally in under 300 ms: answer keys, the v2 detectors, and
  normalised comparison.
- Free production gets an instant local check (detector plus answer key), with the LLM verdict arriving
  asynchronously. It never blocks «Continue».

**Content: an item bank, not a set per session.**
- Every v2 unit gets **generative templates**: slot grammars filled from the lexicon, the learner's known
  words, and the story's cast and places. That gives thousands of distinct, verifiable sentences per rule,
  generated instantly and never the same sentence twice in 7 days.
- The LLM pre-generates a vetted pool offline or in batches (the three gates still apply) for the
  production and situation items only.

**Story and characters.**
- Sentences use the learner's world: Margaux's café, Romy's articles, Gus's workshop.
- Each rule has a **coach**, a cast member who says the rule card's example and reacts to your answers
  (the existing mood portraits).
- The free-use rung is a two-line mini-scene with that character.

**Design and fun, inside the design language.** No mascots, no confetti rain.
- The **combo** is the shape tokens lighting up in a row, with haptics and a soft sound.
- **Éclair** is a 60-second minimal-pair sprint.
- The **grammar map** shows the syllabus as the four shapes. Each rule is a shape that fills from ghost
  to ink as it goes introduced → proficient → held.
- The **Seal** gets an extra ring when a rule becomes held that day.

## 3. Packages

#### WP-S1 · Instant feedback: grade locally, never block on the LLM
- Transform and guided production are graded locally: answer keys, the WP-L2 regex detectors, normalised
  diffs, and the repair diff that already exists.
- The LLM verdict for free production runs asynchronously and amends the evidence when it lands. The
  learner is never held. On disagreement, a quiet «second check: …» note appears.
- The «Second check running…» notice on word-bank items goes: word order is checked by the answer key.
- **Done when:**
  - p95 time from Check to verdict is under 300 ms for every rung except free production;
  - free production shows its local verdict in under 500 ms;
  - no séance request waits on an LLM;
  - latency is logged per rung.
- **Status (2026-09-24): done.** Recognise and transform are graded by the key (`app/services/forge_grading.py`:
  typography folding, token diff naming the ending / missing word / order); measured p95 ≈ 5 ms per submit in the
  test client. Free production returns a provisional local check (unit detector + model-answer similarity) and the
  relecture lands in the background (`second_check`, evidence deferred and written once via `evidence_applied`).
  The word bank's second check is gone; the combo counts checked verdicts only. Each submit writes a
  `forge_verdict` pilot event (rung, `local_ms`, then `async_llm_ms`, `verdict_changed`).

#### WP-S2 · The item bank: variety without waiting
- Generative templates per v2 unit, in the catalogue or `app/data/grammar_templates/`. Each is a slot
  grammar (determiner / noun with gender and number / adjective agreement / verb conjugation tables)
  filled from the lexicon, the learner's known words and the world bible's cast and places, with the
  answer key produced alongside.
- Covers every A1–A2 unit first.
- **Variety guarantee:** no sentence repeats within a session, and none within 7 days for the same
  learner. The rule card's example never appears as an exercise.
- **Pre-generated LLM pools** for situations and production prompts: batched, gated, shared across
  learners by unit and band, refreshed on report rates. Fix the `llm` vs `llm_user` cache split
  (0 shared sets today).
- The curated fallback remains only as a last resort.
- **Done when:**
  - every A1–A2 unit yields ≥ 200 distinct valid items per rung type;
  - a 10-session simulation shows no sentence reused within 7 days;
  - generation adds 0 ms to séance start.

#### WP-S3 · The forge: adaptive ladder, item-level evidence, reprise, interleaving
- **The per-rule staircase** as in §2: rungs, move up and down, reprise 3–5 items later with a new
  sentence.
- **Composition:** 40 % today's rule / 40 % due rules / 20 % contrast. No two items of one rule back to
  back. Contrast pairs come from `contrast_partners`.
- **Evidence per item** through `apply_grammar_evidence`, with first-success-per-rung caps and the
  existing confidence weighting. Unchecked answers never count, and never extend the combo.
- **Test-out** «Épreuve de la règle»: 5 mixed items. If passed, the rule is held; this uses the WP-L4
  held fields with a new `tested_out_at`.
- **Done when:**
  - a simulation shows median items-to-held per rule at 85 % accuracy under 60, versus today's ladder
    measured with the same simulation;
  - no learner sees 3 brand-new rules in one séance;
  - the evidence written matches the items answered.
- **Status (2026-09-24): landed** (`ATELIER_FORGE_ENABLED`, default on; `tests/test_wp_s3_forge.py`).
  - **Engine** — `app/core/forge.py` (pure): the staircase, the reprise (3–5 items later, a new item),
    the 40/40/20 mix with no rule back to back (a one-rule séance is the only exception; when only the
    last rule could go on, the séance ends), at most one brand-new rule, a rule clean at free use
    retires for the day (the adaptive lock, folded in), length = rhythm budget (Léger 240 s, Régulier
    360 s, Soutenu 480 s, Intensif 600 s) ÷ measured seconds per item, 6–24 items.
  - **Evidence** — rung → WP-L3 format: recognise / discriminate → recognise, build → guided,
    transform → transform, produce → production *assisted*, free use → production (the only rung
    that counts as free use for «Tenue»). Every checked answer is one entry: the first success per
    rule per rung and the first failure per rule move the schedule (`apply_grammar_evidence`, new
    `weight_scale`: the k-th success of a rule in one séance is massed practice, weight × 0.5^k); the
    rest fold into the concept's life (`note_concept_evidence`). Unchecked answers count for
    nothing. The journey's D-0 credit still wins (a rule it moved today folds). `complete_session`
    no longer writes the single evidence for a forge séance.
  - **Test-out** — `POST /atelier/forge/test-out {concept_id}` (any rule, from day one): recognise,
    discriminate, build, transform, free use. ≥ 4/5 with the production right → `held_at` +
    `tested_out_at` (migration `c3e5a7b9d1f4`, also `forge_rung`); else the rule is placed on its
    lowest failed rung (a production-only failure: produce). `GET /atelier/forge/state` gives per rule
    rung, stage, next due.
  - **Interfaces** — `app/services/forge.py`: `ItemProvider.item_for(concept_id, rung, exclude)`
    (default: today's exercise set; WP-S2 replaces it), `Composer.pick(user, now)` →
    `[(concept_id, today|due|contrast)]` (default: `select_today` + the journey's rule of the day +
    WP-L2 contrast partners; WP-S4 replaces it), `verdict_from_attempt` (an explicit
    `correction["checked"]` wins; `ForgeService.amend_attempt` books a verdict that lands later — WP-S1).
  - **Simulation** (`simulate_items_to_held`, one séance a day, rules introduced at Régulier's
    2/week, 150 days, rules judged if introduced ≥ 45 days before the end):

    | 85 % accuracy | median items to held | held | median days to held |
    | --- | --- | --- | --- |
    | **Forge**, séance only | **23** | 30 / 30 | 19 |
    | Forge + journey Rappel | 29 | 28 / 30 | 19 |
    | Today's ladder, séance only | **never** (∞) | 1 / 44 | — |
    | Today's ladder + Rappel | 19 | 168 / 212 | 55 |

    Today's ladder writes one evidence per concept at its strongest format (production), so the
    séance alone never gives «Tenue» its spaced item: its rules are held by the Rappel, after
    13–15 séance items on the first day, in 55 days. At 70 % the forge needs 54 items (59 with
    the Rappel). The forge never seats more than one brand-new rule (the ladder: 2 at the
    default budget), and writes exactly one evidence per answered item.
  - **Web** — the séance runs `forge.next` (the existing Épreuve panels, feedback and repair); the rule
    header shows «Step n of 6 · rung», the reprise note and «Test out this rule»; the Cahier rule
    page has «Test out this rule»; the test-out ends on one Garamond line and «Back to the rule».
    Chrome in `lib/forge-copy.ts` (en/de/fr, by `useChromeLanguage`).
  - **Open** — the curated/LLM set has 3 items per recognise mode and one per production rung, so a
    long séance can run a rule dry (it then retires); WP-S2's bank removes that limit.

#### WP-S4 · One engine, one picker, one day
- **One picker:** retire `exercise_generation.select_daily_concepts` and the padding to 3. The séance's
  rules come from concept_life (today's introduced rule) plus `plan_review_items` plus contrast. New rules
  are introduced only through the rhythm quota.
- **The journey hands over to the séance:** «Forge today's rule» follows the Règle step. On Soutenu and
  Intensif the séance is folded into the day's Scène movement; this closes WP-L6's deferred item. On
  Léger and Régulier it is the Home chip after the day, «Forge · 5 min».
- **Respect the chosen rule:** fix `preferred_concept_id` being ignored by an in-progress session.
- **Length from the rhythm;** the séance's minutes count towards the day's measured time (WP-L9).
- **Progress is visible:** the WP-L7 coverage percent and the grammar map update after a séance. The
  day mark's yellow square (Rappel) includes the séance when it is folded in.
- **Done when:**
  - one picker module is used everywhere;
  - an end-to-end test goes from introduction in the journey, through the séance, to held;
  - the intake quota holds across both surfaces.
- **Status (2026-09-24, landed; branch `feat/forge-wp-s4-one-picker`):**
  - **One picker:** `app/services/forge_picker.forge_plan(db, user, now, *, preferred_concept_id=None,
    budget_seconds=None) -> ForgePlan(units=(ForgeUnit(concept_id, role, reason), …),
    budget_seconds, reason, rhythm, new_concept_id)`; `plan.pairs()` is the
    `[(concept_id, "today" | "due" | "contrast")]` list WP-S3's `Composer` takes. Today's rule, in
    order: the learner's choice → the rule introduced today → a rule a due erratum points at → the
    rhythm quota's new rule (`introduction_due` + `next_new_concepts`, the journey's own intake) →
    the weakest in progress → the most due → a held rule kept warm. Due rules come from
    `plan_review_items`; contrast partners must already be introduced. No padding.
    `AtelierScheduler.select_today`, the séance start, the generation context and the journey
    (`practice_href`, the fold, the envelope) all read it; `select_daily_concepts` and the
    pad-to-three are gone. A started séance stores `plan.as_payload()` (+ `origin`,
    `journey_step_id`) in `quote_payload["forge"]`.
  - **The chosen rule:** a start for a rule the open séance does not lead with parks it
    (`status="parked"`, resumed by a bare start within 24 h) and seats the rule; the page no longer
    reopens the old séance.
  - **The fold (Soutenu, Intensif):** the smallest robust design is a hand-off step,
    `StepKind.FORGE`, in the Scène movement after the guided items and before the reply. The day
    keeps 240 s free of quick items and the step takes what the day leaves (120 s … the rhythm's
    forge length, 420 / 600 s). The step opens `/atelier?mode=forge&concept=…&budget=…&step=…`;
    the forge block's recap returns to the day, where the step reads «Back to the scene»
    (`forged`, projected from the séance ledger) and advances. Its time is the step's segment
    (ceiling twice its plan). The day mark counts it in the yellow square.
  - **After the day (Léger, Régulier):** the envelope's `forge {href, concept_id, budget_seconds,
    folded}` drives Home's after-day chip and the recap's quiet button: «Forge today's rule» /
    «Forger la règle du jour» / «Regel des Tages schmieden». Folded days keep «More practice».
    After-day forge minutes count towards the day in the rollup (`p50/p90_day_seconds`).
  - **Progress:** completing a forge block recomputes the CEFR payload (coverage «A1.1 · x %»).
  - Tests: `tests/test_wp_s4_one_picker.py`, `web-frontend/components/atelier-v2/journey/forge-step.test.js`.

#### Integration of WP-S1…S4 (2026-09-24)
- **One `quote_payload["forge"]`:** S4's plan (`units`, `budget_seconds`, `reason`, `rhythm`, `origin`,
  `journey_step_id`) and S3's engine state (`tracks`, `history`, `pending`, …) side by side. The Composer is
  `ForgePlanComposer`: it reads the stored plan back, or calls `forge_plan` once. `SelectTodayComposer` is gone.
  The séance's length comes from the plan's budget.
- **Bank top-up:** `BankItemProvider` is the forge's default. When a rung has no unused item, it generates one
  from the item bank. The new sentence is never one served in the last 7 days, never one already in the
  séance, and never the rule card's example, and it is recorded as served. The item is appended to this
  session's exercise set (`payload.forge.appended`; a shared set is copied first) and graded by its key
  through the ordinary submit path. The forge's `next.item` carries it to the page (`lib/forge-items.ts`).
- **Grading:** `verdict_from_attempt` reads S1's `assessment_status`. A provisional production is unchecked,
  but a detector hit still moves the staircase. It becomes evidence when the relecture lands
  (`ForgeService.amend_attempt`, exactly once; `evidence_applied.mode = "forge"`). In a test-out, free
  production is graded locally and final, so a test-out passes without a model.
- **The fold:** a start carrying `journey_step_id` resumes the open séance of that rule and stamps the step on
  it. The recap names the step.
- Tests: `tests/test_forge_integration.py` (Soutenu day → forge step → séance topped up from the bank →
  complete → back to the day, level recomputed).

#### WP-S5 · Story-linked content and character coaches
- Template slots draw from the world bible (cast, places, recurring objects) and the learner's story
  so far (the chronicle, WP-62).
- Each rule gets a coach, one cast member assigned per unit family, who voices the example and reacts
  to answers with mood portraits.
- The free-use rung is a mini-scene: two lines with the coach, needing the rule. It is graded locally,
  with an asynchronous LLM verdict.
- The conversation rung moves from the legacy serial to the journey's story engine (Codex).
- **Done when:** ≥ 80 % of séance items name a cast member, place or story object, and a learner can say
  which character teaches which rule.
- **Status (2026-09-24): landed** (with the owner-delegated template naturalness review,
  `FORGE-TEMPLATE-REVIEW-2026-09-24.md`).
  - **Story-linked slots** — the bank weights cast, bible places and recurring objects 4×, and the
    learner's recent chronicle 2× more (`app/services/forge_story.py`, read only). Verbs gain story
    complements; pronoun frames get a vocative twin said to a cast member. **85.6 %** of a seeded
    sample (40 per A1–A2 unit) is story-linked, every unit ≥ 50 %.
  - **Coaches** (`app/data/forge_coaches.json`, `app/services/forge_coaches.py`):
    - Margaux — the counter (articles, amounts, ordering, negation);
    - Gus — the past, comparing, modals, advice;
    - Romy — questions, time, places, reasons, reporting;
    - Lila — être/avoir, describing, demonstratives, possessives, instructions;
    - Marin — everyday verbs, going and coming, pronouns, the future, relatives;
    - M. Marchand — il y a, polite requests.

    Every A1–A2 unit has one coach; a v1 concept's rule-card speaker stays its coach. The coach is
    on the atelier concept, the forge's `next` and `rules`, and on each observed answer
    (`correction.forge.coach` / `coach_mood`: happy, cross, moved when the rule became held).
  - **Free use as a two-line scene** — `item_bank.scene_item`:
    - the coach's line (the item's own question, a frame's `ask`, or a coach opener);
    - the learner's reply, which needs the rule;
    - in the page's `conversation_turn` shape, plus `scene.lines`.

    It is graded like any production (S1: local check, then the relecture). A coached scene keeps its
    coach over the legacy serial character.
  - **Web (minimal, S6 styles it)** — `lib/forge-coach.ts`:
    - the rule card shows the coach when it has no speaker;
    - `EpVerdict` shows the coach's portrait with its mood in the badge's place;
    - the scene's byline shows the coach's portrait.
  - The conversation rung's move to the journey's story engine stays with Codex.
  - Tests: `tests/test_forge_coaches.py`, `tests/test_forge_naturalness.py`, `web-frontend/lib/forge-coach.test.js`.

#### WP-S6 · Beauty and clarity
- **Layout:**
  - the top bar is sticky;
  - the footer width matches the content, with the divider intact;
  - no empty gap before the correction;
  - word-bank tiles without outlines, using the av2 tile;
  - one Garamond line per screen.
- **Human counters:** «Rule 1 of 2 · step 3 of 6» becomes a staircase of the rule's shape. Rule changes
  mid-session get a small transition card with the coach's portrait.
- **Language rule on exercise instructions and cues:** instructions in the learner's language up to A2,
  and no English catalogue titles inside French. Cues become short native-language situations; French
  content stays French.
- **The séance recap:** each rule's shape and the rung it reached, what changed (introduced →
  proficient → held), 2 proof lines, and the next due date. It replaces the tally.
- **Done when:** screenshots at 320 px and 390 px in both themes pass the design rules, and the Épreuve
  language test is extended to instructions and cues.

#### WP-S7 · Momentum and fun, inside the design language
- **Combo:** shape tokens light up in sequence, with a haptic and a soft sound (`lib/sound.ts`,
  respecting settings). It is reset only by checked errors.
- **Éclair:** a 60-second minimal-pair sprint, unlocked once two contrasting rules are introduced.
  The best score is kept per pair.
- **Grammar map (Cahier → Règles):** the syllabus drawn with the four shapes, each rule from ghost to
  ink. Tapping a rule opens its card, its coach and «Forge» or «Test out».
- **Rewards tied to mastery, not volume:** the Seal ring for a rule held today, and a rare token for a
  test-out. Confetti stays reserved as it is today.
- **Done when:** these are behind a flag with pilot events (combo length, Éclair plays, map opens), and
  the owner's design review has passed.

#### WP-S8 · Measure and prove the speed
- **Metrics per rule:** items-to-proficient, items-to-held, days-to-held, and lapse rate after held.
- **Per séance:** minutes, completion, abandons (a new pilot event), and latency p95.
- A **pilot dashboard** section and a **simulation baseline**: today's ladder versus the forge on the
  same simulated learners (WP-L3 simulation).
- The claim is made only with data: «a rule held in N days / M items», shown in the Dossier (WP-L8
  style: measured, never promised).
- **Done when:** the dashboard shows the metrics for pilot learners, and the simulation report is in
  this document's Status.

## 4. Order

1. **WP-S1** (feedback without waiting) and **WP-S2** (the item bank) in parallel. Every other package
   needs instant, varied items.
2. **WP-S3** (the forge) on top of both, then **WP-S4** (one engine, the day handover).
3. **WP-S6** (beauty) alongside WP-S3/S4 on the frontend.
4. **WP-S5** (story and coaches; the conversation rung with Codex), then **WP-S7** (momentum).
5. **WP-S8** measurement starts with WP-S1: log latency and item counts from day one.

## 5. Owner decisions

1. **Name: «La Forge» (owner, 2026-09-24).** In the app: «Forge today's rule» / «Forger la règle du jour».
2. **Test-out from day one (owner, 2026-09-24):** every rule can be tested out at once, placement or not.
3. **Folded into the day on Soutenu/Intensif; an after-day chip on Léger/Régulier (owner, 2026-09-24).**
4. **Combo sound on by default (owner, 2026-09-24),** respecting the settings toggle.

## 6. Pool pilot (2026-09-24, owner delegated the call)

- **Run:** `scripts/pregenerate_atelier_pools.py`, the 12 v1 A1 concepts, band A1, one set each.
- **Result: 0 of 12 sets passed** (≈ 12 min, ≈ 70 `gpt-5-mini` calls, cents). The generator kept producing:
  - misspelled word-bank chips («grandss», «avonss»);
  - elision errors («la étagère», «Le ami»);
  - ungrammatical answers («L'école a fermé la»);
  - production prompts without a question.

  The AI critic caught every one; it was sometimes self-contradictory («cet ami»), but it was never wrong
  to reject these.
- **Decision:**
  - No full pool fill.
  - The deterministic item bank (WP-S2) serves every rung, including guided production prompts. Its
    sentences are correct by construction and carry their answer keys.
  - LLMs stay where they are strong: judging free production (WP-S1's asynchronous verdict).
  - Revisit pools only with a stronger generator model and a deterministic post-check (elision, token
    spelling against the answer, lexicon).

