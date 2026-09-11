# WP-36 — Characters prompt self-repair

Package spec: [INNOVATION-WORK-PACKAGES-2026-09-10.md](INNOVATION-WORK-PACKAGES-2026-09-10.md) §3 WP-36.
Evidence: explicit correction produced uptake in **50 %** of cases against **31 %**
for a recast (Lyster & Ranta 1997), and *output-pushing* prompts beat
input-providing feedback for accuracy (Lyster & Saito 2010; Li 2010; Brown 2016).
The consequence the spec draws, and the one this package implements: the
character does not merely recast. It **prompts the repair first**, and corrects
explicitly only when the repair fails.

## 1. What shipped

| Spec item | Where | State |
|---|---|---|
| 1. Recurrence → elicitation → repair credits / failure corrects explicitly | `journey_conversation.py` (new feedback-policy section) | done |
| 2. Bounded: one prompt per scene, never unexplained, never on the last turn | same | done |
| 3. A recurring mastered erratum reaches the same path and re-opens per WP-24 | same | done |
| Extra: WP-33's `missing_greeting`/`politeness`/`closing` surfaced in character | same | done, with one deliberate bound (§4) |
| Extra: `is_closing_turn` finally has a caller (WP-33 §7.3) | `is_closing_turn()` → `register_corrections()` → `assess_register()` | done |
| Extra: the actor's turn plan; the elicitation on the prompt side | `living_story.py` (`_turn_payload`, `ACTOR`, `evaluate_turn`) | done |
| Extra: WP-34's learner-sourced words count as coverage targets | `living_story.coverage_targets` | done |
| Copy in en/de/fr | `learner_copy.py`, `journey-copy.ts` | done |

## 2. The loop

```
learner turn ──► feedback_decision(…)  (pure, provider-free, no writes)
                    │
   recurrence of an │ explained erratum, a turn remains, none asked yet
                    ▼
        « Pardon, un ou une café ? »         ← appended to the character's reply,
        needs_repair = True, no correction,     never replacing it
        no consequence
                    │
     next turn ─────┼──► correct form, wrong form gone  → review_error(3, repaired)
                    └──► wrong form again              → explicit correction
                         (nothing at all → no uptake: no credit, no correction)
```

Three decisions inside that chain had a cheaper wrong answer:

* **The question is deterministic; the reply is not.** The elicitation is
  computed from the erratum and the scene's register and **appended** to
  whatever the character said. Generating it would have cost a second call and
  would have let a model decide whether to ask at all — and the one thing the
  evidence is clear about is that the prompt has to happen.
* **The decision is taken before the paid turn.** It is a pure function of the
  learner's text and their stored errata, so the living-story path can hand the
  actor a *turn plan* (§3) and still not depend on it.
* **A prompt turn shows no correction.** A question and its answer in the same
  breath is a recast wearing a question mark, which is the 31 % arm of the
  study.

### The question

`self_repair_question(wrong_fr=…, corrected_fr=…, register=…)`:

* a **one-word** difference becomes a forced choice — « Pardon, un ou une
  café ? » — with the two options ordered **alphabetically**, never
  correct-first, so the shape of the question can never leak the answer;
* anything wider becomes a request to say it again, in the counterpart's own
  register (« Pardon ? Vous pouvez le redire autrement ? »). An alternative
  question listing two whole clauses would be a reading exercise.

### Recognition, and the once-per-scene bound

Nothing is smuggled into the transcript: a marker inside a learner-facing line
is a marker a learner can read. Both halves are **recomputed**:

* *was this turn a repair?* — regenerate the question for each erratum and test
  it against the immediately preceding character line;
* *have we already asked?* — any earlier character line that opens with
  « Pardon… » or carries a pragmatic nudge counts. Deliberately broad: the error
  that costs the learner is a *second* interrogation, not a missed one.

### What is written, and what is not

