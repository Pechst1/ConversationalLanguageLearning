# WP-58 — Story shape: a serial with ups and downs, and no dead day

**Owner ask (2026-09-19):** the story loops on one problem and aborts when the
model stumbles. The goal was always a storyline the learner engages with —
characters with depth, feelings, rises and falls — so fix the loop, fix the
abort, and commit.

**Evidence before:** `var/reviews/atelier-longitudinal-A2-turns.json` (14
days, 2026-09-07): one leaking radiator and the same plumber's deposit for
fourteen days, boxes wet from day 1 to 14, three chapters that were the same
chapter renamed. `atelier-story-review-A2-2026-09-19{,b}.json`: run 1 died on
day 2 (`inclusive_dot_form` on a private field), run 2 on day 3 (two critic
rejections of clean turns). Both were a learner's failed Séance.

## What changed (`app/services/living_story.py`)

### 1. A chapter is a shape, not a counter

- `CHAPTER_MAX_SCENES` 5 → 4 and `CHAPTER_BEATS = (setup, complication, turn,
  resolution)`. `required_beats(chapter)` says which beat the next scene may
  carry: scene 1 setup, scene 2 complication, scene 3 turn or resolution,
  scene 4 resolution. `chapter_state` exposes `required_beat`.
- `SceneDraft` gains `beat`, `problem_key` (the chapter's concrete practical
  trouble, a slug) and `arc_id`; all optional in the schema so authored
  fixtures stay valid. The validator fills a missing `beat` with the required
  one and rejects a wrong one (`wrong_beat`, with the beat to write).
- **The resolution beat closes the chapter whatever the learner answered**
  (`chapter_after_scene`): the question was answered by events; a refusal is
  an answer. The actor's `chapter_resolved` on a met objective still closes
  early, as before.
- **A new chapter needs a new problem**: `variety.used_problems` carries the
  last six `problem_key`s; a setup scene whose key matches one is refused
  (`stale_problem`) and told to start from another arc stage or open thread.

### 2. The season's depth reaches the director

- The world bible's `season_arcs` (the ring, the Berlin envelope, Gus's
  aristocracy, Romy, settling in), `season_one_situation.open_threads` and the
  `warmth_rule` are projected into `world` (`_season_projection`), with each
  arc's `current_stage` / `next_stage` from `live.arc_progress`. When a chapter
  anchored in an arc resolves, that arc advances one stage
  (`arc_progress_after_scene`, idempotent per event).
- The cast projection now carries `contradiction`, `secret`, `flaw` and
  `dynamic_with_user` (`CAST_KEYS`). The prompt says secrets surface only
  through their arc's stages.
- `DIRECTOR` has a STORY SHAPE block: required beat, chapter problem, arc
  anchoring, hope/setback alternation, one genuine beat of feeling per scene,
  bittersweet resolutions allowed. `ACTOR` is asked for emotional truth in the
  reply — how the learner's words land on the character.

### 3. No dead day

- **Turns.** When both attempts are refused (guards or critic), `evaluate_turn`
  no longer answers `pending` — the failed send the owner saw. It settles an
  honest authored ending (`_fallback_evaluation`): the character is called
  away, the learner's words are the only evidence, outcome `partially_met`,
  no commitment, no chapter closure, `reply_source: authored` (the reader
  shows «Réponse écrite, tirée du scénario»). Reasons that describe the
  learner or stored state (`NO_FALLBACK_REASONS`: empty answer, provider
  disabled, revision conflicts) keep the old pending behaviour.
- **Scenes.** A refused scene still raises: the journey retries or serves the
  prefetched scene; an invented scene is never served (`test_generation_failure_never_serves_authored_scene`).
- Earlier the same day (WP-57): `inclusive_dot_form` judges only what the
  learner reads; `understood_intent` is scrubbed.

### 4. Same bookkeeping everywhere

`open_chapter`, `chapter_after_scene`, `arc_progress_after_scene` are used by
`bind_journey` / `settle_resolution` **and** by `scripts/review_living_story.py`,
so a live review exercises the production shape (it used to reset the chapter
counter every day, which is why it never saw the loop).

## Tests

`tests/test_living_story.py`: required beats; wrong beat refused with the beat
to write, missing beat filled; stale problem refused; resolution beat closes
the chapter and advances its arc once; the director reads arcs, secrets and
threads. The two turn tests that pinned «a refused turn stays pending» now pin
the authored fallback (one honest event, learner quote as evidence, no
commitment, idempotent replay). Fixtures pick a chapter question this life has
not answered (`_fresh_question`), because four-scene chapters open more
chapters in fourteen days than the old modulo did.

## Still open

- The English «why» templates of the practice Séance's recognize round (WP-56).
- The reader shows the chapter title; showing the beat («Chapitre 2 · 3/4») is
  one label away if the owner wants the shape visible.
- Panel art is still one static location image per scene (Codex's image path).

## Follow-up the same night: repair before refusing

The first live runs on the new shape (`atelier-story-review-A2-2026-09-19e/f.json`)
showed the chapter arc working — «La bague de Marin» ran setup → complication
→ turn → resolution over four days, then «La tension Romy» opened on a new
problem in a new place and day 6 remembered day 5's promise — but three of
six turns ended in the authored fallback, two of them because Marin says
«mon grand» (his bible voice) to a learner whose address is neutral, and the
next run lost day 1 to «trempé·e» plus a provider timeout on the retry. Both
are things a deterministic pass can repair, so the validators now repair them
instead of refusing: a forbidden vocative endearment is cut from the sentence
(`_scrub_endearments`, vocatives only — «mon grand frère» is untouched, the
French space before «?» is kept), and an inclusive middle-dot form keeps its
first half (`_scrub_inclusive_dot`) in every learner-facing field of a scene
or a turn. `gendered_agreement` («tu es content») still rejects — there is no
safe mechanical rewrite for it. The address tests are re-pinned to the
repaired text. Provider read timeouts (3 of 21 calls at 35 s this evening)
remain the largest source of lost attempts; the per-call window cannot grow
without breaking the 75 s two-attempt budget.
