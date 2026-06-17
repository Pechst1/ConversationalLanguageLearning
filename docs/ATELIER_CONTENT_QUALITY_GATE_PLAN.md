# Atelier — Package H: Content Quality Gate (parallel track)

Designed to run **in parallel** with the visual/reward work (E, G). It is backend +
content only — it does not touch the drill UI, `components/ui/*`, or the reward visuals,
so it won't conflict with the Claude Design / forms-and-seal stream. This is the
roadmap's #1 dependency: prove the AI-first engine produces correct, answerable
exercises before more polish rides on top.

## H1 — Verify the AI-first generation in practice (the gate)
- Run `scripts/regenerate_atelier_exercises.py` for active concepts. To bound cost,
  start with the 3 seed concepts (`FR_B1_COND_001`, `FR_B1_TENSE_001`, `FR_A2_NEG_001`),
  then widen. Log per concept: model, pass/fail, fallback-used, latency, token cost.
- Run `scripts/audit_atelier_word_banks.py` over the regenerated `atelier-v7` rows.
  **Expect 0 flagged items.** Investigate any concept that fell back to
  `source='fallback'` for a recoverable reason (capture the payload for prompt tuning).
- Manual spot-check: the negation word-bank is solvable, classify tests the de/d' rule
  (not affirmative/negative), transform names the verb to change.

Acceptance: 0 invalid word-banks after regeneration; a short report of pass/fail +
cost per concept.

## H2 — Word-bank meaning cue (live bug, observed in-app)
Problem: the word-bank prompt currently reads only "Build the full French sentence."
with scrambled chips and **no indication of which sentence to build** — the learner
cannot know the target (seen on the imparfait-vs-passé-composé drill). The earlier
Si-type-1 banks at least listed the words to use; the generic prompt is worse.

Fix: every word-bank item must carry a **meaning cue** so the target is knowable —
the target's translation in the learner's L1 (e.g. German/English) or an explicit
"Express: …" instruction. Wire it through:
- **Generation contract/prompt** (`app/services/exercise_generation.py`): require a
  `meaning_cue` (gloss/translation) field on each word_bank item; instruct the model to
  produce it.
- **Renderability/solvability guard** (`app/services/atelier.py`
  `_payload_validation_errors`): reject a word_bank item missing a non-empty
  `meaning_cue`.
- **AI self-critique** (the AI-first critique pass): check the cue actually matches the
  answer sentence.
- **Frontend** (`web-frontend/pages/atelier.tsx`): render the cue under the word-bank
  prompt — a small, isolated one-line addition (the only FE touch; keep it minimal to
  avoid conflict with the E/G work).

Acceptance: every word-bank shows what to build (a translation or explicit goal); no
"Build the full French sentence." with no target.

## H3 — Cross-mode context check
- Audit `transform` / `classify` / `produce` for the same "no context" ambiguity. Confirm
  directed-rewrite instructions **name the verb and target form** (planned in the AI-first
  package — verify it is actually enforced in the contract + critique). Add cues /
  disambiguation where missing.

Acceptance: no exercise leaves the learner guessing the intended target across any mode.

## Suggested PRs
1. PR H-1: run regeneration + audit; commit the report (ops + small log).
2. PR H-2: word-bank `meaning_cue` through contract + validator + critique + the one FE
   line.
3. PR H-3: cross-mode context/disambiguation audit + fixes.

## Definition of done
The AI-first engine is verified to produce correct, **answerable** exercises end to end:
word-banks tell the learner what to build, every mode is unambiguous, and the audit is
clean — so the visual/reward layer is decorating a solid core, not a broken one.
