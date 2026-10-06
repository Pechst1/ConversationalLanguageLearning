# WP-63 — L'horizon de saison (agendas, threads, shapes, finale, season 2)

**The findings this package answers** (WORK-PACKAGES-2026-09-21 §1): «Hard ceiling: 5 arcs
× 22 stages ≈ 88 days, then `suggested_arc=None` — no finale, no season 2, no interlude in
the living engine (`world_bible_paris_s2.json` uses `season_two_situation`, which
`_season_projection` cannot read). Characters have no off-screen life; `open_threads` are
prose with no state. Every chapter is the same 4 beats; `stale_problem` forbids any problem
from recurring, so nothing can escalate; an arc stage advances whether or not its content
happened.»

Everything below lives in `app/services/living_story.py`, the two world bibles, and one
additive field on the season page. WP-62's ledgers are untouched and are what the finale is
built from.

## 1. What landed

### Six new keys in `state["living_story"]`

| key | what it holds | written by |
| --- | --- | --- |
| `agendas{}` | `{character_id: {step, last_day, last_step_id}}` — how far each cast member is through their authored private plan | `agenda_tick`, at a chapter boundary |
| `threads{}` | `{thread_key: {state, day, last_event_id}}` — the season's long questions as state | `threads_after_scene`, `close_open_threads` |
| `escalated_problems{}` | `{problem_key: {ref, day, chapter_id}}` — the problems that have already come back once | `bind_journey` |
| `season_stage` | `running \| finale \| interlude` — the phase the next chapter opens in | `season_stage_after_chapter` |
| `season_chapters`, `chapters_total` | chapters since the season began, and chapters this life has ever opened | `bind_journey` |
| `season_index`, `seasons[]`, `world_flags{}`, `threads_archive[]` | which season this is, the ones behind it, the facts they established, and their closing thread states | `roll_over_season` |

Plus four fields on the stored chapter: `shape`, `location_id`, `character_id`,
`side_story`/`stage_reached` (and `finale` / `interlude` / `interlude_beat_id` on the two
chapters that get them). Every read is `… or {}` / `… or []` and every default is the
pre-WP-63 behaviour, so a thread stored before this package loads unchanged — a chapter with
no shape is the four-beat chapter it has always been
(`test_a_thread_stored_before_the_season_horizon_still_loads`). There is no migration.

### Character agendas — a life between the scenes

`character_agendas` in the world bible: an authored 4–6 step private plan for every cast
member, each step `{id, summary, meanwhile_fr, witnesses[]}`. `agenda_tick` runs **between
chapters** (when `chapter_closing`), rolls `sha256(thread_id:agenda:<chapter>)`, and on two
turns in three advances exactly one agenda — never more, and a quiet fortnight is a real
outcome, not a bug.

What it writes is a `meanwhile` event in the same `events[]` ledger as the learner's own
days: `{id: "meanwhile:<character>:<step>", kind: "meanwhile", witnesses: [...], summary_fr}`.
The witnesses are the authored ones and never include the character whose week it was, so the
existing witness filter in `_turn_payload` does the rest: **the learner can only ever hear
about it second-hand, from somebody who was there.** The director gets
`agendas_projection` — one line per character, the step they are on now, at most five rows;
the actor gets their own row and nobody else's.

### `threads{}` — the season's long questions, with state

`season_threads(world)` gives the authored threads stable keys (`s<season>:<index>`), the
English line the director reads and the French line the learner reads (`open_threads_fr`,
new in both bibles). `SceneDraft.season_thread` + `.thread_shift` advance one of them
`open → developing → closed`, forwards only, idempotent per event, an unknown key dropped by
the validator rather than a lost day. `closed` out of turn — mid-chapter — is recorded as
`developing` instead: the chapter that is still settling the question has not settled it
yet. The finale closes whatever is left (`close_open_threads`).

### Arc gating

`arc_progress_after_scene` now needs three things where it used to need one:

1. the chapter resolved and names an arc (as before);
2. **the accepted output marked the stage as having happened** — `SceneDraft.advances_arc`
   with `arc_stage_id`, carried onto the chapter as `stage_reached`. A chapter that claims
   nothing is recorded as a **side story** (`chapter["side_story"]`, and `side_story` on its
   chronicle row): a real evening in this life that did not move the season;
3. the authored gates pass — `entry_requires` on the stage, checked against `arc_flags`
   (derived from the `sets` of the stages actually reached, plus `world_flags` carried across
   seasons), and `min_episodes_between_stages` on the arc, checked against `day_index`.

`_season_projection` exposes `blocked_by` per arc and prefers an unblocked arc for
`suggested_arc` — falling back to a blocked one rather than to `None`, because a season with
nothing left to play needs an ending, not a silence.

### Escalation instead of the blanket ban

`stale_problem` used to refuse any problem that had been played in the last
`PROBLEM_WINDOW` chapters. It now lets one back **exactly once**, and only when
`SceneDraft.escalates_ref` names a real consequence, an unpaid plant or today's callback
candidate (`escalation_refs`). The escalation is spent when the chapter is published
(`escalated_problems`), and the rejection hint now tells the director both alternatives and
which ids it could legitimately escalate from.

### Chapter shapes

`CHAPTER_SHAPES` is the deck, dealt by `sha256(thread_id:shape:<chapters_total>)`, never the
same shape twice in a row (`chapter_shape(seed, index, previous)`):

| shape | beats | what else it means |
| --- | --- | --- |
| `standard` (×2 in the deck) | setup · complication · turn · resolution | the WP-58 chapter |
| `two_hander` | setup · turn · resolution | one character besides the learner — guard `two_hander_crowded` |
| `bottle` | four beats | one room for the whole chapter — guard `bottle_left_the_room` |
| `ensemble` | setup · complication · complication · turn · resolution | a crowd — rewarded by `_scene_score`, never rejected |
| `letter` | four beats | the turn beat is a Courrier letter — **a flag and a seam, nothing else** |

`required_beats`, `chapter_closing` and `chapter_state` all read the shape, so the beat
guards follow it without knowing it exists. The letter chapter writes no letter: it exposes
`chapter.shape == "letter"`, `context["chapter_shape"]["letter_beat"]`,
`scene.source_snapshot["chapter"]["letter_beat"]` and the helper `letter_chapter_seam(live)`
for WP-64/65 to consume.

### The season ends

`season_completion` measures the authored stages played. When it reaches
`SEASON_COMPLETE_RATIO` (80 %) — **or** when the season has run `SEASON_MAX_CHAPTERS` (40)
chapters without getting there — the next chapter is the **finale**: forced `ensemble`,
built from `finale_context` (the heaviest consequences by `top_consequences`, every unpaid
plant, the threads still open) and closing the season's threads when it lands. The chapter
after it is the **interlude**, an authored quiet beat reused from the serial's own
`INTERLUDE_BEATS`. When that closes, `roll_over_season` swaps the world bible through the
serial's own loader: season two's arcs, threads and agendas, the same cast, locations and
art, and the life carried over untouched — chronicle (which folds per season, exactly as
WP-62 built it to), consequences, plants, secrets, moods, commitments, plus `world_flags` so
a later `entry_requires` can still read what this learner did in season one. With no next
season authored, the life stays in the interlude playing quiet chapters rather than looping a
second finale — the legacy engine's «entre deux saisons» rule.

`_season_projection` reads the right situation per season (`season_situation`), which is the
one-line fix the s2 bible had been waiting for.

## 2. Public helpers and constants

