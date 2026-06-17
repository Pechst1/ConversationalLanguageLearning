# Atelier Exercise Generation — Fix Plan

Handoff plan for a coding agent. Goal: stop the Atelier engine from generating and
serving broken/decontextualized drills. Based on an audit of the live system
(Postgres `language_learning`, model `gpt-4o-mini`, generator `atelier-v6`).

## Problem summary (evidence)

The base exercise payload for each concept is generated in **one** LLM call
(`gpt-4o-mini`) and cached in `atelier_exercise_sets`. Concept selection and the
SRS/errata inputs are fine; the failures are in **content generation + validation**.

Concrete defect (negation concept `FR_A2_NEG_001`, pulled from DB):

```jsonc
// recognize.word_bank.items[2]
{
  "prompt": "Complétez la phrase : Ils ne prennent pas ___ bus.", // fill-blank, not a word-bank
  "tokens": ["Ils","ne","prennent","pas","___","bus"],            // literal "___" chip, no "de"
  "answer_tokens": ["de","bus","de"],                             // gibberish
  "correct_answer": "de bus de"
}
```

Root causes:
1. **Schema forces padding.** `word_bank_item.answer_tokens` has `minItems: 3`
   (`app/services/atelier.py` `ATELIER_EXERCISE_RESPONSE_FORMAT`, ~line 173) and the
   system prompt says "at least 3 ordered answer_tokens"
   (`app/services/exercise_generation.py` ~line 394). When the natural answer is 1
   token (`de`), the model fabricates filler to reach 3.
2. **Validation is shallow.** `AtelierExerciseGenerator._payload_validation_errors`
   (`app/services/atelier.py` ~line 1020) only checks field presence and counts
   (`len(tokens) >= 3`). It never checks that chips can build the answer, that the
   prompt isn't a fill-blank, or that the answer demonstrates the concept. So the
   bad payload passed and was cached (source=`llm`, dated 2026-05-30) and is reused
   for every user.
3. **Weak model.** `gpt-4o-mini` honors the word-bank contract on easy concepts
   (Si type 1 is correct) but violates it on subtler ones (negation/articles). Same
   for `classify`: the negation classify asks "affirmative vs negative", which does
   not test the de/d' rule at all.
4. **Vocabulary rail is decontextualized.** `select_atelier_vocabulary`
   (`app/services/atelier.py` ~line 454) is FSRS-driven, but for a user with no
   vocab history it returns the alphabetical "new" bucket (`abaisser/abandon/
   abandonner`), shown as disconnected chips unrelated to the drill sentences.

> Sequencing warning: hardening validation (Task 1) will cause `get_or_create` to
> reject the cached bad set on next read (re-validation at `app/services/atelier.py`
> ~line 970) and regenerate. If the model/schema are not fixed first, regeneration
> can fail twice and `get_or_create` **raises** `AtelierExerciseGenerationError`,
> breaking session creation. **Do Tasks 2 + 3 before/with Task 1, and add the
> graceful fallback in Task 1.5.**

---

## Task 0 — Quantify the breakage (read-only, do first)

Write a one-off script `scripts/audit_atelier_word_banks.py` that loads every latest
`source='llm'` `AtelierExerciseSet` and flags word-bank items where:
- `prompt` contains `___`, or
- multiset(`answer_tokens`) ⊄ multiset(`tokens`), or
- `correct_answer` has a duplicated adjacent token, or
- `len(set(answer_tokens)) < len(answer_tokens)` for short answers.

Output: `{concept_id, external_id, item_id, reason}`. This both measures scope and
becomes the regression fixture for Task 1. Save the flagged set to
`tests/fixtures/atelier_bad_word_banks.json`.

Acceptance: prints a table; at minimum flags `FR_A2_NEG_001` wb1/wb2/wb3.

---

## Task 1 — Harden payload validation (the gate)

File: `app/services/atelier.py`, `AtelierExerciseGenerator._payload_validation_errors`
(~line 1020). Add semantic checks. Keep the existing count/presence checks.

Add a module-level helper:

```python
def _multiset_subset(small: list[str], big: list[str]) -> bool:
    from collections import Counter
    c_big = Counter(_normalize(t) for t in big)
    for t in small:
        key = _normalize(t)
        if c_big.get(key, 0) <= 0:
            return False
        c_big[key] -= 1
    return True
```

In the `word_bank` loop, after the existing presence/count checks, add:

