# WP-149: paid confirmation (2026-10-08, US$0.41)

**Setup.** Branch `exp/wp149` @ df8cf5d, using the same harness as WP-136 (`tests/test_wp133a_live_read.py`).
- Run 1: A1.1, days 1–10.
- Run 2: B1.1, days 25–32, seeded.
- Each run was capped at US$0.25, and a free dry run (`dry/`) came first.
- Spend: A1 US$0.212, B1 US$0.201. Neither run hit its cap.

| Criterion (WP-149 §Acceptance) | Result | Verdict |
|---|---|---|
| 0 after-release `false_successful_grading` | **0** (WP-136: 5) | pass |
| 0 correctness overrides served | **0**. One `story_critic_correctness` refusal (A1) was retried, not served. | pass |
| Loss rate ≤ 2 of ~8 first days | **1 of 12 generated days lost**: B1 day 27 (g4.1), `season_spoiler` «Berlin» + `mixed_address_register` on every draft, so it fell to the re-read. First days: 1 of 3 lost (A1 g1.1 and g2.1 ok). | pass on the measured sample |

## Results

- **Story-critic overrides served:** 0 in both runs (WP-136: 8 storytelling and 2 correctness on the same days). The critic now sees the learner's turn, and it refused nothing on storytelling grounds.
- **Replies flagged after release:** 3 (WP-136: 9). None is a grading error:
  - A1, `gendered_address`: the phrase «Le apprenant» in the released `understood_intent` / proposal fields.
  - B1, `gendered_address`: the inclusive-dot form «tu t'es engagé·e» in released materials.
  - B1, `invented_learner_choice`: the reply credits the learner with a private plan and pledge they never made.

  None of the three appears in the dialogue transcripts (`*.md`). Whether the `understood_intent` / proposal fields reach the screen needs a check.

## Follow-ups (not WP-149 scope)

1. **Gender guard in the reply lane.** The scene guard `gendered_agreement` does not run on reply-lane fields. Add `·e`/`(e)` inclusive forms and «le/la apprenant(e)» to the deterministic reply scrub.
2. **`invented_learner_choice`.** Add a deterministic check that a reply attributes no commitment absent from the learner's text, or move this issue class into the met-gate's evidence rule.
3. **Season-spoiler pressure on B1 g4.1.** The director keeps reaching for «Berlin» before T5. Add it to the brief's `_must_not` for chapter 4 (cheap).
