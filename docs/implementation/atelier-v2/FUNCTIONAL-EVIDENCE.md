# Atelier V2 — functional evidence log (integration owner)

Actual results only. Anything not executed is marked **pending**, never "should pass".

## 1. One complete café journey against the real API — PASSED

**2026-09-05.** Driver: `scripts/verify_daily_journey_cafe.py`. Real authenticated HTTP,
no mocks, no service-layer shortcuts. Backend on `127.0.0.1:8010` (port 8000 belongs to
another project and was never touched) against a **throwaway PostgreSQL 15 database**
(`atelier_v2_e2e_*`). The owner's live `language_learning` database was never migrated
or written to.

```
44/44 checks passed
```

Covered: register + login through the existing auth endpoints (no bypass); `GET /today`
declaring `contract_version 1` and creating nothing on a second GET; create with an
idempotent replay returning the **same journey id**, and the same key with a different
body returning 409 `idempotency_conflict`; a 3-step plan (scene → respond → resolution)
at 211 s against the 300 s budget, one active step, real cast (`margaux_barman` @
`le_mistral`); help recording assistance **before** returning content, surviving a
refetch; a response after a reveal reported as `assistance_level: translation`, not
`none`; a genuinely stale revision returning 409 `journey_version_conflict` with
`current_revision` + `refresh_href`; a null `current_step_id` rejected rather than
silently advanced; pause/resume preserving identical step IDs, completed work and the
current step; finish reaching `completed` with an honest recap; a duplicate finish
refused; a terminal journey re-readable without re-completing; `capabilities/progress`
resolving ahead of `/{id}`; and another account receiving a non-disclosing 404.

## 2. Learning credit actually persisted — PASSED

The first run above exercised the mechanics but **not** the learning path, because a
brand-new learner has an empty queue, so the plan carried no recall step and no targets.
That gap was found by querying the database rather than trusting the API response.

Re-run with a learner seeded with five genuinely due, scene-relevant words. Plan grew to
the full five steps at 278 s ≤ 300 s:

```
0 scene        39s
1 recall       34s  target='un café'          choice   optional=False
2 recall       33s  target="s'il vous plaît"  choice   optional=True
3 respond     120s  targets=['un café', "s'il vous plaît"]
4 resolution   52s
```

Canonical rows written, verified in PostgreSQL:

| `session_learning_moments` (`source_type='daily_journey'`) | evidence | assistance | modality | srs_credit_applied |
|---|---|---|---|---|
| journey_vocabulary | `recognized` | none | text | true |
| journey_vocabulary | `not_yet` | none | text | true |
| journey_correction | — | — | — | false |
| journey_vocabulary | `produced_independent` | none | text | true |
| journey_vocabulary | `produced_independent` | none | text | true |

SRS genuinely moved, and — critically — **only for the practiced words**:

| word | reps | state | rescheduled forward | correct | incorrect |
|---|---|---|---|---|---|
| `un café` (practiced) | 2 → 4 | reviewing | **yes** | 1 | 0 |
| `s'il vous plaît` (practiced) | 2 → 4 | reviewing | **yes** | 1 | 1 |
| `en terrasse` (omitted) | 2 | review | no | 0 | 0 |
| `je voudrais` (omitted) | 2 | review | no | 0 | 0 |
| `un thé` (omitted) | 2 | review | no | 0 | 0 |

This is the CONTRACTS §9 rule proven against a real database: **an omitted candidate
remains due and is never quietly marked reviewed.** The wrong recall left
`incorrect_count = 1` alongside the later `correct_count = 1`, so a retry did not erase
the failure. The journey's `LearningSession` closed as `completed` with 5 moments, and a
second create on the same local date returned the **same** completed journey rather than
a second one.

Recap contents were real: `objective_outcome: met`; practiced targets classified
`recognized` / `not_yet` / `produced_independent`; capability `order_at_cafe` at
`independent_once` (text); story outcome `served_at_terrace` with callback
`"un café en terrasse"` derived from what the learner actually wrote. `collectible_ids`
was empty because WP-09 is not implemented yet — an honest stub, not a fake reward.

## 3. False completion found and fixed — the café had no honest ending

**2026-09-05, found by driving the live API, not by reading tests.** A learner who
answered `"euh je sais pas"` three times was correctly graded `not_yet` with no story
outcome — and was then shown Margaux saying *"Je vous prépare ça au comptoir, avec ce que
vous avez demandé"*: serving them what they asked for, when they had ordered nothing.

**Root cause was structural.** `order_at_cafe` declared only `served_at_counter |
served_at_terrace | takeaway` — **all three are successes**. The content had no ending for
a learner who does not manage the task, so the fallback had to claim one. The earlier
`arrange_meeting` ruling had looked sufficient only because that family already happened
to carry a neutral `meeting_postponed`.

