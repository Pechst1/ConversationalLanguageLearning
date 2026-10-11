# WP-62 — La mémoire longue (story long-term memory)

**The finding this package answers** (WORK-PACKAGES-2026-09-21 §1): «Memory is a flat
tail: `events[-40]`, `story_so_far[-8]`; nothing is compacted, so day 100 cannot
reference day 5. Branches die with their chapter; moods decay to neutral in ~2 scenes —
a betrayal is forgotten in two days. No payoff/foreshadow ledger; cast `secret`s are
static prompt text and reveals are never checked.»

Everything below lives in `app/services/living_story.py`. No other module was touched.

## 1. What landed

### Four ledgers in `state["living_story"]`

| key | what it holds | written by |
| --- | --- | --- |
| `day_index` | monotonic count of settled exchanges — the "how long ago" the rolling `events` tail cannot answer | `settle_resolution` |
| `chronicle[]` | one digest per **closed** chapter; older ones folded into a per-season digest | `chronicle_after_chapter` |
| `consequences[]` | durable rows for what the learner *did*: branches, mood breaks, promises kept, promises nobody kept | `consequences_after_turn` |
| `planted[]` | the foreshadow ledger: a detail a scene planted, and whether a later scene paid it | `plants_after_scene` |
| `secrets{}` | `{character_id: hidden \| hinted \| revealed}` | `secrets_after_turn` |

All five are written **inside `settle_resolution`**, from output the deterministic
guards and the critic already accepted, and all are **idempotent per `event_id`** — a
replayed settle (the duplicate-request path) writes nothing twice. Every read is
`… or {}` / `… or []`, so a thread stored before this package loads unchanged: there is
no migration, and a learner mid-chapter on the day it ships simply starts with an empty
chronicle.

### `chronicle[]` — a digest per chapter, folded by season

A chapter row: `{id, season, day, title_fr, question, resolved_fr, development,
characters[], location_id, quote, arc_id, event_id}` — the title, the question it asked,
how it actually resolved, the development the learner made true, who was there, where,
one of the learner's **own** quotes, and the day it closed.

`chapter_closing(chapter)` decides when one is written: `resolved`, **or** exhausted by
`CHAPTER_RESOLVED_COMMITMENT_LIMIT` resolved commitments, **or** `CHAPTER_MAX_SCENES`
scenes. The middle case was a memory hole — a chapter replaced because its commitments
ran out never wrote a resolution beat and used to vanish without trace.

`fold_chronicle` keeps detail for the last `CHRONICLE_DETAIL_CHAPTERS` (10) chapters and
folds the rest into one season row per `season`, whose `facts[]` keeps the **first
three** lines it ever folded plus the last two. That asymmetry is the whole design: the
beginning of a life is the part a long memory keeps, so day 100 still carries week one,
and the list is bounded whatever the horizon.

`chronicle_for_prompt` renders it as short lines and trims **from the middle** to
`CHRONICLE_PROMPT_CHARS` (1200) — both ends of the life survive, which is what a reader
of a serial remembers.

### `consequences[]` — what outlives the chapter

Four kinds, each with `weight` (1–5), `day`, `quote`, `character_id`, `chapter_id` and
`last_referenced`:

- `branch` — the development the learner made true (weight 3 if it closed the chapter);
- `mood_break` — the addressed character reached `|mood| >= MOOD_BREAK_THRESHOLD` (the
  edge of `MOOD_RANGE`) and moved further out than they were (weight 3 hurt / 2 glowing);
- `commitment_kept` — a promise resolved by this exchange (weight 2);
- `commitment_broken` — a promise still open `COMMITMENT_LAPSE_DAYS` (10) days after it
  was made (weight 3). Recorded **once** (`lapsed_at` is marked on the commitment row in
  place) and the commitment's status stays `open`: a promise nobody kept is still owed,
  and the engine does not cancel it for the learner.

`top_consequences(rows, day=…)` is the prompt projection: heaviest first, and a row a
scene really used sinks for about six days (`last_referenced`), so a life with one
dramatic betrayal does not spend a month re-opening it. The ledger is capped at
`CONSEQUENCE_LEDGER_LIMIT` (60) by dropping the **lightest and oldest** first, never the
front of the list.