```python
prompt = str(item.get("prompt") or "")
tokens = [str(t) for t in (item.get("tokens") or [])]
answer_tokens = [str(t) for t in (item.get("answer_tokens") or [])]

# 1. word-bank prompt must NOT be a fill-in-the-blank
if "___" in prompt or "___" in " ".join(tokens):
    errors.append(f"word_bank item {item_id(item)} uses a fill-in-the-blank prompt/token")

# 2. every answer token must be buildable from the offered chips
if not _multiset_subset(answer_tokens, tokens):
    errors.append(f"word_bank item {item_id(item)} answer_tokens are not a subset of tokens")

# 3. reject degenerate/duplicated answers (e.g. 'de bus de')
norm_ans = [_normalize(t) for t in answer_tokens]
if len(answer_tokens) <= 4 and len(set(norm_ans)) < len(norm_ans):
    errors.append(f"word_bank item {item_id(item)} has duplicated answer tokens")

# 4. correct_answer must equal the joined answer_tokens
if _normalize(item.get("correct_answer") or "") != _normalize(_join_french_tokens(answer_tokens)):
    errors.append(f"word_bank item {item_id(item)} correct_answer does not match answer_tokens")
```

Add a concept-demonstration check (mirror what `output_ladder` already does at
~line 1096): the word-bank `correct_answer` should contain ≥1 concept hit.

```python
if concept and count_concept_hits(concept, str(item.get("correct_answer") or ""),
                                  task_text=prompt) <= 0:
    errors.append(f"word_bank item {item_id(item)} answer does not demonstrate target concept")
```

For `classify`, add: the labels must be concept-relevant, not generic polarity.
Reject if `set(normalized labels) == {"affirmative","negative"}` (or other generic
sentiment) — those don't test grammar. Prefer a per-concept allowed-label set from
the grammar profile (`infer_grammar_profile(concept)`).

Acceptance:
- `_payload_validation_errors` returns ≥1 error for the `FR_A2_NEG_001` cached
  payload (load it from the Task 0 fixture).
- Still returns `[]` for the `FR_B1_COND_001` (Si type 1) cached payload.
- Unit tests in `tests/services/test_atelier_validation.py` covering: blank-in-prompt,
  non-subset tokens, duplicated answer, mismatched correct_answer, generic classify
  labels, and a known-good payload.

---

## Task 1.5 — Graceful fallback (prevents the "can't start session" regression)

File: `app/services/atelier.py`, `get_or_create` (~line 959) and/or
`_generate_with_llm` (~line 1112).

Today, if generation yields nothing valid, `get_or_create` raises
`AtelierExerciseGenerationError` (line 975), which would 500 the session start once
validation is stricter. Change so a concept that cannot produce a valid payload:
- logs an error with the validation failures, and
- is **skipped** in session assembly (drop it from the session's concept list) rather
  than failing the whole session, OR
- falls back to a minimal *fill+classify-only* payload (no word_bank/transform) that
  still passes validation.

Pick the skip-and-continue option if the session can run with <3 concepts; otherwise
the reduced-payload option. Ensure the session-build endpoint
(`app/api/v1/endpoints/atelier.py`) tolerates a concept producing no set.

Acceptance: with the model temporarily forced to emit garbage (monkeypatched), a
session still starts with the remaining valid concepts and returns 200, not 500.

---

## Task 2 — Fix the schema/prompt that forces padding

File: `app/services/atelier.py` `ATELIER_EXERCISE_RESPONSE_FORMAT` (~line 166) and
`app/services/exercise_generation.py` system prompt (~line 389).

The `minItems: 3` on `answer_tokens` is correct *for a real sentence-build* word-bank
(a full French sentence is always ≥3 tokens). The bug is the model emitting a
fill-style answer. So **do not lower minItems** — instead make the contract explicit
so the model builds a full sentence:

- System prompt: replace the word-bank sentence with:
  > "Each word_bank item asks the learner to assemble ONE complete French sentence
  > from scrambled chips. `prompt` must be an instruction like 'Construis une phrase
  > avec : …' and must NOT contain a blank ('___'). `answer_tokens` is the full
  > ordered sentence (every word as a separate token). `tokens` is `answer_tokens`
  > scrambled, optionally plus 1–2 distractors. The fill-in-the-blank format belongs
  > only to the `fill` mode."
- Add to `strict_contract` in `user_payload`:
  `"word_bank_format": "full_sentence_build_no_blanks"`.
- Optionally add `"minProperties"`-style guidance isn't possible in JSON schema for
  this; rely on the prompt + Task 1 validation to enforce it.

Acceptance: regenerating `FR_A2_NEG_001` produces a full-sentence word-bank
(e.g. answer_tokens `["Ils","ne","prennent","pas","de","bus"]`) that passes Task 1.

---

## Task 3 — Invalidate + regenerate cached bad sets

Two parts:

**3a. Force invalidation.** Bump `ATELIER_GENERATOR_VERSION` (`app/services/atelier.py`
~line 37) `"atelier-v6"` → `"atelier-v7"`. `get_or_create` keys the cache on
generator_version, so all concepts regenerate on next request with the new prompt +
validation. (Hardened validation in Task 1 also rejects old sets, but the version
bump makes the cache-busting explicit and auditable.)

**3b. Offline pre-warm command** so users don't hit cold/slow generation. Add a
management script `scripts/regenerate_atelier_exercises.py` (or a Celery task) that
iterates active concepts and calls
`AtelierExerciseGenerator(db).get_or_create(concept)`, logging successes/failures.
Run it after deploy. Make it idempotent and safe to re-run.

Acceptance:
- After bump + pre-warm, `SELECT generator_version FROM atelier_exercise_sets` shows
  `atelier-v7` rows for the three seed concepts.
- The negation word-bank in the new rows passes the Task 0 audit script.

---

## Task 4 — Upgrade the generation model

File: `app/config.py` `ATELIER_EXERCISE_LLM_MODEL` (line 103, currently `gpt-4o-mini`).

`gpt-4o-mini` is the root unreliability. Move to a stronger model for this
structured pedagogical task. Two options:
- **Same provider:** raise to a stronger OpenAI model (e.g. `gpt-4o` or the current
  top reasoning model) via the env var `ATELIER_EXERCISE_LLM_MODEL`.
- **Anthropic:** if `LLMService` supports Claude (check `app/services/` for a
  provider switch), use a current Claude model — these are strong at instruction-
  following on structured JSON. If not wired, this is a larger change; defer.

Keep it env-configurable; do not hardcode. Re-run Task 3b pre-warm after switching.
Watch cost/latency: generation is one cached call per concept, so a stronger model is
affordable here.

Acceptance: with the new model + Task 1 validation, the regeneration success rate
across all active concepts is ≥95% on first attempt (log it in the pre-warm script).

---

## Task 5 — Pedagogy: classify + transform clarity

File: `app/services/exercise_generation.py` system prompt; optionally per-profile
hints from `app/core/error_concepts.py` / `infer_grammar_profile`.

- **classify must test the rule.** Add to the prompt: "`classify` labels must be the
  contrastive grammatical forms the concept teaches (e.g. présent/futur/conditionnel
  for conditionals; correct/incorrect article for negation), never generic
  affirmative/negative or true/false." Enforce via the Task 1 generic-label rejection.
- **transform instructions must name the verb.** Add: "Directed-rewrite instructions
  must name the exact word to change and the target form, e.g. 'Mets *pleuvait* au
  passé composé', not 'Change the verb to passé composé' (the source may already
  contain a passé composé verb)."