Fixes, made by the integration owner after both package owners had closed:

1. `app/data/journey_scenarios/journey-content-v1/order_at_cafe.json` — new `not_ordered`
   ending on both A1 and A2 variants: *"Pas de souci, prenez votre temps. Je suis là quand
   vous voulez."* Non-punitive, in character, with en/de/fr summaries.
2. `journey_conversation.NEUTRAL_OUTCOMES` gains `not_ordered`, so it warms no
   relationship and records no success.
3. `explain_delay`'s fallback corrected from `romy_waits_at_bar` (which implies Romy knows
   you are coming and when) to the already-honest `romy_reschedules` — *"Laisse tomber pour
   ce soir, on se voit demain."*
4. **One default was doing two jobs.** Making the fallback neutral then broke a legitimate
   case: a learner who *did* explain ("le métro est bloqué") but named no specific option
   fell to the neutral ending. Split into
   `SUCCESS_DEFAULT_OUTCOME_BY_SCENARIO` / `success_outcome_key()` (objective met, no
   specific cue) and the neutral `DEFAULT_OUTCOME_BY_SCENARIO` (nothing got across).
5. **Permanent guard**: `test_every_scenario_can_end_without_claiming_the_learner_succeeded`
   asserts every family has a non-success outcome, that the no-consequence fallback is one
   of them, and that it renders. **This guard is what caught `explain_delay`** — the café
   was found by hand, the second instance was not.

Verified live, both directions:

| learner | objective_outcome | resolution shown | story outcome |
|---|---|---|---|
| never orders | `not_yet` | `not_ordered` — "Pas de souci, prenez votre temps." | **null** |
| orders a coffee on the terrace | `met` | `served_at_terrace` — "Parfait. Un café en terrasse, ça arrive." | `served_at_terrace` |

### Also fixed: the serial memory fragment was being spoken by the character

`_settle_resolution` appended the bounded callback fact to `character_line_fr`, producing
*"Parfait. Un café en terrasse, ça arrive. un café en terrasse"* — a duplicated lowercase
fragment in Margaux's mouth. The callback is ledger data; it reaches the learner through
the recap's `story_outcome`. Removed, and the verification driver now fails on a trailing
uncapitalised fragment. Café journey re-run: **45/45**.

## 4. PostgreSQL-only invariants — PASSED

See BASELINE.md. Partial unique index enforced; **6 concurrent connections → exactly 1
won, 5 refused**; `(user, local_date)` uniqueness; JSONB round-trip; FK cascade.

## 5. Provider-cost incident — CONTAINED

**2026-09-05.** WP-06 reported that a test fixture setting
`settings.ATELIER_LLM_ENABLED = True` globally also enabled WP-03's scenario generator.
Because `app/config.py` loads the repository `.env`, which holds a **live
`OPENAI_API_KEY`**, several of that agent's intermediate test runs very likely made
billable OpenAI calls (161–184 s per run, versus 0.43 s for the fixed hermetic suite).

Confirmed by inspection: `.env` carries a real `sk-` key and an `ELEVENLABS_API_KEY`;
`app/config.py` loads it unconditionally; `tests/conftest.py` used only
`os.environ.setdefault("ATELIER_LLM_ENABLED", "false")`, which a runtime flag flip
defeats. **The exposure predates Atelier V2** — it is a property of the test harness.