**Trust no longer decays.** `moods_after_turn`'s drift loop only ever touched `mood`;
that is now stated, commented and pinned by a test. Trust moves only from what the
learner did.

### `planted[]` — foreshadow and payoff

`SceneDraft.plant_fr` plants one concrete detail; `SceneDraft.pays_plant_id` pays one.
`plants_due(planted, chapter_index=…)` offers back any unpaid plant at least
`PLANT_OVERDUE_CHAPTERS` (2) chapters old, at most `PLANT_PROMPT_LIMIT` (3) of them.
An invented `pays_plant_id` is a no-op, never a rejected day.

### `secrets{}` — state, with a seeded order

`secret_order(cast_ids, seed)` is a `sha256(thread_id:secret:<id>)` permutation:
`secrets_projection` gives the director every character's state plus `next`, the one
character whose secret this life may bring out now. `secrets_after_turn` advances a
character **forward only**, from `SceneDraft.secret_shift` and `SemanticTurn.secret_shift`.
A full reveal out of seeded turn is **downgraded to a hint** rather than rejected — a
deterministic repair must not cost the learner their day (the WP-58 rule).

### The callback loop

- `story_context` sends `chronicle`, `consequences`, `plants_due`, `secrets`,
  `day_index`, and — **on setup beats only** — one `callback` candidate.
- `callback_candidate(live, seed=…, beat=…)` draws from the consequence ledger (each row
  repeated by its weight) plus every chronicle row **including the folded season facts**,
  with `sha256(thread_id:callback:<chapter index>)`. Reproducible per learner, different
  per learner (principle 1). Mid-chapter it returns `None`: the story already has its
  thread to follow.
- `_scene_score` adds +0.5 for any real callback, +1.0 more when the draft takes the
  candidate it was *offered*, and +0.75 for paying an overdue plant.
- **Guard `fabricated_callback`**: a non-empty `SceneDraft.callback_fr` must be grounded
  — `callback_ref` in one of the ledgers, or ≥ `CALLBACK_OVERLAP` (0.15) content-word
  overlap with a chronicle line, a consequence, an event (summary or learner quote), an
  open commitment, an unpaid plant, a retired chapter question or `story_so_far`. On day
  one there is no past, so every callback is by definition invented. The rejection hands
  the retry an instruction, including the candidate it should have used (the rule
  `test_every_deterministic_guard_tells_the_retry_what_to_change` enforces). A
  `callback_ref` nobody holds, with grounded text, is **dropped** rather than fatal —
  exactly as unknown `source_event_ids` already are.

### Knowledge boundary

The director's planning surface stays the director's: `_turn_payload` pops `chronicle`,
`plants_due` and `callback`, filters `consequences` to rows about the addressed
character, and reduces `secrets` to `{character_id: state}` — a character is told
whether their own secret is out, not handed the season's index card.

## 2. Schema (exact keys WP-63 can build on)

```python
state["living_story"] = {
    "day_index": 120,
    "chronicle": [
        {"kind": "season", "season": 1, "chapters": 20, "from_day": 4, "to_day": 84,
         "facts": ["j4 · Titre — comment ça s'est fini", ...], "characters": [...]},
        {"id": "<chapter id>", "season": 1, "day": 88, "title_fr": ..., "question": ...,
         "resolved_fr": ..., "development": ..., "characters": [...], "location_id": ...,
         "quote": "<the learner's own words>", "arc_id": ..., "event_id": ...},
    ],
    "consequences": [
        {"id": "<event id>:<kind>:<n>", "kind": "branch|mood_break|commitment_kept|commitment_broken",
         "character_id": ..., "text_fr": ..., "quote": ..., "weight": 3, "day": 7,
         "event_id": ..., "chapter_id": ..., "last_referenced": 46 | None},
    ],
    "planted": [
        {"id": "<event id>:plant", "text_fr": ..., "character_id": ..., "chapter_id": ...,
         "chapter_index": 4, "day": 14, "status": "open|paid", "event_id": ...,
         "paid_by": ..., "paid_day": ...},
    ],
    "secrets": {"lila_bonnet": "hinted"},
    # unchanged: chapter, recent_situations, events, commitments (+ new "day" and
    # optional "lapsed_at" per row), moods, arc_progress, resolved_chapter_questions
}
```

