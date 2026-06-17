> ⚠️ SUPERSEDED by `ATELIER_AI_FIRST_GENERATION_PLAN.md`. The product is AI-first:
> we generate fresh per-user/per-session and check with AI self-critique, not a static
> bank or deterministic grammar gatekeeper. Kept for history only — do not implement.

# Atelier — Package C: Content Bank + Deterministic Correctness + Per-User Assembly

Follow-up to `ATELIER_EXERCISE_FIX_PLAN.md` and `ATELIER_LEARNING_LOOP_PLAN.md`.

Goal: stop gambling on a live-ish LLM call per concept. Split the system into the
three layers it actually wants to be:

1. **Build-time (shared, cached):** the strongest available model generates a *bank*
   of many tagged items per concept, offline; deterministic code checks every item.
2. **Deterministic correctness (code):** conjugation, articles-after-negation,
   si-clause agreement are generated/validated by rules, never trusted to the model.
3. **Run-time (per-user):** a session is *assembled* by selecting, ordering,
   vocab-threading and error-repairing items from the bank — no live generation on
   the hot path.

This keeps the personalization promise: two learners with the same due concept get
different items, order, vocab and repair drills. Personalization lives in selection,
not in generating each sentence live.

> Current state to replace: `AtelierExerciseGenerator.get_or_create`
> (`app/services/atelier.py` ~line 1107) caches ONE `AtelierExerciseSet`
> (`app/db/models/atelier.py` line 48) per concept; session assembly reads exactly
> that one set (`app/services/atelier.py` ~line 2191). The hardened validator and
> `_fallback_payload` from the previous package stay and get reused.

---

## Task C1 — Deterministic grammar engine (correctness lives here)

New module `app/services/grammar_engine/` with one generator/validator per grammar
profile (reuse `infer_grammar_profile` keys: `si_present_result_form`,
`article_after_negation`, `tense_aspect`, …).

Each profile exposes:
```python
def generate(spec: ItemSpec) -> GrammarItem        # build a correct item from inputs
def validate(item: GrammarItem) -> list[str]        # return [] if grammatically correct
```

- French conjugation: use a vetted library (`mlconjug3` or `verbecc`) or a curated
  table; do NOT hand-roll. This powers `fill` and `transform` (directed/repair
  rewrites) with 100% correctness and unlimited variety.
- `article_after_negation`: deterministic transform du/de la/des/un/une → de/d'.
- `si_present_result_form`: build "Si <present>, <future/imperative>" pairs from a
  verb+subject spec.

Add `validate_item(concept, item)` that composes the profile validator with the
hardened `_payload_validation_errors` checks. Both the bank builder (C3) and runtime
must call it.

Acceptance: unit tests proving each profile generates only grammatical items and
rejects known-bad ones (seed from `tests/fixtures/atelier_bad_word_banks.json`).

---

## Task C2 — Item-bank data model

New table `atelier_item_bank` (Alembic migration). Item-level granularity, not
whole-set, so assembly can mix and match.

| column | type | notes |
|---|---|---|
| id | uuid pk | |
| concept_id | fk grammar_concepts | indexed |
| mode | str | fill / word_bank / classify / transform / produce / sentence |
| payload | jsonb | one item in the existing per-mode shape |
| cefr_level | str | A1.1 … |
| sub_pattern | str | e.g. result-clause-future, du→de |
| difficulty | int | 1–5, for the ramp |
| vocab_used | jsonb (str[]) | normalized surfaces, for vocab threading |
| quality_status | str | draft / approved / rejected (default draft) |
| source | str | model name or `deterministic` |
| content_hash | str | dedupe |
| created_at | ts | |

Indexes: `(concept_id, mode, quality_status)`, `(concept_id, sub_pattern)`.

Keep `AtelierExerciseSet` but repurpose it as the **per-session materialized
snapshot** (what was assembled for one user/session) rather than the shared cache —
or drop its use entirely once assembly (C4) lands. Don't break existing rows; gate the
switch behind `settings.ATELIER_USE_ITEM_BANK` (default `False`).

Acceptance: migration applies cleanly up/down; model + repository helpers exist with
tests.

---

## Task C3 — Bank build pipeline (offline, strongest model)

`scripts/build_atelier_bank.py` — for each active concept:
- Generate a batch (target N≈30–60 approved items/concept across modes) with the
  strongest available model, varying `sub_pattern`, `difficulty`, and seeded vocab.
  Reuse the `ExerciseGenerationService` prompt contract, but request *individual
  items* with metadata rather than a full set.
- Run every item through `validate_item` (C1). Deterministic-eligible modes (`fill`,
  `transform`) can be produced by the engine directly and only sent to the model for
  natural sentence flavor.
- `quality_status='approved'` if it passes all checks; `'draft'` if uncertain
  (flag for review). Dedupe by `content_hash`.
- Idempotent, resumable, logs per-concept counts + token cost.

Optional review: a CLI `scripts/review_atelier_bank.py` to list `draft` items and
approve/reject. Defer any UI. Auto-approve items that pass deterministic validation.

Acceptance: after a run, every active concept has ≥ N approved items spanning all
recognize modes + transform + produce; the Task 0 audit reports 0 invalid items.

---

## Task C4 — Per-user assembly (personalization lives here)

New `assemble_session(user, concepts) -> SessionPayload` in `app/services/atelier.py`,
replacing the single-set fetch at ~line 2191 (behind `ATELIER_USE_ITEM_BANK`).

Per concept, pull approved bank items and:
1. **Select** — filter by the user's CEFR level; prefer `sub_pattern`s tied to the
   user's recent errors (errata); prefer items whose `vocab_used` intersects the
   user's due vocab (`select_atelier_vocabulary`).
2. **Order** — easy→hard by `difficulty`, and by mode ramp `fill → classify →
   word_bank → produce` (coordinate with `ATELIER_LEARNING_LOOP_PLAN` B2.2).
3. **Repair** — inject targeted drills generated from the user's actual errata via the
   deterministic engine (C1) + existing `_word_bank_erratum`/`_fill_erratum` copy.
4. **Thread vocab** — set `target_vocabulary` from due vocab; prefer items already
   using those words (avoids the disconnected rail).

Fall back to `_fallback_payload` only if the bank is empty for a concept.

Acceptance: two users with the same due concept but different error/vocab history
receive measurably different assembled sessions (assert in a test). No LLM call on the
session-start path (assert the LLM service is not invoked). Conjugation items are
always grammatical.

---

## Task C5 — Rollout

- Alembic migration (C2) → build bank (C3) → verify with audit → flip
  `ATELIER_USE_ITEM_BANK=True` in staging → manual QA → production.
- Keep `_generate_with_llm` + `get_or_create` as a dormant fallback path for one
  release in case assembly regresses; remove after the bank proves out.
- Wire the existing pre-warm script to build the bank instead of single sets.

---

## What stays live-LLM (correct and intended)
Evaluating the learner's **open** production/conversation answers (the free-text they
write) is inherently per-user and low-volume — keep a strong model there. Everything
on the *generation* side moves to bank + code.

## Suggested PRs
1. PR C-1: C1 grammar engine + tests.
2. PR C-2: C2 model/migration + repository.
3. PR C-3: C3 bank builder + run it offline; verify with audit.
4. PR C-4: C4 assembly behind the flag + differential-personalization tests.
5. PR C-5: rollout + cleanup.

## Definition of done
Session content is reliable (no invalid items ever served), personalized (selection +
sequencing + repair + vocab per user), and generated with zero live-LLM latency/cost
on the session hot path.
