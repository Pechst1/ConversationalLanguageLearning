# WP-38 — the last seams

[WP-37](WP-37-HOOKS.md) applied the hooks eight packages owed each other, and
did the honest thing with the four it could not apply from inside its own
lease: it wrote them out, verbatim, and said so. [WP-36](WP-36-SELF-REPAIR.md)
did the same with three of its own. Seven diffs, each one in somebody else's
file, each one the difference between a package that works and a package that
ships **dark**.

This package applies them. It adds no feature, makes no judgement of its own,
and made no model call. Where the written-out diff did not survive contact with
the file it was aimed at, the deviation is named below rather than smoothed
over.

Pinned by `tests/test_wp38_last_seams.py` (28 tests).

---

## 1. WP-34 has a surface

The largest thing left open on the 2026-09-10 cohort (WP-37 §10.2): a backend
with 82 passing tests, a component set with 17, and **no page importing any of
it**. `CrIntakeEntry`, `CrArtefactCard`, `CrArtefactTaskCard` and
`CrArtefactUnread` now render on `/missions?intake=1`.

**Why a second view of `/missions` and not a new route.** The intake *is* the
Courrier's: what a read document becomes is a Courrier task, answered in the
Courrier's composer and graded by the Courrier's corrector. A separate page
would have had to grow its own composer, or hand the learner off to `/missions`
anyway. As a view of the same route it also inherits the design rule that route
already keeps: the branches are mutually exclusive, so each one draws exactly
one 3D press — the reply in the thread, «Faire lire» in the intake.

**The expensive trap, and the guard.** `/missions` with no mission *creates*
one — a paid generation — and then rewrites the URL to it. Without a guard, a
learner who followed «Vos documents» would have bought a mission they never
asked for and still not seen the intake. `loadMission` therefore returns before
`createSeededMission` when `intakeMode` is set, and `intakeMode` is in the
callback's dependency list, which has its own assertion because a stale flag
here is the same bug wearing a cache.

Two deviations from WP-37 §2.1's sketch, both about the same rule:

* **The task card is rendered without `onStart`.** With it, the screen would
  carry two 3D presses — «Faire lire» and «Répondre» — and the second one leads
  away from the screen it is on. The task is shown; answering it is a quiet row
  to the Courrier mission the server already created (`mission_id`).
* **The way in from the Courrier is `CrIntakeLink`, an `av2-row`**, not a
  button: the same quiet row shape Home uses for its entries, so it needs no CSS
  of its own and cannot drift from them. It sits above «Courrier passé» and on
  the empty state, and the destination is one exported constant
  (`CR_INTAKE_HREF`) shared with Home.

**And now the Home entry.** WP-37 withheld «Vos documents» on purpose — a row
that opens a screen with no intake on it is a hook that lies. The screen exists,
so the row exists, still gated: on `cap.enabled && cap.remaining > 0`, read from
the server, because a row whose screen can only say "come back next week" wasted
the press. It is Home's third quiet row and Home still draws exactly one
`tone="primary"`, which is pinned in both packages' tests.

## 2. The radio transport goes through the facade

WP-32 §9.1 / WP-37 §4, applied: `useEpisodeAudio.ts` and `StoryEpisodeStep.tsx`
no longer import `apiService`. Behaviour-neutral by construction — the four
facade exports delegate to the same methods — and the point is the direction of
the dependency: the prediction check is measurement, never marking, and it now
reaches the wire through the same facade as the reader rather than through the
whole API surface. `episode-audio.test.js`'s "zero transport calls when
listen-first is off" still holds, because its stub is the module underneath.

## 3. The day-before rehearsal push is sent

WP-31 §7.2's copy has been written, tested and unsent since it landed. Its call
site is `app/tasks/notifications.py`, and the shape WP-37 sketched needed one
change to be correct.

The edition push `continue`d on its own dedupe — *"already sent today, next
learner"*. Adding the reminder after that line would have made it dead for
exactly the learners who use the app: anyone whose edition had gone out would
never hear that the real thing is tomorrow. The edition's dedupe is now a branch
rather than a `continue`, and the reminder runs beside it, with:

* **its own event type and key** — `rehearsal_reminder_sent`,
  `rehearsal-ready:{user_id}:{date}` — so it is idempotent across a beat that
  runs every few minutes, and independent of the edition in both directions;
* **no row when nothing was delivered.** A push no device accepted is not
  recorded as sent, because recording it would burn the only day it can be sent;
* **its own try/except.** A failed reminder must not cost a learner their
  edition.

`send_morning_editions` now reports `rehearsal_reminders_sent` alongside its
own counts.

## 4. `scenario_key` is the authored catalogue

