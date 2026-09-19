# WP-61 — Moods and trust per character; the next beat follows what came true

**Owner ask (2026-09-19, night):** implement the mood/trust score and the
branching, then commit.

## What changed (`app/services/living_story.py`)

### Feelings as state

- `SemanticTurn` gains `feeling_shift` (`warmer` | `colder` | `steady`) and
  `development_index` (1-based entry of the chapter's `possible_developments`
  this exchange made true; 0 = none). Both default, so authored fixtures stay
  valid; the ACTOR prompt asks for them and for a reply written *from* the
  character's current state.
- `live.moods[character_id] = {mood: -2…2, trust: 0…5, last_shift,
  last_event_id}`, updated by `moods_after_turn` in `settle_resolution`:
  warmer +1/+1, colder −1/−1, a refused objective cools a character even when
  the actor says steady, a learner commitment buys one trust; everyone else
  drifts one step toward neutral each scene (a week passes, people recover).
  Idempotent per event.
- The director sees `moods` for the whole cast; the actor sees only the
  addressed character's entry (knowledge boundary as for relationships).

### Branching

- `chapter_after_scene` records `developments` (scene, index, text, outcome)
  and `last_development`; the DIRECTOR prompt says the next beat MUST follow
  from it, and honour every development when several have been taken.

### Score (the loop from WP-59)

`_scene_score` adds: +0.25 per point of the addressed character's |mood|; +0.5
when their last shift was colder (a consequence lands); +0.75 when the draft's
premise or causal reason overlaps the chapter's `last_development`.

`scripts/review_living_story.py` mirrors the mood bookkeeping and passes the
addressed character's mood to the actor, as production does.

## Tests

`tests/test_living_story.py`: moods follow the exchange and others recover,
idempotency, trust from a promise, cooling on a refusal; the development the
learner made true is recorded and none is recorded for index 0; the score
prefers a hurt character and a draft that follows the branch; prompts carry
the keys.

## Still open

- The reader does not show a character's mood; a small «Romy est froide
  depuis mardi» line on the cast page is one label away.
- Trust is not yet read by the Missions planner (Courrier) — the two surfaces
  still keep separate relationship state (`relationships.closeness`).
