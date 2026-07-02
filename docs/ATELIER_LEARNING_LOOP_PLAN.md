# Atelier — Package B: Verify the Generation Fix, then Close the Learn→Apply Loop

Follow-up to `ATELIER_EXERCISE_FIX_PLAN.md` (now implemented: hardened validation,
deterministic fallback, full-sentence word-bank contract, `gpt-4o`, generator
`atelier-v7`, starter vocab). All of that is **code-only** — the database still holds
the old `atelier-v6` payloads and nothing has been regenerated. This package (1)
proves the fix works in practice, then (2) addresses the pedagogy concern that the
correctness fix did not touch: *can a user apply the concept right after reading the
rule, and is the experience engaging/understandable?*

---

## Part 1 — Roll out & verify the generation fix (DO FIRST; gates everything else)

### B1.1 Regenerate with the new model + contract
Run the pre-warm script against all active concepts:
`python scripts/regenerate_atelier_exercises.py` (it calls
`AtelierExerciseGenerator.get_or_create` per concept; `atelier-v7` cache miss forces
fresh `gpt-4o` generation).

- Log per-concept: success / fallback-used / validation failures / latency / token cost.
- This spends OpenAI credits (one call per concept, ~dozens). Confirm with the owner
  before running broadly; you can start with the 3 seed concepts
  (`FR_B1_COND_001`, `FR_B1_TENSE_001`, `FR_A2_NEG_001`).

### B1.2 Audit the output
Run `python scripts/audit_atelier_word_banks.py` against the new `atelier-v7` rows.

Acceptance:
- **0** flagged word-banks (the negation set that produced "de bus de" is now a
  buildable full sentence, e.g. answer_tokens `["Ils","ne","prennent","pas","de","bus"]`).
- No concept fell back to `source='fallback'` for a *recoverable* reason; investigate
  any that did (a persistent fallback means `gpt-4o` still can't satisfy validation —
  capture those payloads for prompt tuning).

### B1.3 Manual QA in the app
Fresh user, start a session, walk all three concepts:
- Negation word-bank is solvable; classify tests de/d' (not affirmative/negative);
  transform names the verb to change.
- No `abaisser/abandon/abandonner` rail; vocab shown is frequency-ranked starters and
  ideally appears in the sentences.

### B1.4 Guard against silent regressions
Add a lightweight scheduled audit (Celery beat or a CI job) that runs the Task 0
audit over stored sets weekly and alerts on any flagged item. The validator blocks
new garbage at write time; this catches drift and old rows.

---

## Part 2 — Close the learn→apply loop (the unaddressed pedagogy concern)

The correctness fix made exercises *valid*; it did not make the session *teach*.
Today the rule card is collapsed (`▸ RULE CARD`), drills don't reference the rule,
and difficulty isn't scaffolded. The data already exists: `_base` builds a
`rule_panel` (`rule`, `when`, `pattern`, `check`, `examples`, `traps`) — it's just
hidden and disconnected.

### B2.1 Rule-first scaffolding (frontend: `web-frontend/pages/atelier.tsx`)
- On the **first** drill of each concept, render the rule card **expanded** by
  default (it's `payload.rule_panel`); collapse it again on subsequent drills of the
  same concept. Persist the collapsed/expanded choice per concept in session state.
- Add a one-line "Now try it" bridge between the rule and the first exercise so the
  rule→apply transition is explicit.

Acceptance: entering a new concept shows the rule before the first exercise without a
tap; the rule recaps `pattern` + one `example`.

### B2.2 Difficulty ramp within a concept (backend ordering)
Order the recognize round so the learner applies the rule from easiest to hardest:
`fill` (recognition) → `classify` (discrimination) → `word_bank` (production). Confirm
the round/tab order in `app/services/atelier.py` session assembly and the frontend tab
order (`A·FILL / B·WORD-BANK / C·CLASSIFY` today) match this pedagogical ramp; reorder
to `Fill → Classify → Word-bank` if product agrees.

Acceptance: first thing after the rule is the easiest recognition item, not a blank
sentence-build.

### B2.3 Feedback that points back to the rule
The post-submit slip (`_fill_erratum` / `_word_bank_erratum` / `_classify_erratum` in
`app/services/atelier.py`) returns `why` + `repair`. On an error, also surface the
relevant `rule_panel.pattern` or `check` line (pass it through in the attempt
response) so the learner re-reads the exact rule they missed, not just a generic
"does not match."

Acceptance: a wrong answer shows the targeted rule line alongside Why/Repair.

### B2.4 Make the target vocab visibly land
B1 wove target vocab into generation. Verify it actually appears: if the model
ignores the woven words, either (a) move the vocab rail off recognize drills entirely
and surface it only in the produce/output steps where it's used, or (b) add a
post-generation check that ≥1 target word appears in the produce example, else
regenerate. Prefer (a) if weaving proves unreliable.

Acceptance: the learner never sees a vocab rail disconnected from the task.

---

## Out of scope (backlog, note but don't build here)
- Per-user *content* personalization beyond errata (base sets are still shared).
- Serial/Feuilleton functional pass (separate package).
- StatusBar plugin for native (separate native-polish package).

## Suggested PRs
1. PR B-1: run rollout (B1.1–B1.3) + add the scheduled audit (B1.4). Mostly ops + a
   small CI/beat job; verifies the prior package in production.
2. PR B-2: rule-first scaffolding + difficulty ramp (B2.1, B2.2).
3. PR B-3: rule-linked feedback + vocab landing (B2.3, B2.4).

## Definition of done
A first-time user opens a concept, reads the rule, immediately applies it on an easy
item, ramps to producing a full sentence, and on any mistake is shown the exact rule
line — with valid exercises throughout and no decontextualized vocab.
