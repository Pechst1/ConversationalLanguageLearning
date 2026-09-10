# WP-31 — Rehearse a real upcoming situation («Répétition»)

Spec: [INNOVATION-WORK-PACKAGES-2026-09-10.md](INNOVATION-WORK-PACKAGES-2026-09-10.md) §3.
Delivered 2026-09-10. Provider-isolated throughout: **US$0.00 spent, no live model
call was made.**

## 1. What it is

The learner declares something that is actually going to happen to them —
*« appeler le propriétaire pour le chauffage, mardi »* — in their own words, in
French or in their own language. The app structures it (goal, counterpart,
register, date, facts), generates one rehearsal scene at their band, runs three
to six graded turns, and then, on or after the declared day, asks the only
question the package is judged by: **comment ça s'est passé ?**

The evidence is narrow and the design follows it. Transfer from task rehearsal
is under-evidenced in general but positive for the lowest-proficiency learners
(Benson 2016); needs-analysis relevance is what drives adult engagement (Huang
2022). So: one rehearsal, of the learner's own declared need, measured by the
debrief and not by the rehearsal score. A learner who rehearsed beautifully and
then did not make the call has not been helped, and the digest line says so.

## 2. The boundary that shapes the whole package

[CONTINUOUS-STORY.md](CONTINUOUS-STORY.md): *distinguish fictional roleplay facts
from real learner biography*. A rehearsal is biography, and the code is built so
that it cannot become canon:

* `rehearsals` is its own table, with no foreign key into any story table.
* `app/services/rehearsal.py` imports no serial service, no living story, no
  story-outcome function. `test_rehearsal_never_writes_serial_memory` parses the
  module's **AST** (not its text — the docstring names those things on purpose,
  to say it avoids them) and fails if `SerialThread`, `SerialEpisode`,
  `apply_story_outcome`, `generate_scene` or `evaluate_turn` is ever referenced.
* The `ScenarioBrief` the rehearsal builds carries an **empty** `story_context`.
  That is load-bearing twice: it is what keeps
  `journey_conversation.evaluate_response` on its deterministic path instead of
  delegating to `living_story.evaluate_turn`, and it is what guarantees no story
  revision is ever attached to a private situation.
* The boundary is enforced in **both** directions. No world-bible character may
  appear in a rehearsal: `mentions_fiction` reads the cast from
  `WORLD_BIBLE_PATH` (read-only) and rejects a generated scene, a character
  reply, or a debrief correction that names one. This is not hypothetical — one
  of the shared conversation module's own correction rules explains itself with
  *"Margaux still uses vous with you here"*, which has no business in a call to
  the learner's real landlord. `sanitize_correction` drops it.

## 3. What is reused rather than rebuilt

| Concern | Reused | Note |
|---|---|---|
| Content contracts | `ScenarioBrief`, `ResponseTask`, `BAND_LIMITS`, `learner_level_band` from `journey_content` | imported, never edited |
| Scene validation | the *rules*, not the function | see below |
| Conversation | `journey_conversation.evaluate_response`, `reply_source` | one call per turn |
| Evidence | `journey_learning.classify_evidence`, `fold_for_comparison` | one rubric, not a second |
| Cost | `PilotEventService`, the `atelier_correction_cost` pattern | one priced row per real call |
| Level | `learner_level_band(user)` | the band the scene is written at |

**Why `validate_scenario_brief` is not called.** It requires a world-bible
character id, a world-bible location id and a `CapabilityKey` scenario key. A
rehearsal has none of those *by definition* — its counterpart is a real person.
`validate_rehearsal_scene` therefore applies the same guarantees to the shape a
rehearsal has: nothing empty, `BAND_LIMITS` lengths for the setup and every
spoken line, one declared register kept in character speech, typed snake_case
ending keys, 2–4 rubric points each with recognition cues, 2–3 endings — and the
**no-spoil gate**: a useful phrase that already appears in the setup, the
objective or the opening line was never held back, so the scene is rejected.

