# WP-30 — The learner writes the recap («Le journal de bord»)

2026-09-10. Spec: [INNOVATION-WORK-PACKAGES-2026-09-10.md](INNOVATION-WORK-PACKAGES-2026-09-10.md) §3 WP-30.

Every recap in the app was written *for* the learner. The evidence says that is
the weakest of the three retrieval formats — free recall beats cued recall beats
recognition — and, more sharply, that retrieval practice buys **nothing at all**
over plain restudy unless corrective feedback follows. So the package is both
halves or neither: the learner writes two to four sentences from memory about
yesterday's scene, with the scene text hidden, and what they wrote is corrected.

| | Before | After |
|---|---|---|
| **(a)** | The recap was generated: `JourneyRecap` told the learner what they had just done | The learner writes it, unaided, a day later, and *then* reads the scene back |
| **(b)** | Nothing measured whether a scene was remembered at all | Content recall is scored against the scene's stored facts, in its own column, separately from grammar |
| **(c)** | Retention evidence came only from the journey's own respond turns | A +7-day one-line follow-up produces a `used_again_later` signal about a scene, not about a sitting |
| **(d)** | — | Every grammar error in the writing enters WP-24's `open → repairing → mastered` loop, and due words the recap used earn ordinary SRS credit |

## 1. The five properties, and where each one lives

**The scene is not on screen while they write.** This is the package; everything
else is a design decision that could be revisited. Two objects, never one:
`JournalCueView` (character, place, `days_ago`) and `JournalRevealView`
(`title_fr`, `setup_fr`, `character_line_fr`, `callback_fr`). The router
attaches the reveal only on the branch where `entry_text` exists. Three tests
hold it: a behavioural one that asserts the *values* are absent from the HTTP
body before submission and present after, a schema one that asserts the *shape*
cannot hold them (a `setup_fr` added to the cue model would pass every runtime
check until someone populated it), and a source scan of the component.

**Two scores, never one.** `journal_entries.correction` holds what the Séance
corrector said about the French; `journal_entries.content_recall` holds what
`score_content_recall` said about the content. Merging them would let flawless
French about the wrong evening read as a pass — the test
`test_grammar_and_content_are_two_columns_not_one_score` is exactly that case.
Content recall is deterministic on purpose: paying a model to decide whether
"le livre" is the promised book would make the one honest number in the package
depend on a provider being up.

**One correction in the foreground.** Through the journey's own
`select_foreground_correction`, so the journal cannot become a second, louder
corrector with its own opinions about French. The full list ships in the same
payload and the client shows it behind «Tout voir», so a stored *strict*
correction preference is never silently reduced to one line.

**Failure is a state, not a verdict.** `assessment_status = "unavailable"` when
the provider does not answer, or when the scene offers no grammar concept for
the paid checker to anchor on. The learner's text is kept, no erratum is
invented, no vocabulary is credited, and the screen says so in French:
« La correction n'a pas pu être faite. Votre texte est gardé tel quel. » The
content half does not depend on a provider and still answers.

**The story is read, never written.** Facts come from `journey.scenario_snapshot`,
`journey.recap_snapshot`, the scene step's `public_prompt`, and
`living_story.story_context()` — a pure read. `private_task` is never touched
(source-scanned): the rubric and the accepted answers are evaluator material,
and scoring a recap against them would be grading the learner's memory of a
hidden document.

## 2. The schedule

`RECALL_OFFSET_DAYS = 1`, `FOLLOWUP_OFFSET_DAYS = 7`. Both dates are **stored**
on the row (`offered_on`, `followup_due_on`) rather than recomputed, so a
learner who opens the app at 23:58 and answers at 00:02 is asked about the scene
they were offered.

* `RECALL_WINDOW_DAYS = 14` — the offer will not reach further back than that. A
  learner returning after a fortnight is asked about a scene they can plausibly
  still recall, not about the last one that happens to have no entry.
* One entry per `(user, journey)`, enforced by a unique constraint. `skipped` is
  terminal, so the offer is made once.
* An empty journal is an empty journal. Nothing is invented to fill the tab.