Public helpers (all pure, all importable): `chapter_digest`, `chapter_closing`,
`fold_chronicle`, `chronicle_after_chapter`, `chronicle_for_prompt`,
`consequences_after_turn`, `top_consequences`, `mark_consequence_referenced`,
`callback_candidate`, `plants_after_scene`, `plants_due`, `secret_order`,
`secrets_projection`, `secrets_after_turn`. Constants: `CHRONICLE_DETAIL_CHAPTERS`,
`CHRONICLE_SEASON_FACTS`, `CHRONICLE_SEASON_HEAD_FACTS`, `CHRONICLE_PROMPT_CHARS`,
`CHRONICLE_LINE_CHARS`, `CONSEQUENCE_PROMPT_LIMIT`, `CONSEQUENCE_LEDGER_LIMIT`,
`MOOD_BREAK_THRESHOLD`, `COMMITMENT_LAPSE_DAYS`, `PLANT_OVERDUE_CHAPTERS`,
`PLANT_LEDGER_LIMIT`, `PLANT_PROMPT_LIMIT`, `CALLBACK_OVERLAP`, `SECRET_STATES`.

New model fields: `SceneDraft.callback_fr`, `.callback_ref`, `.plant_fr`,
`.pays_plant_id`, `.secret_shift`; `SemanticTurn.secret_shift`. All optional with
defaults, so every stored draft and authored fixture stays valid.

## 3. Deviations from the brief

1. **`season_index` is read, never written.** `chronicle_after_chapter` takes
   `season=int(live.get("season_index") or 1)` and folds per season, so WP-63 only has
   to bump that one counter for season 2 to fold separately; nothing here creates it.
2. **Mood break means the edge of the range, not a two-point jump.** One exchange moves
   a mood by at most one step (`moods_after_turn`), so a literal `|shift| >= 2` could
   never fire. The rule implemented is: the character reached `|mood| >= 2` *and* moved
   further out than they were — which is what «a betrayal is not forgotten» actually
   needs, and it fires on the 120-day run.
3. **"Day 100 contains a day-5 fact" is tested as "a fact from the first five days".**
   A chapter is at most four scenes, so this life's first chapter closes on day 4, not
   day 5. The longitudinal test pins `from_day <= 5` and follows one exact sentence said
   on day 4 all the way into the day-100 and day-120 director contexts.
4. **`secrets` has a different shape for the director and the actor** (`{states, order,
   next}` vs `{character_id: state}`). The actor may know its own secret's state, not
   the season's reveal order.
5. **No guard on `pays_plant_id`.** `plants_after_scene` pays a row it can find; an id
   nobody holds is a no-op. A second guard here could only cost days, never buy quality.
6. **`chapter_closing` also folds an *exhausted* chapter** (not in the brief). It closes
   a real memory hole: a chapter replaced by the commitment limit left no record at all.

## 4. Tests

Run per file (the full suite is ~35 min) — all green on 2026-09-21:

| file | result |
| --- | --- |
| `tests/test_living_story.py` | 85 passed |
| `tests/test_living_story_longitudinal.py` | 28 passed |
| `tests/test_living_story_budget.py` | 9 passed (the two-attempt 75 s budget is untouched) |
| `tests/test_living_story_address.py` | 10 passed |
| `tests/test_journey_story_outcomes.py` | 30 passed |
| `tests/test_journey_end_to_end.py` | 50 passed |
| `ruff check` on the four changed files | clean |

Also run as regression, all green: `test_wp28_integration`, `test_wp29_hooks`,
`test_wp36_self_repair`, `test_journey_latency`, `test_pragmatics_register`,
`test_rehearsal`, `test_lexical_coverage`, and WP-64's `test_story_correspondence`.

