# WP-33 — Register and pragmatics as a graded dimension

Package spec: [INNOVATION-WORK-PACKAGES-2026-09-10.md](INNOVATION-WORK-PACKAGES-2026-09-10.md) §3.
Evidence: instruction beats exposure for L2 pragmatics, and **explicit
meta-pragmatic** instruction has the larger effect (Taguchi 2015; the 2022
meta-analysis). The consequence the spec draws: pragmatic adequacy is *graded
and explained* — "vous, parce que…" — not merely reacted to in character.

## 1. What shipped

| Spec item | Where | State |
|---|---|---|
| 1. Deterministic detectors, LLM only for the gap, honest "non évalué" | NEW `app/services/pragmatics.py` | done |
| 2. `register` capability dimension, one rubric | `app/services/journey_capabilities.py` | done; **one line owed** on the wire contract (§4) |
| 3. Explicit meta-pragmatic line, fr/en/de, one relevant correction | `app/services/journey_conversation.py`, `learner_copy.py`, `journey-copy.ts` | done |
| 4. Every authored scenario declares the counterpart's register | `app/data/journey_scenarios/**` + test | done |
| Owner: no pronunciation or accent judgement anywhere | source scan | done |
| Owner: Lila's coarse register stripped below B1 | already landed in WP-17 | re-pinned, not re-implemented (§5) |

## 2. The detectors (`app/services/pragmatics.py`)

Pure, provider-free, importable without the ORM.

* `address_register(text)` — `"tu"`, `"vous"`, or `None`. `None` covers both
  silences: a text with no address marker (« un café ») and one with both.
* `counterpart_register(lines)` — the register the *counterpart* uses, from the
  counterpart's own lines. Lines that disagree return `None`; there is no
  majority vote.
* `politeness_markers(text)` — greeting, thanks, please, conditional softener,
  apology, closing.
* `bare_request_finding(text, level_band=…)` — an imperative used as a request,
  or a blunt `je veux`, **at A1/A2 only**. Above that band a learner may be
  choosing bluntness, and a detector that cannot tell the difference has no
  business calling it a mistake. « je veux bien » is an acceptance, not a demand.
* `slip_span(text, expected=…)` — the span to correct and what to correct it to.

`assess_register(...)` combines them into `RegisterVerdict`:

* `SLIPPED` — the wrong address register, both registers in one turn, or a bare
  command at A1/A2;
* `RESPECTED` — the counterpart's own register, and no command;
* `NOT_EVALUATED` — no declared or demonstrated counterpart register, or a turn
  that addressed nobody. **Never rendered as a pass.**

### The one-word-repair rule

A pronoun is never swapped without its verb: « tu peux » → « vous peux » would
be a worse sentence than the learner's own. So `slip_span` prefers the swaps
that stand alone (`ton`→`votre`, `tes`→`vos`, `toi`/`te`→`vous`, `vos`→`tes`,
object `vous`→`te`), and otherwise corrects the subject **with** its verb from a
table plus the regular `-es`/`-ez` rule (stem-changing verbs — *appelles*,
*jettes*, *envoies*, *préfères* — are listed explicitly so nothing writes
« vous appellez »). `votre` carries no repair at all: it becomes *ton* or *ta*
depending on a noun this module does not analyse, and changing the gender of the
learner's noun is worse than saying nothing. Such a slip is still a slip; it
arrives as an explanation rather than a diff.

### The model

`model_register_gap(...)` is consulted **only** where `assess_register` returned
`NOT_EVALUATED` — it can never contradict a deterministic verdict. One attempt,
200 tokens, strict JSON, one priced `journey_register_assessment` pilot row per
call with the provider's own cost. Any failure — provider down, unparseable
JSON, an unknown verdict word, an extra field — returns `None`, which stays
"non évalué". Its system prompt states the pronunciation prohibition to the
model in as many words.

## 3. The meta-pragmatic line

`journey_conversation.register_corrections(...)` turns the one slip into a
`Correction` whose `note_native` is the rule **and** the reason, in the
learner's own language:

> Here it is “vous”: Margaux addresses you with vous. She runs the counter at
> Le Mistral, and a customer she barely knows stays on vous.

The reason comes from the scenario's own `counterpart_register.reason_native`;
generic keys in `learner_copy.py` (`pragmatics.*`) carry the rule when a
generated scene has no declaration.

**It does not bypass the one-correction policy.** The candidate goes through
WP-05's `select_foreground_correction` like any other. It is listed *first*, so
among corrections that are equally irrelevant to the day's targets the pragmatic
one wins — saying *tu* to Margaux costs the learner more than a missing `-s` —
while a correction on the day's own target still outranks it (pinned by
`test_a_correction_on_the_days_own_target_still_outranks_the_register_line`).

On the living-story path `evaluate_response` wraps `living_story.evaluate_turn`
and fills the correction slot **only when the actor left it empty**. That is
exactly the case the actor keeps missing: it is in character, so it answers a
*tu* with a *tu* and never notices.

Two `_CorrectionRule` entries were removed (« tu peux » → « vous pouvez »,
« te plaît » → « vous plaît »). They were English-only literals and they
double-booked the same slip. `pragmatics` is now the one owner of register.

