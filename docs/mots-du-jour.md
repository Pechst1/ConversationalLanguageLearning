# Les Mots du jour — the daily vocabulary loop (shipped 2026-07-18)

## What it is

Before this feature, vocabulary lived in pairwise links (mission → review linked
words, scene → review) but **each surface sampled the due pool independently** —
no day-level coordination, no visible loop, and the review deck was a bare card.

Now every edition conspires to teach the same handful of words. Each day the app
selects up to **4 focus words** and each word wants **three stamps in three
memory modes** before midnight:

| Stamp | Memory mode | Where it's earned |
|---|---|---|
| **LU** | reception in context | today's feuilleton scene completed with the word |
| **RETROUVÉ** | active retrieval | a review grade submitted in the deck (`/progress/review` or `/anki/review`) |
| **PLACÉ** | production | mission completion credits the word `produced_correct` |

All three in one day = **Triplé** (visible on La Une). Retention rationale:
spaced retrieval + contextual variation + generation/production + episodic
self-reference — the review card shows an *episodic anchor* ("Lu dans
l'épisode 3 · Le radiateur froid") drawn from the learner's own story, after
the answer (never spoils).

## Selection (deliberate, persisted per user+day)

`DailyWordSlateService._select` ([app/services/daily_words.py](../app/services/daily_words.py)):
due ∩ today's-scene-vocabulary first (the LU encounter comes free), then due,
then fragile, at most 1 new. **Nailed words are excluded** (a mastered word with
no scheduled review can surface in the "due" bucket; the slate exists for shaky
memory, not victory laps — uses `vocabulary_coverage.is_vocab_nailed`).
Persisted in `user_daily_word_slates` (migration `b9c0d1e2f3a4`) so all
surfaces agree all day; concurrent first-call races resolve to the winner's
row. Anchors come from the latest scene/mission carrying the word.

## Wiring map

- **Endpoint**: `GET /api/v1/vocabulary/words-of-the-day`
  ([endpoints/vocabulary.py](../app/api/v1/endpoints/vocabulary.py), creates on first call).
- **Stamp hooks (server-side, idempotent per day)**:
  `retrouve` in [endpoints/progress.py](../app/api/v1/endpoints/progress.py) `/review` and
  [endpoints/anki.py](../app/api/v1/endpoints/anki.py) `/review`;
  `place` in `MissionGenerator._apply_target_vocabulary_credit`
  ([services/missions.py](../app/services/missions.py));
  `lu` in `GraphicNovelScheduler.complete` ([services/graphic_novel.py](../app/services/graphic_novel.py)).
  Encounters never *create* a slate — selection stays a deliberate act.
- **Selection bias (surfaces converge on the slate)**: `mot_du_jour` bucket in
  `MissionGenerator._select_vocabulary` — **default daily missions only**
  (skipped when the mission has explicit preferred vocabulary or an active
  category theme, so seeded/themed missions keep their identity), takes only
  due/fragile slate words via `focus_word_ids` (producing a word first met
  today would be premature), capped to leave room for recently-nailed words.
  The feuilleton's `_select_vocabulary` takes **all** slate words (after
  explicit targets and errata repairs) — a first contextual meeting of a new
  word in the story is exactly right there.
- **Frontend**: `components/lexique/MotsDuJour.tsx` — token-pure strip on La Une
  (mounted in `pages/atelier.tsx` TodayView) with per-word LU · RETROUVÉ · PLACÉ
  stamps and the Triplé mark; renders nothing when the slate is empty.
  `pages/vocabulary/review.tsx` floats slate words to the front of the deck,
  tags them "Mot du jour", and shows the episodic anchor on the answer face.
  `apiService.getWordsOfTheDay()` in `services/api.ts`.

## Tests

- [tests/test_daily_words.py](../tests/test_daily_words.py) — selection stability +
  cap, scene-preference + anchor, stamp idempotence + triple detection, `lu` on
  scene completion, `mot_du_jour` bucket in mission selection, endpoint + `retrouve`
  hook end-to-end via the API.
- [tests/test_frontend_mots_du_jour.py](../tests/test_frontend_mots_du_jour.py) —
  static regressions for the strip, the API client, and the review-deck wiring.

## Deliberately not done (candidates for a later pass)

- No SRS mutation on Triplé — the reward is visibility (and the three encounters
  already feed the SRS through their own credit paths); minting a collectible for
  a Triplé day would reuse `atelier_rewards` and is a natural follow-up.
- The slate is capped at 4 and takes at most 1 new word; tuning per user
  (`new_words_per_day`) is a follow-up.
- La Une strip links to the review deck; a dedicated per-word "biography" jump
  from the strip is a follow-up.