**Why this file owns the turn bound.** `journey_conversation.normal_turns` clamps
to `MAX_RESPOND_TURNS = 2` — the daily journey's budget. WP-31 asks for 3–6. The
rehearsal therefore counts its own turns and tells the conversation module only
whether a follow-up remains (`conversation_turn_index`: `0` while turns remain,
its own last index on the final turn). Nothing in the shared module was changed.

## 4. Files

| File | What |
|---|---|
| `app/services/rehearsal.py` (new) | structuring, generation, validation, turns, debrief, cap, cost, digest line |
| `app/db/models/rehearsal.py` (new) | the `rehearsals` table |
| `alembic/versions/e48fd9624811_add_rehearsals.py` (new) | additive, one table, `down_revision = e419f24edcd7` |
| `app/api/v1/endpoints/rehearsal.py` (new) | seven routes, one envelope, French refusals |
| `app/config.py` | `ATELIER_REHEARSAL_WEEKLY_CAP` (default 2; **0 switches the feature off**) |
| `web-frontend/components/atelier-v2/rehearsal/**` (new) | `rehearsal-state.ts`, `RehearsalScreen.tsx`, `index.ts`, `rehearsal.test.js` |
| `web-frontend/pages/repetition.tsx` (new) | the av2 page |
| `web-frontend/pages/settings.tsx` | one entry link |
| `web-frontend/services/api.ts` | types + seven methods, additive |
| `tests/test_rehearsal.py`, `tests/test_rehearsal_api.py` (new) | 57 + 6 tests |

Two files outside the strict lease carry the minimum needed to make a *new*
model and a *new* router exist at all, and nothing else: `app/db/models/__init__.py`
(one import + one `__all__` entry), `app/api/v1/api.py` (one import + one
`include_router`), plus `tests/conftest.py` (the table in `create_all`/`drop_all`).

## 5. States, and what each one promises

```
declared ─prepare─▶ ready ─turn─▶ rehearsing ─turns spent / objective met─▶ rehearsed
    │                                                                          │
    └─provider fails─▶ not_prepared ─retry─▶ ready              on/after the date
                                                                               ▼
                                                                          debriefed
```

* `not_prepared` is a **real state with no scene in it**. The declaration is
  kept, the page says «Répétition non préparée» in as many words, and offers a
  retry. There is no branch anywhere that invents a scene.
* `abandoned` still counts against the week: the generation was already paid for,
  and a cap that refunded abandonment would be a cap in name only.
* The private rubric and the recognition cues **never cross the wire** while a
  rehearsal is live (`public_view` is the only serializer, and the API test
  greps the response body for them). The rubric is released once the rehearsal
  is over, when it explains the grade instead of giving it away.
* Asking for the useful phrases is **assistance**: from that point the turns are
  `produced_supported`, never `produced_independent`. The button says so before
  it is pressed.

## 6. Cost

| Event type | When | Priced |
|---|---|---|
| `rehearsal_prepare` | one call: structuring + scene, per attempt that answered | yes, from the provider's usage |
| `rehearsal_turn` | every graded turn | see below |
| `rehearsal_debrief` | the debrief itself (outcome, days after event) | no spend of its own |
| `rehearsal_debrief_correction` | the free-line correction | yes |

A failed or unusable attempt is **not** billed, and `MAX_PREPARE_ATTEMPTS = 2`
bounds the whole preparation. The weekly cap bounds the learner.

One honest gap, declared rather than papered over: the character reply inside
`evaluate_response` is produced by `journey_conversation._model_reply`, which
**does not price its own provider call** (a pre-existing gap in a file leased to
another package). The `rehearsal_turn` row therefore carries
`cost_known: false` whenever `reply_source == "model"`, in keeping with
"unknown cost is unknown, not zero". Fixing it belongs to whoever next holds
`journey_conversation.py`.

## 7. Hooks owed

None of these were applied: their files are leased to other packages. Each is
the exact diff.

### 7.1 Home entry — `components/atelier-v2/home/HomeScreen.tsx` (WP-28)

A finished rehearsal whose day has come should be surfaced once on Home. The
server already answers the question; the client only needs to read it.

```tsx
// near the other secondary entries
{rehearsalDue && (
  <Action tone="secondary" onClick={() => router.push('/repetition')}>
    Comment ça s’est passé ?
  </Action>
)}
```

