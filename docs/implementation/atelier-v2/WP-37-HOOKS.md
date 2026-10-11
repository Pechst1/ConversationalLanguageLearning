# WP-37 — the hooks the 2026-09-10 packages left owed

Eight packages landed on 2026-09-10. Each stopped at the edge of its lease and
wrote the missing diff into its own handover instead of applying it, which is
the right discipline in a shared checkout and has one cost: a package can ship
**dark**. A digest helper nobody calls prints nothing. A summary the wire
contract cannot carry never reaches a learner. A screen with no entry point is a
screen nobody opens.

This package applies those diffs. It adds no feature and makes no judgement of
its own; where a hook could not be applied honestly, it is written out below
rather than half-done.

Sources: [WP-30 §7](WP-30-JOURNAL.md), [WP-31 §7](WP-31-REHEARSAL.md),
[WP-32 §9](WP-32-RADIO.md), [WP-33 "Hooks owed"](WP-33-REGISTER.md),
[WP-34](WP-34-INTAKE.md), [WP-35](WP-35-DOSSIER.md),
[WP-24 §5](WP-24-MISTAKE-LOOP.md) (already applied by
[WP-28](WP-28-INTEGRATION.md); nothing remained).

---

## 1. `CapabilityKey.REGISTER` — the one-line hook that was not one line

WP-33 wrote the hook as a single enum member, and it is:

```python
class CapabilityKey(StrEnum):
    ORDER_AT_CAFE = "order_at_cafe"
    ARRANGE_MEETING = "arrange_meeting"
    EXPLAIN_DELAY = "explain_delay"
    REGISTER = "register"          # ← the hook
```

What that line alone would have produced is a 500, for a reason WP-33 could not
see from inside its lease: **`journey_capabilities._CAPABILITY_ORDER` was
`tuple(CapabilityKey)`**. Adding the member would therefore have

* asked `read_journey_evidence` for a scenario key nothing writes,
* raised `KeyError` on `_TITLES[language][REGISTER]` — the register title comes
  from `learner_copy`, not from that table — on **every** call to
  `build_capability_summary`, i.e. the progress endpoint and the finish recap,
* and, had it survived that, printed `register` twice: once from the scenario
  loop and once from the append `_REGISTER_IS_CONTRACTED` guards.

So the enum member came with one more change: `_SCENARIO_KEYS` is now the three
scenario objectives, `_CAPABILITY_ORDER` aliases it, and `_capability_key_of`
refuses a record that somehow claims the dimension as its scenario. The
distinction is the real content of this hook and is written into the enum's own
docstring: **`register` is a dimension of a respond turn, not a fourth
capability.** It has no brief, no plan, no ending and no evidence of its own; it
is the same turns re-read, by the same `_summarize`, against the same ladder —
one rubric, which is the whole point (CONTRACTS §8).

**What it changed on the wire.** `GET /daily-journeys/capabilities/progress` and
the finish recap now carry a fourth entry, last, titled from
`capability.register_title` in the learner's language. `contract_version` stays
1: nothing existing changed meaning. The frozen fixture
`tests/fixtures/daily_journey_v1/public/unknown_legacy_assistance.json` gained
the entry and nothing else (+8 lines, 0 deletions).

**Owed to CONTRACT-FREEZE.md** (not this lease). Revision 2 wants one more row:

| # | Change | Owner | Rationale |
|---|---|---|---|
| 16 | `CapabilityKey` gains `register`, appended last; every capability list on the wire is four entries | WP-33/WP-37 | additive; a *dimension* re-read from the same respond turns by the same rubric, never a fourth scenario. `journey_capabilities._SCENARIO_KEYS` — not the enum — is the authored-scenario catalogue, and `journey_content.SCENARIO_PRIORITY` remains three |

**Six test files were re-pinned**, all for the same reason: they read
`CapabilityKey` as "the list of authored scenarios". They now read
`journey_content.SCENARIO_PRIORITY`, which is what they always meant.
`test_journey_contract_parity.py`, `test_journey_conversation.py`,
`test_journey_planner.py`, `test_journey_end_to_end.py`,
`test_journey_capabilities.py` and `test_pragmatics_register.py` — the last of
which had WP-33's two "until the enum lands" tests, now flipped to pin the
landed behaviour *and* the two failure modes above.

**Still lax, and deliberately not fixed here:**
`journey_events.py`'s event-payload validator declares
`"scenario_key": _enum_of(*[str(key) for key in CapabilityKey])`, which now also
accepts `"register"`. It only *accepts* more, so nothing breaks and nothing can
be mis-written by it — but the closed vocabulary should be
`SCENARIO_PRIORITY`. One line, in a file this lease does not hold.

---

## 2. Home: two quiet entries, no second press bar

`HomeScreen.tsx` gained one presentational prop, `entries?: HomeEntry[]`, and
renders each as an `av2-row` link — a label, one clause, an arrow. Never an
`Action`, never a `tone`: design principle 1 is one primary action per screen
(`docs/design-overhaul-2026-08-31.md`), and the red press bar is the day. A test
pins that the file still contains exactly one `tone="primary"`.

