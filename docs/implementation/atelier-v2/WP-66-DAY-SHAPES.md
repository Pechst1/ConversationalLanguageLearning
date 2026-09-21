# WP-66 — Des journées qui ne se ressemblent pas

Status: landed, 2026-09-21. Owns `app/services/journey_*.py`,
`web-frontend/components/atelier-v2/journey/*`.

The finding this package answers (WORK-PACKAGES-2026-09-21 §1): *day 1 = day 10 =
day 40*. One hard-validated template (`journey_contracts.py:411-421`), three
recall formats in the daily loop while eight richer ones sat unused in the
off-day Séance, and a register dimension graded on every respond turn since
WP-33 and shown nowhere.

---

## 1. What landed

### Day shapes, validated as a set

`DayShape` (`journey_contracts.py`) names five kinds of day. The single template
is gone: `PlannedJourney.validate()` now checks the shared invariants (opens on
the scene, ends on the ending, exactly one respond, ≤ 2 recall, stable ordinals,
inside the budget) and then the per-shape bounds from `DAY_SHAPE_RULES`.

| Shape | Steps | Recall | What makes it that day |
|---|---|---|---|
| `standard` | 3–5 | 0–2 | The shape every plan had before this package. |
| `letter` | 3–5 | 0–2 | The respond step is a Courrier letter (§4). |
| `listening` | 3–5 | **1**–2 | Scene heard first; recall restricted to `DICTATION_RECALL_FORMATS` — never a multiple choice, which cannot be taken down by ear. |
| `reprise` | **4**–5 | **1**–2 | Errata-led, dealt at a chapter's resolution beat; the ending carries the chapter recap. |
| `short` | **3** | **0** | Offered after a missed day: coming back costs a scene and a reply. |

**The dice** live in the new `app/services/journey_day_shapes.py` — seeded,
never random, never a fixed rotation:

- seed = `sha256(DAY_SHAPE_DICE_VERSION : user_id : iso_week : …)`, so the same
  learner refreshing the same day gets the same day, and two learners on the
  same day get different days;
- a missed day deals `short` and a chapter's resolution beat deals `reprise`,
  both *before* the dice are consulted — the story leads;
- neither is dealt twice running;
- otherwise a weighted draw (`SHAPE_WEIGHTS`) over the *eligible* set with
  yesterday's shape removed. A shape is eligible only when the thing it is made
  of exists: no audio → no listening day, nothing due → no reprise, no letter →
  no letter day. Offering a shape the deployment cannot fill would be the
  phantom-loop mistake.

`daily_journey.py` decides the shape at plan time from facts already in hand
(`_day_shape_inputs`): yesterday's shape, whether yesterday happened, the
story's beat, `ATELIER_EPISODE_AUDIO_ENABLED`, the errata queue length, and the
letter seam. No provider call, no second content source. A failure anywhere in
there costs the *variation*, never the day.

### Three Séance formats in the daily loop

`RecallFormat` now has six members. The three additions are built from the same
authored affordances and the same target, with **no model call** and **no new
field on `RecallTask`**:

- **`word_bank`** — tiles plus at least one plausible chip drawn from the
  scene's own affordances that is *not* part of the answer. Without a spare
  chip the chip row is the answer written down in the wrong order and counting
  solves it, so the builder returns `None` rather than pose it.
- **`classify`** — two contrastive labels, from one of two sources read off the
  target itself: **gender** for a noun stored with its article (the article
  settles the answer, so the article is exactly what the prompt withholds; a
  noun behind `l'` settles nothing and gets no classify), or **address** for a
  phrase that unambiguously says `tu` or `vous`.
- **`transform`** — a directed rewrite into the opposite form of address,
  computed by the same deterministic detectors that grade register live
  (`pragmatics.slip_span`), so the exercise and its grader cannot disagree.

**Rotation** is by target type first (`FORMAT_BIAS`: a mistake is posed as the
rewrite that repairs it, a concept as the contrast that names it, a word as the
thing to build) and then by the same seeded dice. The planner walks the order
and takes the first format that can be posed honestly; the legacy preference
order is the floor beneath it, so a target never loses its step to this change.

### Register, shown

`journey_capabilities.build_journey_register_line` projects the **existing**
rubric — same `_capability_opportunities`, same `_register_verdict` — into one
French line plus the reason in the learner's language, reusing the
`capability.register_context_*` and `pragmatics.register_use_*` copy that
already existed. `_attach_register_line` writes it onto the resolution step for
both the authored and the living-story settle paths.