`chapters_total`, `chapter_beats`, `chapter_shape`, `planned_shape`, `shape_note`,
`letter_chapter_seam`, `season_situation`, `season_threads`, `threads_projection`,
`threads_after_scene`, `close_open_threads`, `character_agendas`, `agendas_projection`,
`agenda_tick`, `arc_flags`, `arc_stage_gate`, `season_completion`, `season_phase`,
`season_stage_after_chapter`, `finale_context`, `interlude_beat`, `roll_over_season`,
`escalation_refs`. Constants: `CHAPTER_SHAPES`, `SHAPE_DECK`, `DEFAULT_SHAPE`,
`TWO_HANDER_CAST`, `ENSEMBLE_CAST`, `LETTER_BEAT`, `AGENDA_TICK_SIDES`,
`AGENDA_PROMPT_LIMIT`, `MEANWHILE_PREFIX`, `THREAD_STATES`, `ESCALATION_LEDGER_LIMIT`,
`SEASON_COMPLETE_RATIO`, `SEASON_MAX_CHAPTERS`, `FINALE_CONSEQUENCES`, `FINALE_PLANTS`.

New `SceneDraft` fields, all optional with defaults so every stored draft and authored
fixture stays valid: `arc_stage_id`, `advances_arc`, `season_thread`, `thread_shift`,
`escalates_ref`.

New director context keys: `agendas`, `chapter_shape`, `season`, `escalated_problems`, and
`world.open_threads` is now rows with state. The actor sees none of them except its own
agenda row (`_turn_payload` pops `season`, `escalated_problems`, `chapter_shape` and
`world.open_threads`).

## 3. Surfaces

- `GET /api/v1/serial/season` gains `threads: [{key, text_fr, state}]` — additive, read-only,
  from the same projection the engine uses.
- `SeasonPage.tsx` prints «Les fils de la saison»: the French line per thread with «ça
  bouge» / «en suspens» / «réglé», moving threads first and settled ones last
  (`seasonThreads`, `seasonThreadLabel`). A payload without the key shows no section.
  av2 styling, French chrome; `tsc`, `next lint` and the node suite are green.

## 4. Deviations from the brief

1. **A two-hander is the learner and one character.** The brief says "two-hander (3 beats)";
   `TWO_HANDER_CAST = 1` counts characters, because the learner is the voice that is always
   in the room.
2. **The ensemble's fifth beat is a second complication**, not a new beat name. Adding a beat
   to `SceneDraft.beat`'s literal would have invalidated every stored draft for a shape that
   an extra complication serves just as well.
3. **The ensemble's crowd is a preference, not a guard.** A "not more than" rule (one room,
   two voices) can be obeyed on demand; "at least three characters" could cost a learner
   their day for a shape they never asked for, so `_scene_score` rewards it instead.
4. **`chapters_total` is a new counter.** `chapters_opened` is bounded by the twelve retired
   questions the state keeps, so on a long life it stops moving — fine for WP-62's callback
   die, useless for dealing shapes and ticking agendas, which must keep changing forever.
5. **A chapter ceiling forces the finale** even when the arcs never advanced
   (`SEASON_MAX_CHAPTERS`). Without it a life whose director never claims a stage would run
   forever below 80 % and the brief's "never `suggested_arc=None` without a finale" would
   depend on the model's goodwill.
6. **`suggested_arc` falls back to a blocked arc** rather than to `None`: the block is the
   reason the director is told (`blocked_by`), not a reason to tell it nothing.
7. **The rollover lives in `settle_resolution`**, where the chapter closes, and reuses
   `SerialThreadService._load_next_season_world_bible` rather than re-implementing the merge.
8. **One interlude chapter, not a phase of several.** The authored deck is reused for its
   content; with no season three authored, the life then stays in the interlude indefinitely,
   which is the legacy rule.

## 5. Tests

Run per file (the full suite is ~35 min) — all green on 2026-09-21:

| file | result |
| --- | --- |
| `tests/test_living_story.py` | 96 passed |
| `tests/test_living_story_longitudinal.py` | 30 passed (~45 s) |
| `tests/test_living_story_budget.py` | 9 passed — the two-attempt 75 s budget is untouched |
| `tests/test_living_story_address.py` | 10 passed |
| `tests/test_journey_story_outcomes.py`, `tests/test_journey_end_to_end.py`, `tests/test_serial.py`, `tests/test_wp28_integration.py`, `tests/test_wp29_hooks.py`, `tests/test_story_correspondence.py` (WP-64), `tests/test_frontend_av2_chrome_language.py` (WP-67) | all passed |
| `ruff check` on the changed Python files | clean |
| `tsc --noEmit`, `next lint`, `node --test season.test.js` | clean, 10 passed |

New unit tests (`tests/test_living_story.py`): a chapter is dealt a seeded shape that is
reproducible per learner, different between learners and never repeated twice in a row, and
the beat guards follow it; a two-hander with a third voice and a bottle that leaves its room
are refused with actionable hints; an arc advances only on an honest stage claim, only when
`entry_requires` and `min_episodes_between_stages` allow it, and a chapter that claims
nothing is a side story in the chronicle; a played problem returns once as an escalation tied
to a real consequence or plant, and is refused a second time and with an invented ref; the
cast's agendas tick at most one per chapter with witness rules respected and different
timings per learner; the season's long questions advance forwards only, drop an unknown key,
downgrade an out-of-turn close and are all closed by the finale; the season reaches 80 %,
plays a finale built from the heaviest consequences and unpaid plants, an authored interlude,
and a second season whose bible, arcs, threads and agendas are its own while the life carries
over; the letter chapter is a flag and a seam; the director reads the horizon and the
character does not; both prompts carry it; and a thread stored before this package still
loads.

New longitudinal tests (`tests/test_living_story_longitudinal.py`):

- **200 consecutive days through the assembled API, one learner** —
  `test_two_hundred_days_reach_a_finale_an_interlude_and_a_second_season`: no day is ever
  served with no arc and no ending; the phases go running → finale → interlude; the finale
  context carries the season's weight and the interlude its authored beat; season two's own
  arcs are on the thread; season one's chronicle, consequences, secrets, archived threads and
  world flags survive the rollover; side stories exist; at least four shapes appear and no
  dealt chapter repeats the previous shape; the cast's off-screen week is in the ledger with
  witnesses; and the day-200 prompt is no more than 1.6× the day-20 one.
- `test_two_seeds_deal_different_arcs_shapes_and_agenda_timings`: two learners, 24 days each,
  different arc orders, different chapter shapes and different agenda timings.

The fixtures gained two compliance flags: `ScriptedProvider.season_engine` (claims the arc
stage it was offered when the arc is not blocked, moves a thread) and shape-obedience in both
`draft()` helpers (a bottle chapter stays in its room and rotates the person instead). Both
are off by default, so every older test keeps the exact draft it pinned.

`scripts/review_living_story.py` mirrors the new bookkeeping — shapes and the
finale/interlude overrides at `open_chapter`, gated `arc_progress_after_scene`, thread
advances, the agenda tick and the real `roll_over_season` on a stand-in thread — so the paid
prose review walks production rather than a second implementation of it. It was smoke-tested
end to end against a scripted fake (twelve synthetic days, `sample_ready_for_human_review`);
**no live provider call was made and nothing was spent.**

## 6. What is still open

- The letter chapter is only a seam: WP-64/65 own the letter that fills it, and until they
  land a letter chapter plays as an ordinary four-beat chapter.
- The chronicle is still not surfaced to the learner; the season page shows the threads and
  the open commitments, not the life's own digest (WP-65).
- `min_episodes_between_stages` is measured in `day_index`, which is settled exchanges, not
  calendar days: a learner who plays twice in one day moves the season twice as fast.
- The paid live review with the new horizon (`scripts/review_living_story.py --live --days
  14`) is prepared but **not run** — it costs money and the owner consents first (WP-68).
