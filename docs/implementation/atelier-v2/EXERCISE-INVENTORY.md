# Exercise inventory — 2026-10-03

Every exercise type a learner can answer in L'Atelier: where it is generated, where it is graded, where it is drawn, what it trains, which bands get it, and a verdict. The verdict is **keep**, **fix** or **remove**. Findings and fixes are in [EXERCISE-QA-2026-10-03.md](EXERCISE-QA-2026-10-03.md).

Line numbers are from 2026-10-03. Other packages are editing the same files, so expect drift.

## Conventions

- **Skill trained.**
  - **Rec** — recognition (pick from options).
  - **Recall** — retrieve and produce French.
  - **Prod** — free or guided production.
  - **Disc** — discrimination (tell two forms apart).
  - **List** — listening.
- **Grader.** Every typed answer now goes through `app/services/answer_acceptance.py` (`judge`), unless the table says otherwise. Taps are compared by option id or tile id: the server checks them, and the client checks them first against the hashed key (`journey_answer_key.py`, `web-frontend/lib/answer-key.ts`).
- **Chrome language.** The learner's own language up to A2, French from B1 (`chrome_language.py`, `lib/language-rule.ts`). Translations of meaning always use the native language.

## 1. Daily journey: Rappel warm-ups, after-scene practice, recall

**Shared code**
- **Planner:** `fill_practice_items` (journey_planner.py:3010) and the scene top-up `top_up_from_scene` (:3404).
- **Grader:** `journey_learning.evaluate_recall` (:1616). Typed answers use `answer_matches` (:311), now routed through `judge`.
- **Frontend:** `RecallStepView` (`web-frontend/components/atelier-v2/journey/JourneySteps.tsx:462`).
- **Miss feedback:** `AttemptResult.correction`, which carries `{span_fr, corrected_fr, note_native}`.
  - For a tap, the client marks the right card (`correctOptionLocally`).

| Type | Generator | Skill | Bands | Verdict |
|---|---|---|---|---|
| `choice` (meaning → French) | `build_recall_task` journey_planner.py:865 | Rec | A1–A2; B1+ only as one warm-up | keep |
| `choice`, scene cloze | `scene_items.build_cloze_task` :388 | Rec in context | all | **fixed**: needs ≥ 2 context words (no more «La ___», «___.») |
| `choice`, grammar «which sentence follows the rule» / «choose» | `grammar_items.recognise_item` :374, `choose_item` :439 | Disc | Essai A1–A2; one warm-up at B1+ | keep |
| `classify` (gender m/f, tu/vous) | `build_classify_task` :1115 | Disc | A1–A2 | keep; owner call: the option labels «masculin/féminin» are French chrome for a German A1 learner |
| `listen_tap` | `build_listen_tap_task` :1378 | List / Rec | A1–A2, listening days | keep (reads as Rec while no audio is deployed) |
| `who_said` | `build_who_said_task` scene_items.py:340 | plot memory | none (producer removed by QA-PRACTICE) | **remove** the dead enum, UI and grader branch (tests plot, not French) |
| `tiles` | `build_recall_task` :865 | Recall (order) | A1–A2 | keep |
| `word_bank` | `build_word_bank_task` :1045, `grammar_items.build_item` :489 | Recall (order + selection) | A1–A2 | keep |
| `unscramble` (rebuild a scene line) | `build_unscramble_task` :1465, `build_line_unscramble_task` scene_items.py:465 | Recall (syntax) | A1–A2 | **fixed**: an unnamed speaker is no longer printed as an id («clerk_2») |
| `match_pairs` | `build_match_pairs_task` :1312 | Rec | A1–A2 warm-up | **fixed**: never two identical grids in one day |
| `short_answer` | `build_recall_task` :865; B1+ «Complétez»; Rappel coach scene (journey_learning.py) | Recall | all | **fixed**: give-up sentences no longer pass; slips are named; never posed in the block that just printed the word |
| `transform` (tu↔vous; «correct this sentence») | `build_transform_task` :1197, `grammar_items.transform_item` :571 | Prod (guided) | all; most of B1+ | **fixed**: accent-sensitive; no «-s/-ent» typo pass |
| `dictation` | `build_dictation_task` :1616; grader `evaluate_dictation` journey_learning.py:1814 | List → Recall | all; needs audio | keep (its own partial credit for accents is right for dictation) |

## 2. The Règle step and its test-out

| Type | Generator | Grader | Frontend | Skill | Verdict |
|---|---|---|---|---|---|
| Rule card (read, not answered) | `_rule_step` journey_planner.py:3283; card from `grammar_units.rule_card` | — | `RuleStepView` JourneySteps.tsx | input | keep |
| Essai, A1–A2: recognise → choose → build → transform | `grammar_items.guided_items` :609 | `evaluate_recall` | RecallStepView | Disc → Recall → Prod | keep |
| Essai, B1+: one warm-up + up to 3 repairs | `guided_items` | `evaluate_recall` | RecallStepView | Prod | **fixed**: a repair never asks for the sentence the card or warm-up just printed. B1 units now have ≥ 2 pairs, so B1 learners meet the Règle at all. |
| Spaced review (Rappel) | `grammar_items.review_item` :668 | `evaluate_recall` | RecallStepView | Recall | keep |
| «Je connais déjà — vérifier»: discriminate → transform → free use | `ForgeService.start_test_out` forge.py:866; pass rule `core/forge.evaluate_test_out` :597 | `atelier._test_out_local_grade` :133 | `RuleTestOut.tsx` | Disc / Prod | **owner/Forge**: free use passes on a detector hit even with wrong French; a missed free-use item shows no expected line |