Example, driven through the real API in `test_journey_end_to_end.py`:

> « vous » tenu avec Margaux.
> Kept vous with Margaux.

`None` when the dimension was **not evaluated** — no counterpart register, or a
conversation that addressed nobody. That is never a pass and never a failure, so
it is no line at all. A learner whose control language is French gets the line
alone rather than the same sentence twice.

---

## 2. Contract changes (all additive)

`PLAN_CONTRACT_VERSION = 2`, new in `journey_contracts.py`, versions the *plan*
separately from the wire. `CONTRACT_VERSION` stays `1`: every wire payload gained
only optional, defaulted fields.

**Plan contract** (`journey_contracts.py`)
- `DayShape`, `DEFAULT_DAY_SHAPE`, `DayShapeRule`, `DAY_SHAPE_RULES`,
  `day_shape_rule()`, `MIN_PLANNED_STEPS`.
- `RecallFormat`, `RECALL_FORMATS`, `LEGACY_RECALL_FORMATS`,
  `DICTATION_RECALL_FORMATS`.
- `RecallTask.task_type` widened to the six formats.
- `PlannedJourney.day_shape` (default `STANDARD`) and `.shape_reason`.

**Wire** (`app/schemas/daily_journey.py`)
- `RecallPrompt.task_type` widened to the six formats.
- `ScenePrompt.listen_first: bool = False`.
- `RespondLetter` model; `RespondPrompt.letter: RespondLetter | None = None`.
- `ResolutionPrompt.chapter_recap_fr`, `.register_note_fr`,
  `.register_reason_native` — all `str | None = None`.
- `JourneySnapshot.day_shape: str = "standard"`, deliberately a free string:
  a client meeting a shape a newer server deals must render the steps it was
  sent, not refuse the day.

**Storage: no migration.** The shape and its reason live inside the existing
`plan_selection` JSON column. A row written before WP-66 has no key, which
`_stored_day_shape` reads back as `standard` — which is what it is. A shape name
this build does not know also reads back as standard rather than 500-ing the
learner's day.

**Old plans still load and still validate**, pinned three ways:
`test_a_plan_written_before_wp66_still_loads_and_still_validates` (planner),
`test_a_v1_payload_still_validates_after_the_wp66_additions` (parity, against
the untouched frozen fixtures), and
`test_a_journey_planned_before_wp66_reads_back_as_the_standard_day_it_was`
(end to end, by stripping the keys off a real row).

---

## 3. The no-spoil rule and the three gates

The atelier rule (generation prompt · structural validator · AI critic stay
aligned) applies to the journey's transforms too. The journey's half:

1. the answer may not be the sentence already printed above it;
2. the instruction quotes the source fragment to change, which is in the source
   by construction;
3. the instruction names the target *form* (`tu`/`vous`) and never the
   conjugated answer word — so a swap where the pronoun alone is the whole
   answer (« pour toi » → « pour vous ») is **refused** rather than given away.

The planner cannot import `exercise_generation` to reuse its validators: that
module reaches `unified_srs`, and `test_the_planner_imports_no_ladder_and_no_scheduler`
exists precisely to keep the scheduler out of a pure planner. So the alignment
is pinned in the test suite instead —
`test_a_journey_transform_clears_the_legacy_seance_gates` builds the real task
in **every control language** and runs it through the legacy Séance's own
`_transform_noop_errors` and `_directed_rewrite_instruction_errors`. That is
what makes the instruction templates use straight quotes in en/de: `_quoted_fragments`
reads `'…'`, `"…"` and `«…»`, and a German `„…“` would silently fail the gate.

Gender classify withholds *both* the letter hint and the native gloss, because
both spell out the article that is the answer; only the paid `solution` reveals
it. iOS smart quotes are folded by `normalize_answer_text` before every
comparison, unchanged.

---

## 4. The «jour de lettre» seam (WP-64 is in flight)

WP-64 owns `missions.py`, which this package may not touch. So the shape ships
as a contract and a planner option that is **off**, behind exactly one function:

```python
app.services.journey_day_shapes.set_letter_provider(provider)   # the whole seam
app.services.journey_day_shapes.letter_offer_for(user_id=…, local_date=…)
```

A provider is `(*, user_id: str, local_date: date) -> LetterOffer | None`.
`LetterOffer` is six flat strings — no mission model crosses the seam.