New unit tests (`tests/test_living_story.py`): a resolved chapter folds into one digest
and a replayed settle writes no second one; thirty chapters fold into a season that
still names chapter 0, and the prompt rendering stays under 1200 characters with both
ends of the life intact; consequences outlive their chapter, a referenced one sinks, and
trust does not decay; a promise nobody kept becomes one consequence and stays open; an
unpaid plant comes back until a scene pays it; a callback to a past that never happened
is refused with an actionable hint while a stray id is merely dropped; the score rewards
the offered callback and an overdue plant; two seeds deal different callbacks and each
life the same ones; secrets advance forward only with a seeded order and an out-of-turn
reveal downgraded; both prompts carry the new keys; and one assembled-API day proves the
ledgers are written and that the chronicle/callback never reach the actor.

New longitudinal tests (`tests/test_living_story_longitudinal.py`):

- **120 consecutive days through the assembled API, one learner** —
  `test_day_one_hundred_still_knows_the_first_week_and_the_context_stays_bounded`:
  `day_index == 120` while `events` is still the 40-row tail; one season digest of ≥ 15
  chapters plus exactly 10 detailed ones; the sentence said on day 4 is in the day-100
  **and** day-120 director contexts; the chronicle block is under
  `CHRONICLE_PROMPT_CHARS` and the whole day-120 prompt payload is no more than 1.6× the
  day-20 one; all four consequence kinds present, at least one `last_referenced`, at
  least one plant paid, secrets moved. ~15 s.
- `test_two_lives_are_offered_different_memories`: two threads, twelve days each, the
  seeded callback sequence reproducible per learner and different between them.

The fixture gained `_composed_question` (two disjoint word banks behind the existing
`_fresh_question`) because nine authored questions cannot carry thirty chapters, and a
`ScriptedProvider.long_memory` flag that makes the fake director behave like a compliant
one (takes the offered callback, pays an overdue plant, plants a new detail). It is off
by default, so every older test keeps the exact draft it pinned.

`scripts/review_living_story.py` mirrors all five writers and the projections, so the
paid prose review walks the real code rather than a second implementation of it. It was
smoke-tested end to end against the scripted fake (six synthetic days); **no live
provider call was made and nothing was spent.**

## 5. What WP-63 (l'horizon de saison) can build on

- **Season 2**: set `live["season_index"] = 2` at the interlude. `fold_chronicle` will
  keep season 1's digest as its own row and start a second one; `chronicle_for_prompt`
  renders both, oldest first. Carry `consequences`, `planted`, `secrets` and `moods`
  across untouched — none of them is keyed on a chapter or an arc.
- **The finale**: `top_consequences(live["consequences"], day=live["day_index"])` is the
  "heaviest consequences" list the brief asks a finale to be built from, and
  `plants_due(live["planted"], chapter_index=chapters_opened(live), overdue=0)` is every
  unpaid plant.
- **Escalation instead of the blanket `stale_problem` ban**: a returning problem is
  legitimate exactly when it is linked to a consequence or a plant — both now have ids
  a draft can cite (`callback_ref`, `pays_plant_id`), and `_callback_grounded` is the
  check for "this past is real".
- **`meanwhile` events / agendas**: append to `live["events"]` as WP-64 does; the
  chronicle only reads chapters, so off-screen ticks will not distort it.
- **Chapter shapes**: `chapter_closing` is the single place that decides a chapter is
  over, and `chronicle_after_chapter` is the single writer of the digest — a three-beat
  two-hander or a five-beat ensemble needs no change here, only a different
  `CHAPTER_BEATS` walk.

## 6. What is still open

- The `stale_problem` ban is untouched (WP-63 owns escalation), so a consequence can be
  referenced but the problem behind it still cannot return.
- Nothing yet surfaces the chronicle to the learner; the season page is WP-63/WP-65.
- The paid live review with the new ledgers (`scripts/review_living_story.py --live
  --days 14`) is prepared but **not run** — it costs money and the owner consents first
  (WP-68).
