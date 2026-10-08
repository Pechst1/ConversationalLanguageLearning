# WP-136: loss-rate confirmation read (2026-10-07)

**Setup.** The runs follow the recipe in `LOSS-RATE-2026-10-06.md` §6, on `codex/next` = `release/rc-2026-10-06` @ 2bc31f3, which contains the fixes from `exp/loss-rate`.
- Harness: `tests/test_wp133a_live_read.py`.
- Production configuration: two drafts, the critic, lanes, catalogue v2, practice day on.
- Every run was preceded by free dry runs with `WP133A_DRY_FAIL`, in `dry/` and `dry-b1/`. The recovery path and the seeded start worked.

**Spend.** US$0.666 in total (C1 0.258, B1 0.203, A1 0.206). The cap is checked before each call, so each run ends one call past its cap.

## Result

| Run | Band | Days | Generated days served | Lost |
|---|---|---|---|---|
| 1 | C1.1 | 1–10 | g1.1–g1.5, g2.1 (6/6) | 0 |
| 2 | B1.1 | 25–32 (seeded) | g4.1–g4.5 (5/5) | day 32 (g4.6): **spend cap**, not the model |
| 3 | A1.1 | 1–10 | g1.1–g1.5 (5/5) | day 10 (g2.1): **spend cap**, not the model |

Both lost days carry four `story_provider_failed` refusals. That is the harness's `SpendCapReached` (`tests/test_season_one.py` `_live_model`) firing once spend reached the cap. They are artefacts of the budget, and the read marks them as such.

**Against the pass criteria (§6):**

| Criterion | Measured | Verdict |
|---|---|---|
| At most 2 of ~8 first-day attempts lost | **0 of 4** first days the model could attempt (C1 g1.1, g2.1; B1 g4.1; A1 g1.1). Two more (B1 g4.6, A1 g2.1) were cut by the cap. | pass, on a smaller sample than planned |
| No `wrong_beat` / `chapter_not_advanced` continuing a closed chapter | none at all | pass |
| Every `invalid_story_output` carries `finish_reason` and an excerpt | none occurred | pass (vacuous) |

**Overall:** **0 of 16 generated days lost on merit.** The baseline was 31 of 77 (40 %), and 64 % on first days. The fix in `0770a3b` (the brief states what the guards check) holds on this sample.

## Still open

1. **The sample is small.** Four first days were attempted, against ~8 planned. A top-up of about US$0.10 would cover A1 g2.1 and B1 g4.6 with a higher cap.
2. **The continuation read past the epilogue (day 62) was not run** (about US$0.10). The Lila guard is still checked only by a unit test.
3. **The critic was overruled.** It refused 8 drafts twice and they were served anyway ("accepted and logged"): C1 g1.1–g1.4, B1 g4.2–g4.3, A1 g1.3 and g1.5. Examples:
   - a page that ends with nothing changed;
   - Margaux holding a letter that Marin was trusted with.

   The days count as not lost, but the critic is overruled on half the C1 days.
4. **Reply lanes released replies the checker later refused** (9 events, B1 3, A1 6):
   - 5 × `false_successful_grading`: a reply marked "met" when the learner had not given what the task asked;
   - 1 × `reply_vs_resolution_contradiction`;
   - 1 × `attributing_a_learner_choice_to_the_character`;
   - 1 × `unsupported_commitment_resolution`;
   - 1 × `incompatible_demonstrated_targets`.

   Learners would see these replies. This is a grading-trust issue, separate from the loss rate.
5. **The harness learner is canned.** It answers «C'est gentil. Je suis un peu perdu ici.» on many turns. The prose judgments here are about what the model writes around a weak learner, not about a real conversation.

Raw output: `run*/` (`*.json`, `*.md`, `*.spend.json`, `pytest.log`).

## Top-up and continuation (same day, US$0.115; WP-136 total US$0.78)

The epilogue is now six authored days (60–65, Content program D8), so the first generated day after it is **day 66**, not 62. All three runs were dry-run first (`topup/dry-*`).

| Run | Day | Served | Notes |
|---|---|---|---|
| A1.1 | 10 (g2.1) | yes, «Le carnet et l'omelette» | two drafts were blocked by `gendered_agreement` («sûr» for a learner who never gave a gender) and **never shown**. The page served is a third draft that passed every deterministic guard and was refused only by the LLM critic. |
| B1.1 | 32 (g4.6) | yes, «Le matin d'après» | critic and `mixed_address_register` refused twice, then served anyway |
| B2.1 | 65 → **66** | yes, «La fenêtre allumée» | `departed_cast_on_page` **caught Lila** in the first draft; the retry kept her off the page. The guard works live. |

**WP-136 totals:**
- **0 of 19 generated days lost on merit**, including 6 of 6 first days of a gap.
- The Lila guard is confirmed live.

**What remains is not loss, it's the path that serves refused drafts.** When both attempts fail a soft check, the day is served with the refused draft so it is not lost. Correction (same day): no deterministic guard was overruled. Every served page passed them all, and the gendered drafts were blocked. What learners would see is 9 critic-refused pages (storytelling or continuity) and 9 released replies the checker flagged afterwards, 5 of them a false «met». That trade-off is the next story-engine package.

Day 66 also invents a continuity detail, «la nuit du 14 mars», that no canon supports. Romy's replies echo the canned learner lines.