with, in the same file's data load:

```ts
const { debrief_due: rehearsalDue } = await api.getRehearsalState();
```

`debrief_due` is non-null **only** when a rehearsal is finished and its declared
date has arrived, so the entry cannot appear on a day it has nothing to ask.

### 7.2 Day-before push — `app/services/serial_notifications.py`

Alongside `daily_journey_morning_copy`, and called from the same beat:

```python
REHEARSAL_READY_TITLE = "Votre répétition est prête"


def rehearsal_reminder_copy(db: Session, user: User, *, today: date) -> tuple[str, str] | None:
    """The day before the real thing. Returns ``None`` when there is nothing to say."""
    from app.db.models.rehearsal import Rehearsal

    row = db.scalar(
        select(Rehearsal).where(
            Rehearsal.user_id == user.id,
            Rehearsal.status.in_(("ready", "rehearsing")),
            Rehearsal.event_date == today + timedelta(days=1),
        )
    )
    if row is None:
        return None
    goal = _compact((row.brief or {}).get("goal_fr") or "")
    return REHEARSAL_READY_TITLE, goal or "C’est demain. Répétez-la une fois."
```

Two properties to keep: it fires only for a rehearsal that is still **unplayed**
(a learner who already rehearsed does not need reminding), and it names the
learner's own goal, never a story character.

### 7.3 Digest line — `scripts/pilot_digest.py`

`rehearsal.rehearsal_digest_line(db, since=…, until=…)` already returns the line;
the digest needs one call:

```python
from app.services.rehearsal import rehearsal_digest_line
...
print(rehearsal_digest_line(db, since=window_start, until=window_end))
```

It prints e.g.

```
Rehearsals (Répétition, n=4 debriefed): done:3, partly:1, not_yet:0 · carried out for real: 3/4 (75%)
```

and, with no debriefs in the window, says so rather than printing 0 %.

### 7.4 npm test script — `web-frontend/package.json`

```json
"test:rehearsal": "node components/atelier-v2/rehearsal/rehearsal.test.js",
```

Until it lands the suite runs, but only by hand.

## 8. Open items

1. **Capabilities do not accrue from a rehearsal yet.** The rubric is applied —
   every turn stores its `evidence_kind` and `assistance` from
   `classify_evidence` — but `journey_capabilities._capability_opportunities`
   counts an opportunity only when its `step_id` resolves to a
   `DailyJourneyStep` **and** its scenario key is one of the three
   `CapabilityKey`s. A rehearsal has neither, by design: it is a private
   situation, not one of the three certified capabilities, and manufacturing a
   `DailyJourney` row for it would pollute the funnel the pilot digest reads.
   Making rehearsal turns countable is a change to `journey_capabilities.py`
   (leased to WP-33) plus a decision nobody has made yet — *does a rehearsal of
   the learner's own landlord call evidence "arrange a meeting"?* Recorded here
   rather than answered silently.
2. **No live model call has been made.** The mechanism is tested with a fake
   provider end to end; the *quality* of a generated rehearsal scene is unproven,
   exactly as WP-25's ladder calibration is. It needs the same bounded paid run
   (US$0.10 ceiling was allotted and not spent).
3. **Voice is text-only here.** The rehearsal accepts `mode: "voice"` on the
   wire and grades it identically, but the page ships the text field only; the
   WP-27 voice control could be dropped in unchanged.
4. **Not walked on the simulator.**

## 9. Verification

* `tests/test_rehearsal.py`: **57 passed**. `tests/test_rehearsal_api.py`:
  **6 passed**. Full backend suite: **2087 passed, 1 skipped** (see the session
  note in STATUS.md about seven concurrent-edit failures in another package's
  files that pass on their own).
* `npm run type-check`, `npm run lint`, `npm run build` clean; `/repetition` is
  route 33. All twelve existing node suites plus the new one pass.
* `alembic heads` before: `e419f24edcd7`. After: one head from this package's
  chain; WP-30 landed a sibling migration off the same parent, merged at commit.
* `ruff` clean on every file touched.