Acceptance: regenerated `FR_B1_TENSE_001` transform items name the target verb;
regenerated `FR_A2_NEG_001` classify labels are de/d'-relevant, not affirmative/
negative.

---

## Task 6 — Vocabulary relevance

Files: `app/services/atelier.py` `select_atelier_vocabulary` (~line 454),
`inject_vocabulary_context` (~line 556); `ProgressService.get_vocabulary_recommendations`.

- **New-user seeding.** When FSRS returns the raw alphabetical "new" bucket (no
  history), select a small curated A1/A2 starter set (high-frequency words) instead
  of dictionary order. Add a `is_starter`/frequency rank to vocabulary selection, or
  order the "new" bucket by a frequency column if one exists (check
  `VocabularyWord`).
- **Weave, don't decorate.** The chips at the top of recognize drills are
  disconnected. Either (a) hide the vocab rail on recognize drills and only surface
  target vocab in the produce/output_ladder steps where `inject_vocabulary_context`
  already sets `production_goal=use_target_vocabulary_in_context`, or (b) pass the 3
  target words into the generation prompt so the generated sentences actually contain
  them. Prefer (b) for cohesion: add `target_vocabulary` to `user_payload.context`
  and instruct the model to use those words in the example sentences where natural.

Acceptance: a fresh user no longer sees `abaisser/abandon/abandonner`; the displayed
target vocab either appears in the exercise sentences or is confined to the
production step.

---

## Suggested order & PRs

1. PR A (safety): Task 0 (audit) + Task 1 (validation) + Task 1.5 (fallback) + tests.
   Merge behind the existing generator version so nothing regenerates yet.
2. PR B (quality): Task 2 (schema/prompt) + Task 4 (model) + Task 5 (pedagogy).
3. PR C (rollout): Task 3 (version bump + pre-warm). Run pre-warm, verify with Task 0
   audit, then deploy.
4. PR D (vocab): Task 6.

## Test/verification checklist

- `pytest tests/services/test_atelier_validation.py` (new) green.
- Task 0 audit script reports 0 flagged word-banks after PR C.
- Manual: start a session as a fresh user; the negation word-bank is a buildable
  full sentence; classify tests the de/d' rule; transform names the verb; no
  `abaisser/abandon/abandonner` rail.
- Confirm session start returns 200 even if one concept fails generation (Task 1.5).