## 3. What the correction feeds

* **Errata.** Each grammar error becomes a WP-24 erratum through
  `ErrorMemoryService.record_erratum(source_type="journal")`, so journal mistakes
  reach tomorrow's scene through `journey_errata` exactly like Séance mistakes.
  `task_compliance` and `length_compliance` notes are dropped: a note about the
  brief is not a mistake in French.
* **Vocabulary.** Due words the recap used earn credit through
  `VocabularyCreditService` at the unassisted `produced_correct` rate — free
  recall with no text on screen is the strongest production evidence the app
  collects. A word the correction flagged is *not* credited: it was used and
  used wrongly, and the erratum already says so.
* Both are gated on `assessment_status == "checked"`. An uncertified sentence
  must not move a schedule in either direction.

Cue matching folds accents, case and iOS smart quotes (`fold_for_comparison`),
and tolerates French suffixal inflection (`cue_matches`: equal, or a prefix
within three characters and at least four long) so a learner who writes
*rapporté* gets credit for the cue *rapporter*.

## 4. The character's line

Authored, not generated, and this is a deliberate trade written down rather than
hidden: a second paid call for one sentence would double the package's per-entry
cost and add a second failure mode to a line that has exactly three things to
say. What it says is real — it names the commitment the learner remembered, or
the fact they missed — and it never praises a recap that recalled nothing. With
no facts, or no character name, it says nothing at all: an empty compliment is
worse than silence. An LLM line is listed as an open item (§7), not as a gap.

## 5. Cost

One priced `journal_correction` PilotEvent per real correction call, written by
`record_journal_cost` on the same policy as `atelier_correction_cost` and its
placement sibling: the provider's own usage metadata, through the caller's
transaction, never committed there, telemetry failures swallowed.

The mechanism is a one-method subclass, `_JournalCorrector`, overriding
`AtelierCorrectionService._record_correction_cost`. The correction itself — the
prompt, the schema, the no-op erratum filter, the `fallback_used` honesty rule —
stays the Séance's. That is why it is a subclass and not a copy, and why the row
carries its own event type: the digest's cost line cannot otherwise tell a
journal entry from a Séance check.

A replayed write is a no-op (`entry.status != "offered"` returns the row
untouched), so a retried request never buys a second paid correction. Pinned at
both the service and the HTTP layer.

`journal_followup` is a zero-cost row carrying the signal, the fact counts and
the interval.

**US$0.00 spent — no live model call was made.** Every test drives a fake
checker.

## 6. Migration

`alembic/versions/c7d8e9f0a1b2_add_journal_entries.py`, one new table, no column
on any existing one. `upgrade()` is idempotent (`_has_table`), `downgrade()`
drops it.

`down_revision` is `e48fd9624811` — the newest revision that was **committed**
when this landed — so committed history has exactly one head. Four innovation
packages added tables against this checkout on the same day; two of them
(`907eb914c502`, `3759e1c7098c`) were still untracked at that moment and branch
off `e48fd9624811` as well. Whoever commits last owns the merge. If both sides
are already committed when you read this, the merge is one file:

```python
revision = "<new id>"
down_revision = ("c7d8e9f0a1b2", "3759e1c7098c")  # or whatever the other head is
def upgrade() -> None: pass
def downgrade() -> None: pass
```

`journal_entries` is deliberately **not** in the shared `tests/conftest.py`
table list: several packages were adding tables to that list the same week, and
a package that owns its own DDL in its own test module cannot collide with any
of them. `tests/test_journal.py` creates it with `checkfirst=True`.

## 7. Hooks owed by other owners

Nothing outside the lease was edited. Two of these are one-line additions.

**`app/api/v1/api.py`** — the router registration (2 lines) *was* applied, since
a router nobody includes is not a deliverable:

```python
from app.api.v1.endpoints import (..., journal, ...)
api_router.include_router(journal.router)
```

**`scripts/pilot_digest.py`** (measurement owner) — the two event types are
written and nothing reads them yet. The digest already prints cost per surface
for `atelier_correction`, `transcription` and `placement_grading`; the journal
needs the same shape plus the one number that matters:

```python
from app.services.journal import JOURNAL_EVENT_TYPE, JOURNAL_FOLLOWUP_EVENT_TYPE

# cost, exactly like _placement_costs
rows = db.query(PilotEvent).filter(PilotEvent.event_type == JOURNAL_EVENT_TYPE, ...)

# and the retention line — the reason the package exists:
follow = db.query(PilotEvent).filter(
    PilotEvent.event_type == JOURNAL_FOLLOWUP_EVENT_TYPE, ...
).all()
used_again = sum(1 for row in follow if row.payload.get("signal") == "used_again_later")
print(f"Journal follow-ups (+7d): {used_again}/{len(follow)} still recalled a stored fact")
```

`used_again_later` here is the **journal's** signal about a scene. It is
deliberately *not* fed into `build_capability_summary`: that rubric reads
journey respond-turn evidence, and writing journey evidence from the journal
would be a second rubric — the exact failure CONTRACTS §8 records. The two
numbers belong side by side in the digest, named apart.

**`components/atelier-v2/home/HomeScreen.tsx` + `app/services/daily_journey.py`**
(WP-28 integration owner) — the journal has no entry point from Home. The
smallest useful one, after the day's recap:

```tsx
{/* WP-30: the day after, the learner writes it themselves. */}
<Link className="av2-row" href="/notebook?mode=journal">
  <span className="av2-label">Le journal de bord</span>
  <span>Racontez la scène d’hier, de mémoire</span>
</Link>
```

Gate it on a real offer rather than showing it every day: `GET /journal/state`
returns `status: "none"` when nothing is due, which is the condition to hide it.
Until that lands the tab is reachable from Le Cahier and from
`/notebook?mode=journal`, and nothing is dark.

**`app/services/living_story.py`** (story-engine owner) — optional quality half:
a scene whose commitment is *concrete* (a named object, a named day) is a scene
whose recall can be measured. `scene_facts_for` drops a commitment with no
content cues, so a vague promise silently produces no fact. Nothing breaks; the
entry simply scores `no_facts`.

## 8. How to verify

```bash
TZ=UTC .venv/bin/python -m pytest tests/test_journal.py tests/test_journal_api.py \
  tests/test_frontend_journal.py -q            # 58 tests
TZ=UTC .venv/bin/python -m pytest -q           # 2094 passed, 1 skipped
cd web-frontend && npm run type-check && npm run lint && npm run build
# plus the twelve node suites, all green
```

Manual walk, once a learner has a finished scene: open
`/notebook?mode=journal` the next day. The card should name the character and
the place and show no French from the scene; after «Envoyer et relire la scène»
the same screen should show the writing, one correction, a second block about
what was remembered, and the scene itself last.

## 9. Known limits

* **`journal_entries` is not in the digest yet** (§7). The `used_again_later`
  signal is written on every follow-up and read by nobody, which is the single
  largest open item: the package's own success metric is dark until that line
  lands.
* **Content recall is lexical, not semantic.** It matches folded stems against
  the fact's cues. A learner who paraphrases perfectly — *«j'ai rendu son
  bouquin»* for *«rapporter le livre»* — scores zero. The thresholds
  (`CUE_THRESHOLD_WIDTH`, `CUE_SUFFIX_TOLERANCE`, `CUE_STEM_FLOOR`) are chosen,
  not measured; WP-22's five-learner study is the first data that could move
  them. A semantic pass is the obvious upgrade and costs a model call.
* **The character's line is authored** (§4). Three shapes, not a performance.
* **A scene with no grammar concept cannot be corrected at all** and lands on
  `unavailable`. That is honest but it is also a gap: a free-recall paragraph is
  worth checking whether or not the scene taught a concept, and the Séance
  corrector's paid path requires one. Widening it means touching
  `app/services/atelier.py`, which was outside this lease.
* **No paid call was ever made.** The mechanism is proven; the *quality* of the
  correction on free-recall French is not, and needs the same kind of bounded
  paid run the journey conversation waited on.
* **No simulator walk.** Web only.
