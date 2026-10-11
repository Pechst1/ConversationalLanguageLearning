# WP-64 — Le Courrier vit dans l'histoire

Backend package. Spec: `WORK-PACKAGES-2026-09-21.md` §3 WP-64. Frontend follow-up:
WP-65, which renders everything listed under **Payload shapes** below.

The finding this closes: the Courrier and the Feuilleton were coupled one way. The
story's mood coloured the letter (WP-61), and no mission code ever wrote
`state["living_story"]` back — a rude letter to Romy changed nothing about
tomorrow. Selection was a fixed catalogue walk (`ordered[0]`, `count % 3`), success
was a keyword read over the learner's punctuation, `resolve_outcome` was a stub
written for episode 1's radiator, and the debrief printed four numbers, three of
which were formulas over word count.

## What landed

### 1. The writeback (`app/services/story_correspondence.py`, new)

One module owns every write into `thread.state["living_story"]` on behalf of a
letter. `living_story.py` is untouched; only its public names are imported
(`STATE_KEY`, `MAX_HISTORY`, `MOOD_RANGE`, `TRUST_RANGE`).

On `MissionScheduler.complete`:

- an **`events[]` row** `{id: "courrier:<mission_id>", scene_id: null, witnesses:
  [correspondent_id], summary_fr, source_quotes, outcome, at, source: "courrier",
  mission_id}` — idempotent per mission, capped with the journey's own
  `MAX_HISTORY`, and stamped `source: "courrier"` so the director can say «dans
  votre lettre» rather than «dans la scène»;
- a **mood/trust step** on the existing `moods{}` structure: `kept` +1/+1,
  `partial` 0/0, `missed` −1/0, `ignored` −1/−1. Unlike `moods_after_turn`, nobody
  else drifts — a letter is private and the rest of the cast did not hear it;
- **commitments** opened from the promises the letter actually makes (near future,
  simple future, `je m'engage`, `promis`, `on se voit`; the `-rais` conditional is
  politeness and is deliberately not a promise), and an open commitment witnessed
  by this correspondent is closed when a `kept` letter restates it;
- one line appended to `state["story_so_far"]`.

It runs for any learner with a living-story thread, **with no reference to
`SERIAL_WORLD_ENABLED`** — that flag still gates only the legacy serial episode
machinery in `_advance_serial_thread`. It never raises into `complete()`.