Fix (integration owner): a repository-root `conftest.py` loads before
`tests/conftest.py` — and therefore before `app.config` reads `.env` — and **overwrites**
`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `PERPLEXITY_API_KEY` and `ELEVENLABS_API_KEY`
with an obviously fake value, plus keeps the cost-bearing flags off by default.
`tests/test_provider_cost_guard.py` (8 tests) asserts no credential is visible or
live-looking, and reproduces the exact incident shape: flipping the flag alone can no
longer reach a provider. Legitimate flag-flipping tests still pass, because they patch
the client object rather than relying on a credential.

**Residual action for the owner:** review OpenAI billing for 2026-09-05 and rotate the
key in `.env` if the exposure matters. Rotation is not something an agent should do.

### Correction — the first version of this guard broke 7 tests

The guard originally also forced the cost-bearing feature flags off
(`ATELIER_LLM_ENABLED`, `ATELIER_CORRECTION_LLM_ENABLED`, …) as "belt and braces". That
was overreach by the integration owner and it broke 7 tests in `tests/test_atelier.py`
(the AI-review, critic and relecture paths), which depend on
`ATELIER_CORRECTION_LLM_ENABLED` keeping its real default of `True` while passing a fake
`llm_service`.

WP-05 reported the failures, correctly proved they were not its own, and correctly
suspected that flag — while attributing them to a different package. The decisive test
was to move `conftest.py` aside and re-run: `90 passed` without it, `7 failed` with it.

The guard is now credential-only. That is what actually prevents spend — a request with
a fake key is rejected, not billed — and it leaves every feature flag exactly as the
application and `tests/conftest.py` define them. Both properties verified after the fix:
`tests/test_atelier.py` **90 passed**, `tests/test_provider_cost_guard.py` **8 passed**.

**Lesson recorded:** a safety guard must neutralise the dangerous *capability*
(credentials), not silently change *application behaviour* the existing suite depends on.

## 6. Independent QA pass and the defects it found — 2026-09-05/06

WP-12 ran as an adversarial QA agent and returned **NO-GO** with ten defects. Its
architectural verdict held: no double credit, no cross-learner leakage, no injection
escape (4 answer-key payloads and 3 unsupported story-memory proposals all rejected), no
false success after a failure. **What was broken was what the product said.**

Four content/wiring defects were confirmed by the integration owner against the live API
and then fixed:

| | Defect | Before | After |
|---|---|---|---|
| D-1 | Two of three families unreachable | 5 fresh learners → all `order_at_cafe`; `arrange_meeting`/`explain_delay` advertised but permanently `not_tried` | Rotation over the learner's own journey history: six consecutive days cycle all three; a new learner still starts at café |
| D-2 | Wrong drink served | ordered *un thé* → graded `met` → *"Un café pour vous"*, recap *"served your coffee"* | *"Un thé pour vous, au comptoir."* / *"served your tea"*. `arrange_meeting` had the same shape (Samedi for a learner who said dimanche) and was fixed too |
| D-3 | The app's own answer failed its own objective | suggested reply copied verbatim → `partially_met` (A1) / `not_yet` (A2) | all six variants → `met`, guarded by a parametrised test over every authored variant |
| D-4 | Recall payload contained its own answer | `target.label_fr: "un café"` shipped beside the options, bypassing the assistance ledger | `label_fr: ""`; the paid `solution` reveal is the only path to the string |

Three frontend defects fixed and measured:

* **D-5** — on day one a `serial-welcome` modal made `START TODAY` unclickable
  (`elementFromPoint` returned the backdrop), could not be dismissed by Escape or backdrop
  click, and its only CTA started the **legacy** session. The welcome no longer renders
  while the journey owns Today; where it still renders it is a real dialog (close control,
  Escape, backdrop dismiss, focus trap and restore). A 434 ms flash of it was traced to the
  controller reporting an unread capability as `disabled` rather than `loading`.
  Proof is an API read: clicking the hit-tested element creates a real journey row.
* **D-6** — at 320 px with 200 % text the shell overflowed to 373 px inside a 288 px column
  (`min-width: auto` on a grid item), clipping the textarea and SEND by ~36 px with nothing
  scrollable. Now 16 → 304; zero overflowing descendants at 320/390/440/768/1280 at both
  text sizes.
* **D-7** — six controls raised from 40 px to a 44 px effective touch target, widths unchanged.

### Test-suite corrections the fixes forced (integration owner)

* `tests/test_journey_end_to_end.py` read the correct option out of `prompt.target.label_fr`
  in three places. With D-4 fixed that raised `StopIteration`, and two call sites were
  silently answering arbitrarily while still passing. `Driver` now takes a session and reads
  `private_task["recall_task"]["correct_option_id"]` — the answer key from where it actually
  lives. Any fix that keeps reading it from the prompt re-opens D-4.
* Four `xfail(strict)` defect markers became `XPASS` and were removed.
* The D-2 regression test compared `'un thé' in 'Un thé…'` case-sensitively and could never
  have passed even once fixed; now case-insensitive.
* **D-1b was kept as an honest `xfail`.** The rotation fix made it pass *incidentally* —
  its assertion was `grounded or changed`, and a different scene is not a scene grounded in
  yesterday. It now asserts grounding only, and fails: `recap.story_outcome.callback_fr` is
  stored but never read back. **"The next eligible day uses a grounded callback" remains
  unimplemented.**
* 23 frozen fixtures were refreshed so the bundle stays truthful about live payloads
  (generic pre-answer café ending, empty recall `label_fr`, the corrected A1 suggestion).
  The two fixtures depicting a learner who really ordered a coffee keep their specific text.
  A new guard asserts no recall fixture can carry its own answer again.

## Pending — not executed, not claimed

| Gate | Status |
|---|---|
| `alembic downgrade base` | **fails pre-existing** at `grammar_enhancements` (see BASELINE.md); not caused by V2 |
| Frontend `npm run build:native`, `capture:mobile`, Docker build | pending |
| Real-model content/correction quality review | pending — WP-12, needs a reviewed sample |
| Physical-device / native lifecycle checks | pending — WP-10/WP-12 |
| Learner study (5 participants) | pending — owner-run, WP-12 prepares materials |
| Claude Design visual milestones (WP-01, 07 visual, 08, 09 visual) | pending — artifact still inaccessible |