The last paragraph of WP-37 §1: `journey_events`'s payload validator declared
`"scenario_key": _enum_of(*CapabilityKey)`, which since WP-37 also accepted
`"register"`. It only *accepted* more, so nothing could break — but a vocabulary
that admits a value nothing writes has stopped being a vocabulary. It validates
against `journey_content.SCENARIO_PRIORITY` now, which is what it always meant,
and the rejection is reported the way every other rejection is: by key name,
never by echoing the value.

The import is made on first use rather than at module scope, deliberately:
`journey_content` pulls the whole generation stack (the LLM service, the serial
reader) and `journey_events` is imported lazily by `pilot_events` precisely
because telemetry should stay cheap to import.

**CONTRACT-FREEZE row 16** is applied as WP-37 drafted it, with one clause added
for the above.

## 5. WP-36's three hooks

1. **`test:self-repair`** is in `package.json` and in the CI node block, next to
   `test:journey` — seventeen node suites now.
2. **A rehearsal can close the loop.** `rehearsal.py` passed a history of
   learner turns only, so a rehearsal could be prompted once — on its first
   turn, where there is nothing to recognise — and the repair could never be
   recognised, credited or corrected. The entry now carries the character's own
   reply. One deviation from §8.3's diff: the stored key is `reply_fr`, not
   `character_reply_fr` (that is the *evaluation's* field, not the record's), and
   it is empty when the line was dropped for naming a story character.
3. **Uptake is countable.** `FeedbackDecision.reason` was computed, acted on and
   thrown away, which is why WP-36's own open item 1 — *does a prompted repair
   actually beat a recast here?* — could not be answered. `ResponseEvaluation`
   carries the reason out now and `daily_journey` writes one `PilotEvent` per
   graded respond turn that had one.

   Three decisions inside that:

   * **The stamp is not inside `apply_feedback_policy`.** That function returns
     the *same object* when nothing fired, which is how "a learner with no open
     errata is scored exactly as before" is pinned rather than asserted — and
     the reasons most worth counting are the ones where nothing fired.
     `repair_not_attempted` is a learner who was asked « Pardon, un ou une
     café ? » and answered something else. `evaluate_response` stamps it
     afterwards, on both paths.
   * **`no_open_errata` writes nothing.** It is every other turn in the app; a
     row each would bury the six that mean something.
   * **The row is written after the turn's own flush, inside a SAVEPOINT.** This
     is not defensive decoration: the first version added the row before the
     flush, and `test_daily_journey_concurrency` went red — that harness builds
     its own SQLite database without `pilot_events`, and the failure surfaced on
     the flush that carries the learner's *turn*. A telemetry row that can take a
     graded turn down with it is worse than no telemetry.

   The digest line (`format_self_repair_line`) prints prompts asked, answers
   received and the repair rate **over answers, not prompts** — a question asked
   at 23:58 is answered tomorrow, so a rate against the day's prompts would be
   arithmetic on two different populations. A window with no answers prints no
   percentage at all, and an ignored prompt is named rather than folded into
   "failed". Unlike the rehearsal and intake lines it *is* filterable by
   `--user-id`, because every row carries its learner.

## 6. Verification

```
TZ=UTC .venv/bin/python -m pytest tests/test_wp38_last_seams.py   # 28 passed
TZ=UTC .venv/bin/python -m pytest        # 2375 passed, 1 skipped, 1 warning
.venv/bin/ruff check app tests scripts   # All checks passed!
cd web-frontend && npm run type-check && npm run lint && npm run build   # clean, 37 routes
```

All seventeen node suites pass, including the newly wired `test:self-repair`.

**US$0.00 — no model call was made by this package**, and none of what it
applied can make one: a mount, four import lines, a push string, one validator,
one history key, one telemetry row and a report line.

## 7. Open items

1. **Nothing here has been walked.** No browser, no simulator. The intake
   screen in particular has never been *used*: the components were pinned by
   render assertions before this package and by source scans in it, and a real
   document has never been pasted into the real form. That is the first thing a
   pilot day should do.
2. **The self-repair numbers are a mechanism, not a result.** The rows will be
   written from today; whether a prompted repair beats a recast *here* still
   needs a pilot week of them (WP-36 §9.1).
3. **The intake screen's own empty state is thin.** One French sentence. It
   deserves the treatment the other empty states got once someone has seen it.
4. **`format_self_repair_line` counts a learner's prompts, not their scenes.**
   Two prompts in one day could be one learner twice or two learners once; the
   line does not distinguish, and the first pilot week will say whether that
   matters.
5. One prerendering error on `/placement` appeared in a single `npm run build`
   and did not reproduce in two consecutive clean runs (both exit 0, 37 routes).
   It is not a page this package touched; it is recorded here rather than
   forgotten.