Until one is registered, `letter_offer_for` returns `None`,
`eligible_shapes()` omits `DayShape.LETTER`, and nothing else changes. When one
arrives it is a single call at wiring time. A provider that raises costs the
shape, never the day; a shape dealt against a letter that has since vanished is
downgraded to standard with `shape_reason="letter_withdrawn"` rather than
promising a letter it cannot show.

Exercised end to end with a stub in
`test_a_registered_provider_turns_the_respond_step_into_a_letter`.

---

## 5. Tests and results

Run per file (the full suite is ~35 min). All green unless noted.

| Command | Result |
|---|---|
| `pytest tests/test_journey_planner.py` | 103 passed |
| `pytest tests/test_journey_contract_parity.py` | 46 passed |
| `pytest tests/test_journey_capabilities.py` | 36 passed |
| `pytest tests/test_journey_end_to_end.py` | 53 passed |
| `pytest tests/test_daily_journey_{api,state,concurrency,fixtures,migration}.py` | passed |
| `pytest tests/test_journey_{learning,content,conversation,events,rewards,fixture_bundle,latency,story_outcomes,correction_policy,negated_intent_api}.py` | passed |
| `pytest tests/test_wp24_mistake_loop.py tests/test_wp36_self_repair.py tests/test_pragmatics_register.py tests/test_wp38_last_seams.py tests/test_wp39_qa_walk.py tests/test_frontend_av2_chrome_language.py tests/test_wp27_voice_respond.py` | passed |
| `ruff check app/ tests/…` | clean |
| `npx tsc --noEmit`, `npm run lint` | clean |
| `node components/atelier-v2/journey/journey.test.js` | passed |
| `npm run test:self-repair / test:journey-latency / test:story-model / test:atelier-ui / test:recovery / test:resume-target / test:seance / test:courrier-intake` | passed |

**The 28-day simulations.** `test_a_month_of_days_does_not_repeat_itself` asserts
≥ 4 shapes, no shape above 50 %, and never the same shape twice running;
`test_two_learners_do_not_live_the_same_month` asserts two seeds differ;
`test_a_month_of_plans_poses_at_least_five_of_the_six_formats` runs the **real
planner** for 28 days over a mixed queue and asserts ≥ 4 shapes, ≥ 5 formats and
none above 50 %. Observed distributions:

```
learner A  standard 10 · listening 8 · reprise 7 · short 3
learner B  standard  9 · listening 7 · reprise 7 · short 3 · letter 2
```

(Learner A drew no letter day in that month even though letters were on offer —
which is the point: the dice, not a rotation.)

Not run: the full suite, and anything that spends money. No live provider calls
were made.

---

## 6. Deviations and open points

1. **`journey_learning.py` touched** (2 lines, outside the owned list, not on
   the forbidden list). `evaluate_recall` now grades `classify` through the
   choice branch and `word_bank` through the tiles branch. Without it the two
   formats would post answers nothing could grade, which is not a format anybody
   may be asked. `transform` needed nothing: it falls through to open production,
   which is what it is.
2. **`app/schemas/daily_journey.py` touched** — unavoidable for the wire
   contract, and additive only.
3. **A flush before the register line.** `_attach_register_line` calls
   `self.db.flush()` first: the turn that decides the verdict is still pending in
   the transaction, and reading the exchange without the last thing the learner
   said graded half a conversation (found while driving the real API).
4. **The transform is register-only for now.** It fires on a due phrase that
   unambiguously tutoies or vouvoies. An erratum keeps its existing repair form
   (`tiles`/`short_answer`) because naming a target form for an arbitrary
   mistake would either print the answer or be too vague to pass the Séance's
   own gate. A richer transform wants the erratum's grammar concept on the
   candidate metadata — a WP-67/WP-24 follow-up, not a WP-66 one.
5. **Non-repeat is a guarantee only when an alternative is eligible.** A
   deployment with no audio, an empty errata queue and no Courrier has exactly
   one eligible shape, and the honest answer is a second standard day. The
   decision records it as `reason="seeded_dice_no_alternative"` rather than
   pretending.
6. **The «jour de lettre» chrome is minimal**: the letter block, the
   correspondent's name and the objective. Correspondent threads, chain progress
   («2ᵉ lettre sur 3») and soft expiry are WP-65's surface, and this package
   does not pre-empt them.
7. **Pre-existing failure, not from this package**:
   `tests/test_wp37_hooks.py::test_the_rehearsal_entry_is_gated_on_the_servers_own_answer`
   fails against `web-frontend/pages/atelier.tsx` as changed by commit c65e26d
   (WP-67). That file is untouched here.