## 4. The `register` dimension, and the one rubric

`journey_capabilities` grades it with `_summarize` — the *same* function, the
same ladder (`not_tried → with_support → independent_once → used_again_later`),
the same 24-hour/different-journey/different-date repeat arithmetic. Scoring
register a second way here would be the second rubric CONTRACTS §8 exists to
forbid.

It needs **no new column and no new writer**. The evidence is already stored:
`DailyJourneyStep.private_task["turns"]` holds the exchange, and the counterpart
register is read from the character's own lines in that same step, falling back
to the authored declaration. An opportunity counts as independent for this
dimension when it was already independent *and* the register held. One slip
anywhere in the exchange costs the turn: a scene is one conversation.

### Hooks owed

`build_register_summary(db, user=…, control_language=…)` returns the dimension
today. It joins `build_capability_summary`'s list — and therefore
`journey_events.capability_rollup` and the digest — the moment `CapabilityKey`
carries the member. `journey_capabilities` already reads
`getattr(CapabilityKey, "REGISTER", "register")`, so the hook is **one line**,
owned by the integration pass (WP-28's lease covers `schemas/daily_journey.py`):

```diff
--- a/app/services/journey_contracts.py
+++ b/app/services/journey_contracts.py
 class CapabilityKey(StrEnum):
     ORDER_AT_CAFE = "order_at_cafe"
     ARRANGE_MEETING = "arrange_meeting"
     EXPLAIN_DELAY = "explain_delay"
+    REGISTER = "register"
```

Nothing else changes: `schemas/daily_journey.py` validates against that same
enum, `_CAPABILITY_ORDER` is `tuple(CapabilityKey)` and would pick it up, and
the digest counts whatever `build_capability_summary` returns. It is held back
only because a key pydantic has never heard of turns the finish recap into a
500 — `test_the_wire_list_stays_on_the_contracted_keys_until_the_enum_carries_register`
pins that the list is safe today, and
`test_the_dimension_joins_the_summary_as_soon_as_the_contract_allows` pins that
it is correct the moment the line lands.

Two optional follow-ups, neither required by this package:

* `journey_events.capability_rollup` could print a `register` line of its own
  before the enum lands, by calling `build_register_summary`. Not done: that
  file is not in this lease and the one-line hook above makes it unnecessary.
* `living_story.py` could put the counterpart's declared register into the actor
  payload so the generated scene *states* it instead of demonstrating it. Today
  the register is read from the character's lines, which is evidence rather than
  a claim, and is correct for every scene the `mixed_address_register` guard
  admits.

## 5. The below-B1 register decision

The owner's standing guidance — strip Lila's affectionate *putain* below B1 —
**was already implemented** by WP-17 in the data path: `living_story.VULGAR_TERMS`,
`CLEAN_REGISTER_LEVELS = {A1, A2}`, `_cast_for_level` strips the bible's cast
projection, and the `vulgar_register` guard rejects any learner-facing text that
carries one at those bands (ENGINE-IMPLEMENTATION.md §4). WP-33 does not own
`living_story.py`, so it re-pins the behaviour read-only rather than editing it:
`test_lilas_coarse_register_is_already_stripped_below_b1_in_the_data_path`, plus
a scan proving the authored scenarios carry no coarse register at any band.

## 6. Verification

* `tests/test_pragmatics_register.py` — **52 passed**.
* Backend suite with the concurrently-edited packages' own suites excluded
  (WP-30 journal, WP-31 rehearsal): **1973 passed, 1 skipped**.
* `ruff check` clean on every file in the lease.
* `npm run type-check`, `npm run lint`, and all twelve node suites pass;
  `test:journey` gained the register-copy and no-pronunciation assertions.
* **US$0.00 spent — no live model call was made.** `model_register_gap` is
  proven by mechanism (provider absent, unparseable answer, `unclear`, and a
  real verdict), not by calibration. Like WP-25's ladder, its *behaviour* is
  proven and its *judgement* is not.

## 7. Open items

1. **The model half is uncalibrated.** It fires only where the detectors see
   nothing, which with authored scenarios is rare — so the first thing a bounded
   paid run should measure is how often it fires at all, and whether
   `too_formal` is ever right (a learner over-vouvoying Lila is a real slip; a
   learner over-vouvoying a stranger is not).
2. **Politeness findings are advisory and currently unshown.** `missing_greeting`,
   `missing_politeness` and `missing_closing` are detected and returned but never
   become corrections — only slips do. Surfacing them needs a place to put a
   second, softer line, which is WP-36's feedback-policy territory.
3. **`missing_closing` has no caller.** `assess_register(is_closing_turn=True)`
   exists; nothing yet knows which turn ends the scene.
4. **No frontend surface renders the dimension.** The copy keys
   (`capability_register`, `capability_state_not_evaluated`,
   `correction_register`) are in `journey-copy.ts`; `HomeScreen.tsx`,
   `pages/atelier.tsx` and `useDailyJourney.ts` are WP-28's lease, so nothing
   displays it yet. After the enum line lands it renders through the existing
   capability list with no further frontend work.