Exactly one write, through WP-24's own API:
`ErrorMemoryService.review_error(rating=3, repaired=True)` — the pair
`journey_learning.ERROR_EVIDENCE_REVIEW` gives `PRODUCED_SUPPORTED`, because a
prompted form was **not** produced alone. WP-24's "distinct days" rule makes the
call safe to repeat: a replayed turn re-schedules the row and cannot advance the
mastery streak twice in one sitting.

A **failed** repair writes nothing here. It emits a correction, and WP-05's
existing one-punishment-per-turn pipeline records the recurrence exactly as it
records every other correction — which is also what re-opens a *mastered*
erratum ("a recurrence destroys the evidence", WP-24 §1). Writing the reopen
here as well would have booked the same mistake twice.

## 3. The living story

`evaluate_turn(…, self_repair=…)`. The actor payload gains `turn_plan`:

```json
"turn_plan": {"closing_turn": false, "clarify_form_fr": "Pardon, un ou une homme ?"}
```

and the ACTOR prompt gains one clause: when `clarify_form_fr` is set the scene
does not end — `needs_clarification` true, no correction, no ending — and the
model may neither ask the question itself nor say which form is right.
`VERSION` is **not** bumped: an additive prompt clause, the same call WP-28 made
for the director's errata, and bumping it would re-date every episode of every
learner.

The plan is a courtesy to the model's own coherence, never the mechanism:
`evaluate_turn` forces `needs_repair` and the caller appends the question, so an
actor that ignores the plan costs the scene its tidiness and not its pedagogy
(pinned by a fake actor that answers with a full closing turn).

**WP-28's rule is re-pinned, not weakened.** `"errata" not in ACTOR` still holds.
The actor is never told what the learner is *expected* to get wrong; it is told
that a question is being put about a wording the learner has *already written in
this very sentence*, which the actor can read for itself.

## 4. WP-33's advisory findings

`missing_greeting` / `missing_politeness` / `missing_closing` were detected and
never shown: they are not slips, so they never became corrections (WP-33 §7.2).
They are **elicitations** now — the character asks for the move rather than the
app explaining it — under four bounds:

1. only when the register itself held (`RESPECTED`) and no correction was
   foregrounded: one thing at a time;
2. a recurrence always outranks them;
3. the softener nudge only at **A1/A2** — above that a direct question is a
   style, and a detector cannot tell the difference;
4. **only the closing move may cost a turn the scene had not planned to spend.**
   The greeting and softener nudges ride along on a turn that was continuing
   anyway. A learner who ordered their coffee in one polite sentence without
   « bonjour » is still told — but not by having the ending they earned held
   back. The closing nudge is the exception because there is, by definition, no
   later turn for it to ride on, and even it leaves the consequence alone: only
   a self-repair prompt leaves a scene genuinely unresolved.

`missing_closing` needed something to know which turn was the last one.
`is_closing_turn(task, turn_index=…, outcome=…)` is that caller: the budget is
spent, or the objective is met and nothing is left to ask for.

## 5. Bounds, stated as rules

| Rule | How it is enforced |
|---|---|
| At most one prompt per scene | recomputed from the character's own prior lines |
| Never on the last turn | `remaining_turns(task, turn_index) > 0` |
| Never for a mistake the learner has never seen explained | `_erratum_is_explained`: a stored explanation **and** either a reviewed repair card, a foreground journey correction, or a source that shows its correction when it records it. `SILENT_ERROR_SOURCES` (`audio`, `conversation`, `pilot_capture`) scan a transcript after the fact and tell the learner nothing |
| Never an accent-only erratum | folding drops accents, so both options would read identically |
| Never a fuzzy match | `_contains_phrase` is folded run-containment, not `answer_matches` — whose 0.92 ratio makes « un homme » *be* « une homme » |
| A learner with no errata is untouched | `apply_feedback_policy` returns the **same object** |

## 6. Files

