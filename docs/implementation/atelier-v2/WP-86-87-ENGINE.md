# WP-86 / WP-87 — the story engine teaches words and answers fast

Owner brief (2026-09-23): the two Wave C targets the frontend could not reach — a median day
of ≥ 6 graded interactions, and the character's reply within ~2 s — may be solved in the
story engine itself, fundamentally if needed.

## Why the targets were missed (read from `app/services/living_story.py`)

**Reply speed.** One `ACTOR` call (`evaluate_turn` → `_approved(ACTOR, …, SemanticTurn)`)
returns everything at once: outcome, correction, reply, clarification, resolution, summary,
callback, commitments, chapter resolution, feeling shift, development index, secret shift.
It runs with `reasoning_effort="low"`, up to 1,600 output tokens, `json_object` mode, and the
full output JSON schema pasted into a 10–12k-token user message. Then the `CRITIC` call
re-reads the whole thing (`CRITIC_STAGES = {"SemanticTurn"}`). The learner waits for the
story's bookkeeping in order to see one line of French. Measured: reply p50 12.6 s, check
4.6 s, total ≈ 17 s.

**Practice volume.** `SceneDraft` never says which words the scene teaches, so the planner's
candidate pool is only what is already due. A new learner has almost nothing due, and the
126-day harness median is 3 graded items.

## WP-87 · La réplique d'abord (split the turn into three lanes)

| Lane | When | Output | Budget |
|---|---|---|---|
| **Tutor** | on the request, in parallel | `outcome`, correction (span / corrected / note in the learner's language), `demonstrated_target_ids`, `evidence_quotes` | small prompt (objective, targets, learner text, band; no world bible), small schema, minimal reasoning, ≤ 300 output tokens |
| **Voice** | on the request, in parallel | `reply_fr` (the character's line), `understood_intent`, `needs_clarification`, `feeling_shift` | scene + character + short recent context, minimal reasoning, ≤ 250 output tokens |
| **Story** | after the response, off the critical path (worker/thread), must finish before the resolution step renders | `resolution_fr`, `summary_native`, `callback_fr`, commitments, `chapter_resolved`, `development_index`, `secret_shift`, moods — and the **critic** reviews the whole turn here | today's budget (75 s), today's guards |

Rules:
- **Consistency.** The voice lane owns understanding: if it asks for clarification, the
  outcome is capped (`partially_met` at most) and the turn continues, whatever the tutor
  says. The tutor owns language: the correction is validated with the existing
  `Correction.is_valid_for`.
- **Deterministic guards run synchronously** on the reply before it is returned: endearment
  scrub, middle-dot / parenthetical gender scrub, tu/vous register, length, no invented
  choices, no spoiler of the objective. The LLM critic moves to the story lane. A post-hoc
  critic refusal of an already-shown reply is logged (`reply_refused_after_release`), never
  retracted, and the story lane writes bookkeeping consistent with what the learner saw.
- **Prompt-cache-friendly payloads.** Static text (system prompt, output schema, world bible,
  cast) comes first and stays byte-stable within a learner's day; per-turn data comes last.
  This applies to every engine call (OpenAI caches identical prefixes of ≥ 1,024 tokens).
- **Resolution waits honestly.** The resolution step shows a short "…" state and polls if the
  story lane is still running. If the lane fails, today's `fallback_turn` authored ending applies.
- **Streaming is not in scope** unless the measured p50 of the two parallel lanes stays
  above 4 s.
- Idempotency, revision checks, cost ledger (one row per lane), spend guard and rate limits
  are unchanged. The contract stays additive.

**Done when:** with a fake provider, verdict and reply reach the client in one response whose
server time equals max(tutor, voice), and the story lane completes before the resolution step
renders. A replay of the same mutation is byte-identical. A bounded paid measurement
(owner-consented) shows p50 verdict + reply ≤ 4 s and no loss in the accepted-day rate vs
WP-69-EVIDENCE.

## WP-86 · Le vocabulaire vient de l'histoire (scenes teach words; a floor of scene items)

- `SceneDraft.lexicon`: 3–5 entries `{surface_fr, lemma, gloss_native, part_of_speech,
  gender, line_ref}` chosen for the band. They are validated deterministically:
  - the surface appears in the scene's own text;
  - the gloss is non-empty and not a copy of the French;
  - the gender is required for nouns;
  - band fit is checked against the frequency rank of the French 5000 deck where known (a soft
    score, not a refusal).
- Accepted entries are matched to the catalogue by lemma, or created as learner-scoped rows
  that follow the WP-74 rule (no shared placeholder rows, gloss in the learner's language).
  They become `is_new` candidates with relevance 1.0 for today's warm-ups ("words you'll
  meet") and the post-reply "a word from today". They enter the Lexique once practised.
- **A floor that needs no dictionary:** when the pool is still thin, the planner derives items
  from the scene text itself:
  - unscramble a character's line (≤ 8 words);
  - «Qui a dit ça ?» (match a line to a face);
  - a cloze on a lexicon word in its scene sentence.

  Everything is local-gradable (WP-76 answer keys) and costs no extra model call.
- The day's minutes are re-priced per item (WP-78 pricing).

**Done when:** a generated scene yields 3–5 validated lexicon entries (fake provider). The
126-day harness median is ≥ 6 graded interactions within the stated minutes. Kept words
(WP-78) and lexicon words are preferred in later scenes via the director payload.

## Leases (both packages touch `living_story.py`)

- **WP-86:** `SceneDraft`, `DIRECTOR`, `_validate_scene`, `generate_scene` (lexicon parts),
  planner / journey_learning / journey_content candidate code.
- **WP-87:** `SemanticTurn` and the new lane schemas, `ACTOR`, `CRITIC` usage, `_turn_payload`,
  `_approved`, `_json_call` (prompt ordering), `evaluate_turn`, `journey_conversation.py`,
  the `daily_journey.py` attempt/resolution path, `llm_service.py`, and the frontend respond and
  resolution steps.

Codex's engine work should pause while these land, or rebase onto them.
