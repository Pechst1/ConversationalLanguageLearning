# Séance: honest assessment and a coherent practice loop

The earlier visual redesign did not finish the learning loop. The reported screenshots exposed false-positive grading, prompts without an actual question, and exercises whose target differed from the displayed rule.

## What changed

- Free writing, spoken transcripts, and conversation require a completed AI assessment. Provider failure saves the response as unassessed; it earns neither mastery nor vocabulary credit. Retry is exposed, including for older unchecked answers.
- UI verdicts use the assessment, not the absence of displayed errata. Task-compliance problems remain visible. An English complaint cannot be displayed as an approved model recording simply because no grammar errors were returned.
- The whole answer reaches the checker; the previous 520-character truncation could hide later mistakes. Correction output has a larger budget. Open answers no longer carry a heuristic score that biases the model. Invalid or incomplete model responses are rejected.
- Each of the 54 core catalog lessons has an inspectable challenge, a marked teaching span and foil, and a real question. Catalog identity determines the lesson; incidental words in examples cannot select a different grammar family. The y/en lesson explicitly explains replacement, placement and retaining the quantity.
- New compact curated sets use one recognition item per mode and one repair, followed by open use. Existing authored si, tense-contrast and negative-quantity sets retain their larger, adaptive drill pools. Time estimates remain conservative pool estimates; the actual session progress counts its own items.
- Generated sets must retain the canonical rule and pass a complete per-item critique covering exact subskill alignment, answerability and answer quality. Missing critique coverage falls back to curated material. The generator version invalidates earlier broken content.
- Character decoration preserves the actual question. A character response is only generated after a successful answer. Internal character biographies are no longer printed in the byline.
- Final writing now uses the same first-session assignment on the server and screen, with only its visible requirements. The final curated prompt invites the learner to change a detail and adapt the response, rather than copy the worked example.
- Whole-line repair is graded against the same complete rewrite shown on screen. A successful repair feeds the existing delayed retrieval queue after two intervening drills; copying a repair itself does not earn a mastery reward. Off-topic answers make retry the primary action.

## Learning design and evidence

The loop is **notice → retrieve/build → detect a trap → repair → say it without rereading → reply → change the situation**. Feedback distinguishes language errors, missing task requirements and unavailable assessment. The learner gets a brief explanation and an actionable retry, rather than generic praise.

Retrieval, spacing and corrective feedback have experimental support in web vocabulary learning: [Belardi et al., 2021](https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2021.757262/full), with a [2025 correction](https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2025.1629682/full). This supports the direction of the repair/retrieval loop; it is not proof that this particular grammar interface improves retention.

A semi-open language-learning study found value in simpler immediate feedback: [From belief to evidence, 2025](https://www.frontiersin.org/journals/education/articles/10.3389/feduc.2025.1654809/full). Accordingly, the interface leads with the specific correction and gives the learner another attempt. The findings do not establish a universally best exercise or justify a gamification claim.

The proposed engagement comes from concrete questions, speaking, making a choice about a detail, and seeing one's own corrected sentence. Whether learners find this fun requires learner testing. Useful follow-up measures are voluntary retry rate, delayed-retrieval accuracy, completion without skips, and reports of irrelevant prompts; completion alone should not be treated as learning.

## Validation and limits

Regression coverage checks every core lesson, incomplete model outputs, no-op verdicts, unavailable review in all four freeform rounds, full-paragraph transmission, and the frontend success decision. Existing tests that previously expected offline open answers to pass now explicitly test either diagnostic hints or honest unassessed behavior.

An isolated browser preview renders the real séance components with offline fixtures. It verifies a concrete speaking question, the expanded en rule, rejected English input, and an unavailable checker with a retry action. This is component/UI verification, not a live microphone or device test.

The first three authorized live checks with the old gpt-5-nano configuration exposed weak feedback and a false rejection of a valid answer. The correction default was therefore changed to gpt-5-mini with low reasoning, and contradictory prompt instructions were removed. Real model quality must be evaluated separately from deterministic plumbing; an AI cannot guarantee every grammar judgment.

No production deployment or user-history rewrite is included. Existing environment overrides can supersede the new model default. Previously awarded historical mastery is not retroactively erased.

### Final check results

- Focused backend/UI regressions: 174 passed, followed by the added future-tense feedback regression (the contract suite now has 68 cases).
- Production Next.js build, TypeScript check and lint passed. The broad suite initially had 1,538 passing tests and five failures; those failures were resolved and their suites rerun together successfully.
- Authorized live model checks: the revised gpt-5-mini checker accepted the valid French sentence (4/4), rejected the English complaint (0/4), and flagged the screenshot paragraph (1/4) with grammar, vocabulary and task-compliance feedback.
- The long-paragraph retry confirmed a complete JSON response using 2,573 completion tokens. The final output ceiling is 5,000 tokens, with a 60-second single-attempt deadline. The previous 900-token default was insufficient for this case.
- Some AI explanations still make context-dependent interpretations (notably pronoun referents and whether a morning action is completed). The prompt now explicitly cautions against forcing those interpretations. The live checks establish the reported false-success fix, not perfect linguistic accuracy.

To use the new defaults, restart the backend and start a new séance. A deployment and a physical-device microphone test remain outside this local change.