| File | Change |
|---|---|
| `app/services/journey_conversation.py` | the whole feedback-policy section; `register_corrections(is_closing_turn=…)`; both paths call the policy |
| `app/services/living_story.py` | `turn_plan` in the actor payload, one ACTOR clause, `evaluate_turn(self_repair=…)`, learner-sourced coverage targets |
| `app/services/learner_copy.py` | `self_repair.explicit_note` (en/de/fr) |
| `web-frontend/…/journey-copy.ts` | `correction_self_repair`, `self_repair_hint` (en/de/fr) |
| `tests/test_wp36_self_repair.py` | 40 tests |
| `web-frontend/…/journey-self-repair.test.js` | the new copy keys |

## 7. Verification

```bash
TZ=UTC .venv/bin/python -m pytest tests/test_wp36_self_repair.py        # 40 passed
cd web-frontend && node components/atelier-v2/journey/journey-self-repair.test.js
```

Full backend suite: **2347 passed, 1 skipped** (2026-09-11, this checkout, with
WP-37's concurrent work in the tree). `ruff`, `type-check`, `lint` and the node
suites clean. **US$0.00 — no model call was made by
this package**, on either path: the decision is deterministic and the fake actor
is the harness `tests/test_living_story.py` already ships.

## 8. Hooks owed

1. **`package.json`** (not this lease): add
   `"test:self-repair": "node components/atelier-v2/journey/journey-self-repair.test.js"`
   and put it in the CI node block next to `test:journey`.
2. **Frontend surface.** `correction_self_repair` and `self_repair_hint` are in
   the table and nothing reads them: the respond step renders one correction
   card with a fixed label, and those components are not in this lease. The
   package is fully functional without it — the question arrives as the
   character's line, which the step already renders.
3. **`rehearsal.py`** passes a history of learner turns only
   (`{"role": "learner", "text": …}`), so a rehearsal can be prompted once (on
   its first turn, where there is nothing to recognise) and the repair can never
   be recognised, credited or corrected. One line closes it — store the
   character's reply in the same history entry:
   ```python
   history=[
       {"role": "learner", "text": str(turn.get("learner_text") or ""),
        "character": str(turn.get("character_reply_fr") or "")}
       for turn in history
   ]
   ```
   (`_character_history_texts` reads `"character"` on any entry shape.)
4. **Telemetry.** `FeedbackDecision.reason` (`recurrence`, `repair_succeeded`,
   `repair_failed`, `repair_not_attempted`, `already_prompted`, `last_turn`,
   `pragmatic_move_missing`) is the number the pilot needs — *how often does a
   prompted repair succeed?* — and nothing records it. A `PilotEvent` on the
   attempt path would answer it; `daily_journey.py` is not in this lease.

## 9. Open items

1. **Uptake is unmeasured.** Whether a prompted repair actually succeeds more
   often than a recast lands, for *this* product, is the one question this
   package exists to answer and cannot answer yet: no learner has seen it. It
   needs hook 4 and a pilot week.
2. **The recurrence detector only sees what it stored.** An erratum is matched
   by its recorded wording (« une café »), so the same rule made on a different
   noun is not a recurrence. WP-24 §8's per-row/per-concept limit is the same
   limit, and folding it would be that package's work, not this one's.
3. **A prompt costs a turn.** On a two-turn scene, a learner who repeats a
   mistake on turn one spends their repair turn on the repair. That is the
   intended trade — the scene is a conversation, not a form — but it means a
   scene can end on the repair rather than on the objective, and the ending is
   then honest about it (`not_ordered` rather than a served coffee).
4. **The softener nudge can still be wrong.** « Bonjour, vous avez du café ? »
   carries no softener and is perfectly idiomatic; at A1/A2 it earns
   « Vous me demandez ça comment ? ». The band bound keeps it away from learners
   who might be choosing bluntness; whether it is right at A1 is a question for
   the first pilot day, and it is one constant (`_PRAGMATIC_BANDS`) to remove.