`resolve_outcome`'s radiator stub is replaced: the outcome is `kept | partial |
missed` from the corrector's per-objective `met` flags. `heating_fixed` /
`marchand_trust` are still written when the thread genuinely tracks them, so the
authored pilot keeps working; they are no longer the shape of every outcome.
`branch_state` survives as a nudge inside the delta (`state_delta["nudge"]`) and no
longer gates `turn_outcome`'s `ready_to_advance`.

### 2. Correspondent threads

`RealWorldMission.correspondent_id` is a stable identity across standalone letters,
chains and living-story cast members. `thread_history()` returns the last three
finished letters with that person (oldest first) and feeds:

- `build_payload(correspondence=…)` → `prompt_payload["correspondence"]`;
- the scenario prompt (`letters_with_this_person`, `how_they_feel_about_the_learner`,
  `unanswered_letter_to_mention_once`, `chain`) plus a system-prompt clause pinning
  the contact's identity across instalments;
- `messenger.thread_recap` and a `realism_rules` line for the fallback path.

`callbacks` in the sense the spec asked for are written as the event's
`summary_fr` + `source_quotes`, which is what `story_context` already reads.

### 3. Chains

2–4 letters, seeded (`CHAIN_OPEN_PROBABILITY = 0.45`). Letter 1 may be the weekly
letter; instalments 2..n arrive as `ad_hoc` letters that `today()` materialises and
promotes to `active_mission`. `stakes_level` climbs by one per instalment. The
outcome of letter k is carried into k+1 verbatim (`after_outcome`,
`after_summary_fr`) and shapes both the prompt and the fallback realism rule.

Soft expiry: `expires_at` = created + 2–5 days (seeded, tighter at higher stakes),
on chain letters only and **never on the weekly letter** — the weekly row is unique
per ISO week and a lapsed week could not be replaced. `lapse_overdue_letters()`
marks an overdue chain letter `status="lapsed"`, `outcome="ignored"`, writes the
ignored event, cools the correspondent by one and stores a one-time
`mention_fr` that the next letter from that person carries. No failure screen; the
remark is cleared by the next finished letter.

### 4. Story-born letters

`story_letter_candidate()` scans the eight most recent unused journey events
(`scene_id` present), rolls a per-event seeded die at 50 %, picks a witness, and
returns a candidate. Capped at two per ISO week by a ledger in
`state["courrier"]["story_born"]`; an event never produces two letters. The
scenario is built from the stored event only — the letter cannot invent a past.

`today()` opens at most one extra letter a day (chain step first, then story-born),
and only when no `ad_hoc` letter is already open, so the one-CTA rule holds.

### 5. Seeded selection

`_choose_variety` is seeded weighted sampling over domain × contact × format.
Recency is two-tier: domain and contact are *excluded* while in the last-8 window,
channel (×0.45) and tone (×0.7) only lose weight. A category match narrows to the
domains whose whole subject is that category (food words → the bakery, not a picnic
that mentions food). `forced_domain` pins a chain's setup. `_choose_format` deals
the channel's natural format at weight 4 against `chat_message` / `email_formal` /
`voicemail_reply` at 0.5 — `admin_form` and `phone_call` arrive only from their own
channels, because both change the composer.

`_next_fuel_source` replaces `count % 3` with a seeded *permutation* of the three
sources, re-drawn each ISO week and indexed by the letter ordinal: coverage is still
guaranteed every three letters, the order is the learner's own. Deliberately not a
recency read — `created_at` has one-second resolution on SQLite and six letters made
in one second have no reliable order.

### 6. Honest numbers

Deleted from the debrief: `readiness.overall`, `clarity`, `naturalness`
(`55 + words*0.45`), `repair_stability` (`100 - errata*18`), `register` (86 or 78),
and `_latest_correction`, which fed only those. `debrief_version` is now
`mission-debrief-v2` and carries `outcome` plus `measured{objectives_met,
objectives_total, objectives_met_all, objectives_all, repairs, phrases_saved,
replies, words_written}` — every one of them counted. `branch_outcome.label` and
`next_best_move` now describe what happened rather than a score.

**Frontend impact (for WP-65):** `web-frontend/pages/missions.tsx:1108-1113` renders
the readiness tile behind `{mission.recap?.readiness && …}`, so the tile simply
disappears; `recap` is typed `extends Record<string, any>`, so `tsc` is unaffected
and no frontend file was edited. WP-65 should replace that tile with the `measured`
block. `branch_outcome.next_best_move` (`missions.tsx:841`) still exists.

## Payload shapes for WP-65

Every serialized mission (`serialize_mission`, `MissionRead` is `extra="allow"`)
now carries:

```jsonc
{
  "correspondent": { "id": "samira", "name": "Samira", "role": "boulangère",
                     "initials": "SA", "mood_line": "Un peu distant(e) en ce moment." } | null,
  "chain":        { "id": "chain:samira:2026-W39:3", "index": 2, "total": 3 } | null,
  "expires_at":   "2026-09-24T16:26:01.061009+00:00" | null,
  "thread_history": [ { "mission_id": "…", "title": "…", "summary_fr": "Le pain d'hier",
                        "outcome": "kept", "stakes_level": 1, "chain_index": 1,
                        "at": "…" } ],
  "courrier": { "correspondent": …, "chain": …, "expires_at": …, "thread_history": …,
                "outcome": "kept" | "partial" | "missed" | "ignored" | null,
                "origin": "courrier" | "chain" | "story_born" }
}
```

`outcome` is inside the `courrier` block because the top-level `outcome` key is
already taken by the legacy serial state delta and typed as an object in
`app/schemas/missions.py`; changing that type would have been a schema edit outside
this package's ownership. `mission.recap.courrier_outcome` carries the same string.

`GET /missions/{id}` refreshes `thread_history` at read time (the stored payload
holds the history the letter was *written* with); `/missions/today` serves the
stored one.

New statuses and columns: `status` may now be `"lapsed"`; the six new nullable
columns on `real_world_missions` are `correspondent_id`, `chain_id`, `chain_index`,
`chain_total`, `expires_at`, `outcome` (migration `a1c4e7b90d33`, additive, head).

`thread.state["courrier"]` holds `{chains{}, cooled{}, story_born[]}` — a namespace
outside `living_story` so WP-62's `chronicle` / `consequences` / `planted` /
`secrets` cannot collide.

## Tests

`tests/test_story_correspondence.py` (18) and `tests/test_missions.py` (36).

- writeback reaches `living_story.story_context` — event, witnesses, commitment,
  mood and `story_so_far`, with and without `SERIAL_WORLD_ENABLED`;
- idempotent writeback; a learner without a living story still completes;
- outcome from objective flags (`kept`/`partial`/`missed`), promises quoted not
  inferred (the conditional is excluded);
- last-three thread with one person; history + mood line reach the letter;
- a 3-letter chain with a missed middle letter, end to end, including the queued
  step's `after_outcome`, the pinned contact and domain, the soft deadline, and the
  cumulative mood (+1, −1, −1 → −1) at the end;
- an ignored letter lapses, cools, is mentioned once and then cleared; the weekly
  letter never lapses;
- four seeds deal ≥3 different opening sequences, no learner repeats a domain in
  three; the same seed reproduces; fuel sources still cover all three, never twice
  running;
- story-born letter from a stored event, character pinned, never twice for one
  event, capped at two a week;
- the `courrier` block over the API (`/today`, `/{id}`, `/complete`).

`pytest tests/test_missions.py tests/test_story_correspondence.py` → 54 passed.
Adjacent suites green: `test_serial`, `test_intake`, `test_daily_words`,
`test_living_story`, `test_living_story_longitudinal`, `test_graphic_novel`,
`test_frontend_serial_surfaces`, `test_vocabulary_coverage_conjugation`.
`ruff check` clean on every changed file. No provider was called; nothing was spent.

`tests/test_atelier.py::test_select_atelier_vocabulary_uses_curated_starter_for_new_user`
fails when the file is run after `test_serial.py` in the same process. Pre-existing
order dependence over the shared database (already recorded 2026-09-19); reproduced
on this branch without any WP-64 file in the run.

## Deviations from the spec

1. **No `daily_journey.py` hook.** The spec allowed a ≤5-line additive call site.
   None was needed: `story_letter_candidate()` reads the living story's own
   `events[]`, so `MissionScheduler.today()` can find a fresh journey resolution
   without the journey telling it. If a same-request letter is ever wanted, the one
   line is `story_correspondence.story_letter_candidate(db, user=user)` after
   `settle_resolution`, passed to `MissionScheduler.create(story_letter=…)`.
2. **`outcome` is exposed as `mission.courrier.outcome`**, not at the top level —
   see above.
3. **`_choose_format` excludes `admin_form` and `phone_call`** from the seeded
   alternatives; both change the composer (paperwork, live voice) and should not
   arrive as a surprise.
4. **Chains open on the weekly letter but never expire there.** The spec's "letters
   get a soft `expires_at`" is applied to instalments 2..n only, because the weekly
   row is unique per ISO week.
5. **`test_food_vocabulary_builds_food_domain_mission` still passes unchanged** —
   the category-specificity narrowing was designed to keep that promise (food
   vocabulary → the bakery) under seeded sampling rather than weakening the test.

## Still open

- WP-65 owns the surfaces: Home entry, correspondent view, chain progress, soft
  expiry, and replacing the removed readiness tile with `measured`.
- `_recent_variety` still orders by `created_at`, which is second-resolution on
  SQLite. It only feeds a recency *set*, so nothing depends on the order within the
  window — but a monotonic ordinal column would be cleaner if the window ever
  becomes order-sensitive.
- Chain and story-born letters are materialised by `/missions/today`. If the Home
  screen learns to show the Courrier without that call (WP-65), it must call the
  same entry point or the extra letters will not appear.
