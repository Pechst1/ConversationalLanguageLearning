# WP-59 — Loop engineering, per-learner dice, and a level-true B1/B2/C1

**Owner ask (2026-09-19, night):** make the arc less deterministic through
loop engineering, and fix what the B1/B2 reviews showed; add C1.

**Evidence before:** every fresh learner at A2, B1 and B2 opened on «La
tension Romy» and reached Montréal by day 3 (`atelier-story-review-{A2-g,B1,B2}-2026-09-19.json`);
every B1/B2 objective read «tell Romy in one sentence…»; a B2 reply wrote
«prêt(e)» and «content(e)»; the B2 resolution asked the turn's question again;
C1 learners were served as B2.

## What changed (`app/services/living_story.py`)

### 1. The loop: two drafts, one kept

On the beats where surprise matters (`DUAL_DRAFT_BEATS` = setup and turn),
`_approved` draws `DUAL_DRAFT_CANDIDATES` (2) scene drafts **concurrently**
inside the same deadline, runs every deterministic guard on each, and keeps
the one `_scene_score` prefers: premise novelty (×2) and objective novelty
against the recent situations, a bonus for a character or a location this
life has not used lately, a bonus for an arc anchor and one more for the
suggested arc. Both drafts' spend is recorded. If neither passes, their
feedback seeds the second attempt, which is a single draft as before. Wall
time stays that of one draft; cost is one extra draft on two of four beats
(≈ +0.3 ¢ per day). The review script uses the same call.

### 2. The dice are rolled in code

`_season_projection(world, arc_progress, seed=, chapter_index=)` orders the
season arcs by a hash of the learner's thread id, so `world.suggested_arc`
differs per learner and stays fixed for them, and deals this chapter's
`world.complication_card` from an authored deck of fourteen
(`COMPLICATION_CARDS`) by hash of seed and chapter index. The director is
told to open chapters on the suggested arc and to play the card on the
complication beat. `chapters_opened(live)` is the card index in production;
`--seed` sets it in the review script.

### 3. Level-true objectives, prose and replies

- From B1 the objective is a move, never a sentence: `objective_too_thin`
  rejects «in one sentence» framing (en/fr/de) and objectives under 10/12/14
  words at B1/B2/C1, with a hint that says what a move is. A1/A2 keep the
  one-act rule.
- `_REPLY_WORD_LIMITS` and `_SCENE_WORD_LIMITS` now scale to B1, B2 and C1;
  the DIRECTOR and ACTOR prompts carry a prose bar per band (connectors,
  subordination, idiom, implicit meaning from B2; register play at C1).
- `resolution_repeats_turn` rejects a resolution whose objective overlaps the
  same chapter's previous objective at 0.45.
- `_scrub_paren_gender` cuts «prêt(e)», «content(e)s» in every learner-facing
  field, like the endearment and middle-dot scrubs.

### 4. C1

`learner_level_band` returns C1 for a C1 estimate and reads C2 as C1; the
review script accepts `--level C1`. The grammar catalogue already holds six
active C1 rules; the placement ladder still stops at B2.1 by design.

## Tests

`tests/test_living_story.py`: objective contracts per band; C1 band and
limits; the parenthesised-gender scrub; the resolution-repeats guard; the
dice (reproducible per seed, different across seeds, completed arcs never
suggested, a card per chapter); the two-draft loop keeping the novel draft
and recording both drafts' spend. Fixture objectives grow a reason and an
alternative from B1 so the fake director passes the new contract.

## Still open

- The score is lexical; an emotional-delta term (mood/trust state per
  character) is the next lever for scenes that *land* differently.
- Branching on which `possible_development` came true is not wired yet.
- C1 has no live review on record; B1 and B2 do.

## Evidence (`atelier-story-review-B1-2026-09-19b.json`, seed `learner-b1-two`)

Four of four days accepted, 14 requests (two drafts on the setup and turn
beats), ≈US$0.05. The dice worked: this life opened on «Le portrait de
Berlin» — Lila's envelope — where every earlier run opened on Romy; the
suggested arc was `lila_berlin_secret`. The objectives are moves («tell her
whether you will keep the secret and give a short reason, or tell her she
should tell Marin and why»; «propose a concrete way … and explain why your
plan protects Lila and respects Marin»). The chapter ran setup (the envelope
under the canvas) → complication (Marin overhears; the scripted refusal) →
turn (Lila asks the learner to read it for her) → resolution (at the park
with Romy, the group waiting; the learner advises Lila to read it herself).
B1 prose: «On dirait que le tableau a volé ta voix, Lila.» No fallback, no
parenthesised gender, no repeated question.