## 3. La Forge, Éclair, l'Épreuve (Forge package; read-only for this pass)

| Rung / mode | Generator (item_bank.py) | Grader (atelier.py) | Frontend | Skill | Note |
|---|---|---|---|---|---|
| recognise → `fill` | `fill_item` | `_correct_recognize` :5470 (`_normalize`, accents folded) | atelier.tsx `RecognizePanel` | Rec | an accent-only trap would be graded right (none in the bank today) |
| discriminate → `classify` | `classify_item`, `pair_item` | same; correct-it follow-up `forge_grading.classify_follow_up` | atelier.tsx, `ForgeFollowUp.tsx` | Disc | A1 tile follow-up vs an inner comma (see QA) |
| build → `word_bank` | `word_bank_item` | `_normalize` join | atelier.tsx | Recall | keep |
| transform → `rewrite` | `transform_item` | `_correct_transform_rule_based` :6040 (`forge_grading.same_answer`, accents kept and reported) | `TransformPanel` | Prod | already matches the contract |
| produce → `sentence`/`speak`; free_use → `conversation` | `output_item`, `scene_item` | local check, then the model (`_correct_output_ladder` :6104) | `OutputLadderPanel` | Prod | keep |
| Séance paragraph | `produce_block` | `_correct_produce` :6437 | `ProducePanel` | Prod | **fixed**: «Wort/Wörter» → pluralised count |
| Éclair (60-second minimal pairs) | `eclair._items_for_rule` :237 | `eclair.grade_answers` :385 | `pages/eclair.tsx` | Disc (speed) | **fixed**: the server now keeps accents, like the page |

## 4. Vocabulary

| Type | Generator | Grader | Frontend | Skill | Bands | Verdict |
|---|---|---|---|---|---|---|
| Drill card, recall-ladder rungs (recognition, production, audio, cloze, scene, rescue) | `recall_ladder.rung` :63, `card_ladder` :86; `progress.py` | **client only** (`review.tsx normalizeAnswer`); the server trusts `correct` (`vocab_fsrs.earned_rating`) | `pages/vocabulary/review.tsx` | Rec → Recall | per-band thresholds | **owner call**: move grading to the server, or port `judge` to TS |
| Band check («Vérification du lexique») | `band_check._items` :104 | `band_check.submit` :152 (option index) | `band-check/BandCheck.tsx` | Rec | sub-bands below the learner's | **fixed**: «le haricot», not «l'haricot» |
| Conjugation review | `ConjugationService.review_queue` :478 | client compare + self-rating (`review` :544) | `pages/vocabulary/conjugation.tsx` | Recall | ≤ band | keep; client fold misses «œ» (owner: port `judge`) |
| Erratum review (repair your own mistake) | `error_memory` task payload | `review_answer_repairs` error_memory.py:38 | `ErrataReviewSheet.tsx` | Recall | all | **fixed**: retyping an accent error no longer files it as repaired; word boundaries, not substrings |

## 5. Courrier, Revue, radio, story

| Type | Generator | Grader | Frontend | Skill | Verdict |
|---|---|---|---|---|---|
| Courrier letter reply (free) | `MissionGenerator` missions.py:1055 | `MissionCorrectionService.correct_submission` :2698 (model, then authored fallback) | `pages/missions.tsx`, `Courrier.tsx CrRepair` | Prod | keep; English strings in stored objective notes (see QA, owner) |
| Revue respond turn | `RevueEncounter.turn` encounter.py:1989 | `revue/grading.grade` :338 | `RvThread.tsx` | Prod | keep; wrong words are never named (by design) |
| Revue headline choice | `_headline_exercise` :2716 | option id `_pick_headline` :2906 | `RvMake.tsx` | Rec (reading) | keep; no retry |
| Revue headline write / short report / reader question | encounter.py :2862 / :2886 / :2937 | rubric / none | `RvMake.tsx` | Prod | keep (B1+) |
| La Relecture | `relecture.offer` :175 | `relecture.answer` :324 | `CarteRelecture.tsx` | Prod (re-do) | keep; Romy's lines are French only (by design) |
| Le Correcteur (proofread) | `correcteur.draft_for` :1070 | `correcteur.grade` :1234 (accents kept) | `CrResult.tsx` | Disc → Prod | **owner**: `grammar_point` is French only for a German A1 learner |
| La Carte review (`match_pairs`/`word_bank`/`unscramble`/`dictation`) | `carte._items_for` :536 | `carte.grade_review` :683 | `CarteReview.tsx` | Rec / Recall / List | **owner**: no expected answer in the response; dictation folds accents |
| Radio dictée | `radio.dictee_index` :279 | `radio.grade_dictee` :577 → `evaluate_dictation` | `RadioSurface.tsx` | List → Recall | keep |
| Story / season reply turns | season/turns.py, runtime.py | **routed by meaning, never graded** (`match_reply` :90 / `ReplyChoice`); the form correction is a separate margin note | JourneySteps.tsx | Prod (meaning) | keep; story package: a reply in German routes like French (see QA) |