`pages/atelier.tsx` decides which entries exist:

* **«Votre répétition» → `/repetition`** (WP-31 §7.1). Gated on the server's own
  answer: `getRehearsalState().debrief_due` is non-null **only** when a rehearsal
  is finished and its declared date has arrived, so the row cannot appear on a
  day it has nothing to ask. A failed read shows no row — an entry nobody can
  open is worse than no entry.
* **«Votre dossier» → `/dossier`** (WP-35). Always present: it is the learner's
  standing answer to "what does this thing believe about me", and that is true
  every day.

An `errorOnlyPage` shows neither: a page that could not load the edition should
not be offering side doors.

### 2.1 Not done: «Vos documents» (WP-34), and why

WP-34's handover says *"Courrier's own intake button is the only way in."* It is
not. `CrIntakeEntry`, `CrArtefactCard`, `CrArtefactTaskCard` and
`crIntakeCapLine` are built, exported and covered by 17 assertions in
`components/courrier/courrier-intake.test.js` — and **no page imports any of
them**:

```
$ grep -rn 'CrIntakeEntry' web-frontend --include='*.tsx'
components/courrier/Courrier.tsx:502:export function CrIntakeEntry({
```

So a Home entry would open `/missions` and the learner would find no intake on
it. Adding the row would have been a hook that lies, which is exactly the class
of thing these packages have been refusing to do all week. The row is therefore
**not** added, and what is owed is not a Home entry but a surface:

1. `pages/missions.tsx` renders `<CrIntakeEntry cap={…} onRead={…} error={…} />`
   above the mission list, wired to `apiService.getIntakeArtefacts()`,
   `POST /intake/text` and `POST /intake/photo`, with `CrArtefactCard` /
   `CrArtefactTaskCard` for what comes back and `DELETE /intake/{id}` behind the
   card's delete control.
2. *Then* the Home entry, in `pages/atelier.tsx`'s `homeEntries`, gated on a
   non-zero `cap.remaining`:

   ```tsx
   {
     id: 'intake',
     label: 'Vos documents',
     hint: 'Un menu, une lettre : on la lit avec vous.',
     href: '/missions',
   }
   ```

Until (1) lands, WP-34 is a backend with 82 passing tests and no way in.

---

## 3. Réglages: «Écouter d'abord» (WP-32 §9.2)

One row in the Voix section, reading and writing the reader's own
`LISTEN_FIRST_KEY` through `readListenFirst` / `writeListenFirst` — the same
functions `StoryEpisodeStep` uses, so the two controls cannot disagree. It is
read in a `useEffect`, not during render: seeding state from `localStorage` while
rendering is a hydration mismatch. Default off, exactly as WP-32 argues — listen
-first is the harder way to meet a scene and the evidence assumes a learner who
chose it. What changes is that choosing no longer requires being shown the offer
inside an episode first.

---

## 4. The journey facade's radio exports (WP-32 §9.1)

`services/daily-journey.ts` now exports `getEpisodeAudio`,
`synthesizeEpisodeAudio`, `getEpisodeAudioClip` and `recordEpisodePrediction`.
They sit with the reader calls, below `dailyJourneyService`, not inside it: the
prediction check is measurement, never marking, and must stay as far from the
mutation/reward authority in code as it is in the rubric (WP-32 §3).

**Owed, and not applied:** switching `useEpisodeAudio.ts` and
`StoryEpisodeStep.tsx` off `apiService` and onto these four exports. Both files
are WP-32's lease, the change is behaviour-neutral, and it is four import lines:

```diff
-import apiService from '@/services/api';
+import { getEpisodeAudio, synthesizeEpisodeAudio, getEpisodeAudioClip } from '@/services/daily-journey';
...
-      const blob = await apiService.getEpisodeAudioClip(String(sceneId), clip.id);
+      const blob = await getEpisodeAudioClip(String(sceneId), clip.id);
```

with the same substitution for `getEpisodeAudio` / `synthesizeEpisodeAudio` in
`useEpisodeAudio.ts` and `recordEpisodePrediction` in `StoryEpisodeStep.tsx`.

---

## 5. The digest: six lines that were written and never printed

`scripts/pilot_digest.py` prints, after the WP-29 coverage line:

| Line | Owed by | What it answers |
|---|---|---|
| `format_rehearsal_line` | WP-31 §7.3 | of the rehearsals debriefed, how many the learner **actually carried out** |
| `format_intake_line` | WP-34 | documents brought in, how many were read, what it cost |
| `format_episode_audio_line` | WP-32 §9.3 | spend per listening learner **and the cache-hit rate** — the number that decides whether listening-first is affordable |
| `format_episode_prediction_line` | WP-32 §9.3 | `confirmed / other / unresolved`, as counts |
| `format_journal_lines` | WP-30 §7 | the journal's cost, and the +7-day retention signal |
| `format_register_line` | WP-33 | the register dimension's states across the day's learners |

Five properties they share, each pinned:

1. **Empty is a result.** No rehearsals, no documents, no episodes → "none" or
   "nothing to report". A test asserts no new line ever prints `0 %` on an empty
   window; a rate with no denominator is not a measurement.
2. **The prediction is never a percentage.** The guess is a two-way choice, so a
   coin flip scores 50 %. The line prints counts and says so in words.
3. **The money says it is modelled.** The speech endpoint returns audio and no
   usage block, so the synthesis line repeats WP-32's own declaration —
   *estimated from characters, not a provider bill*.
4. **The journal's two numbers are named apart.** `used_again_later` here is the
   journal's signal about a *scene*; the capability rubric's is about a respond
   turn. Folding them would be the CONTRACTS §8 failure, so the retention line
   says "not journey evidence" in the line itself.
5. **The register line costs nothing and cannot disagree.** It is read off the
   `by_capability` rollup the journey section already computed — which calls
   `build_capability_summary`, the one rubric — rather than re-scoring.

`rehearsal_digest_line` and `intake_digest_line` take no learner filter, so
under `--user-id` both lines say `cohort-wide, not filtered by --user-id`
rather than letting a reader take them for one learner's numbers.

A test asserts that every formatter this file defines is actually called from
`main()` — which is the failure this whole package exists to fix.

---

## 6. The day-before rehearsal push (WP-31 §7.2)

`serial_notifications.rehearsal_reminder_copy(db, user, today=…)` returns
`(title, message)` the day before a declared event, or `None`. Two properties,
each with tests:

* **Only an unplayed rehearsal.** `ready` and `rehearsing` — the two states with
  turns still to spend. `rehearsed` and `debriefed` are done; `declared` and
  `not_prepared` have no scene to open. A rehearsal with no resolved
  `event_date` is never reminded about, because guessing a date is how a push
  lands on the wrong day.
* **The learner's own goal, never a story character.** The message is
  `brief.goal_fr` — what *they* said they were going to do. A rehearsal is
  biography, not canon (WP-31 §2), and a source scan asserts no world-bible name
  appears in the function. With no resolved goal it falls back to
  «C'est demain. Répétez-la une fois.», which claims nothing.

**Owed, and not applied: the call site.** The morning beat is
`app/tasks/notifications.py`, which this lease does not hold, and
`_morning_copy` returns exactly one `(title, message)` per learner per day —
so this is a *second* push, not a variant of that one, and it needs its own
dedupe key. The diff, for whoever owns that file:

```python
# in send_morning_editions, after the edition push for this learner
from app.services.serial_notifications import rehearsal_reminder_copy

reminder = rehearsal_reminder_copy(db, user, today=now.date())
if reminder is not None:
    title, message = reminder
    key = f"rehearsal-ready:{user.id}:{now.date().isoformat()}"
    # …same PilotEvent dedupe check the edition push uses, then:
    NotificationService(db).send(user, title, message, key)
```

Until it lands the copy is written, tested and unsent.

---

## 7. What WP-24 §5 still owed: nothing

WP-28 applied both halves — `daily_journey` reads the errata, plans with them
and stores `plan_because`'s payload with the plan; `GET /atelier/today` serves
it; Home prints the French. The `living_story` quality half landed too (the
director is told the erratum, the actor is not). Verified by reading
[WP-28-INTEGRATION.md](WP-28-INTEGRATION.md) §1 against the source, not by
re-applying anything.

---

## 8. A pre-existing failure, fixed in passing

`tests/test_rehearsal.py::test_the_weekly_cap_is_hard_and_counts_abandoned_rehearsals`
failed from 2026-09-11 onward, on any tree. `Rehearsal.created_at` is a server
default — real wall-clock — while the window arithmetic is driven from a frozen
`NOW` of 2026-09-10, so from the morning after it was written, rows stamped
"today" still sat inside `NOW + 8 days`' window and the slot never freed. The
two rows are now stamped with the same clock the assertion uses, which makes it
a test of the seven-day window rather than of the date it is run on.

---

## 9. Verification

```bash
TZ=UTC .venv/bin/python -m pytest tests/test_wp37_hooks.py     # 31 passed
TZ=UTC .venv/bin/python -m pytest                              # see STATUS.md
cd web-frontend && npm run type-check && npm run lint && npm run build
# plus all sixteen node suites
```

**US$0.00 — no model call was made by this package**, and none of the hooks it
applied can make one: they are an enum member, six report lines, a push string,
two links and a preference row.

## 10. Open items

1. **Nothing here has been walked.** No browser, no simulator. The two Home
   entries, the Réglages row and the register line are pinned by tests and have
   never been seen by a person.
2. **WP-34 has no surface** (§2.1). This is the largest thing left open on the
   2026-09-10 cohort: a backend with 82 passing tests, a frontend component set
   with 17, and no page that renders either.
3. **The rehearsal push is unsent** (§6) and the two radio imports are unswitched
   (§4). Both are written out verbatim; both are somebody else's file.
4. **The register dimension has never been *read* by a learner either**, and its
   model half is still uncalibrated (WP-33 §7.1). What WP-37 changed is that it
   is now on the wire and in the digest, so the first pilot day can say how often
   it fires at all.
