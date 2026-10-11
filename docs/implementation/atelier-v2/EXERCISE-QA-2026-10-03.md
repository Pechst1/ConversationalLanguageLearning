# Exercise QA — 2026-10-03

**Trigger.** On day 1 the owner played as an A1 learner with German as native language and met incoherent items. The test suite was green at the time.

**Mandate.** Every exercise must be clear, natural, at the learner's level, worth the learner's time, fairly graded, explained when missed, and written entirely in the learner's language.

**Related documents**
- The inventory and a per-type verdict: [EXERCISE-INVENTORY.md](EXERCISE-INVENTORY.md).
- Running at the same time, and not duplicated here:
  - the story lane (QA-STORY);
  - the practice items (QA-PRACTICE): «Wer hat das gesagt?», unscramble notes, «appartement», «2 Wörter»;
  - La Forge (QA-FORGE / FORGE-DE).

## 1. The permanent gate: a learner walk

| File | What it does |
|---|---|
| `tests/learner_walk.py` | Plays whole days through the real HTTP router in production configuration, and records each day as a JSON transcript in reading order. Production configuration means: season 1 with level overlays, the practice day, the v2 catalogue, the authored first day, and the core word list synced as at deploy. |
| `tests/walk_checks.py` | Eight automated checks over the transcripts: grading, language leaks, translation↔French, duplicates and "answer just printed", level, a miss shows the expected answer, placeholders / machine keys / empty gaps, and names the learner has not met yet. |
| `tests/test_learner_walk.py` | **Fast tier** (default, about 1 min): day 1 for each of 5 personas × good / average / poor answers. **Long tier** (`-m walk` or `WALK=1`, about 2.5 min): one 30-day life per persona, with days 1, 2, 7, 14 and 30 recorded. `WALK_TRANSCRIPTS=dir` writes the JSON files and `WALK_ALL_DAYS=1` records every day. |

**Personas.**

| Persona | Native language | Level |
|---|---|---|
| Fresh learner | de | A1.1 |
| Placed learner | de | A2.1 |
| — | en | B1.1 |
| — | en | B2.1 |
| — | de | C1.1 |

**Answer qualities.**
- **Good:** the key, or the season's own example reply.
- **Average:** iPhone typography, an accent slip, and one tap in three wrong.
- **Poor:** a wrong answer, or a reply in German.

**Fake story provider.** The model is the season suite's scripted provider. A compliant director weaves the day's grammar unit into the scene (`learner_walk.weave_grammar`); without this, no generated day can ever carry a Règle. The fake's English placeholder prose is not product content, so the checks skip it (`walk_checks._is_fake`).

**CI.** Add `pytest -m walk tests/test_learner_walk.py` as a separate job. I did not edit the workflow files, because they are under another agent's working tree.

## 2. Findings, ranked, with fixes

| # | Severity | Finding (walk evidence) | Fix | Regression test |
|---|---|---|---|---|
| F1 | **P0** | **A B1 learner never met a Règle step.** In 30 days, 0 rules and 15 days with no item at all. Every B1.1/B1.2 v2 unit (40/41) has a single ✗→✓ pair in `main_traps`, and a B1 Essai needs two repairs, so the introduction was refused every day. Because `introduction_for_today` only looked at the first unit in line, the whole grammar track stopped behind it. After the fix: **14 rules in 30 days** (same as B2/C1). | `grammar_units.contrast_pairs` also reads the reviewed card's `traps` (3 pairs per B1 unit). `concept_life.introduction_for_today` looks 3 units ahead and takes the first one that is `introducible`. | `test_every_b1_unit_has_two_contrast_pairs_for_its_essai`, `test_an_unintroducible_unit_does_not_hold_the_grammar_track` |
| F2 | P1 | **The B2/C1 Essai asked the learner to rewrite the sentence just printed three times.** The card prints «Je suis content que tu es là → … sois là». The warm-up offers both. The first repair is the same «Je suis content que tu es là.» That is copying, not retrieval. (Seen on 26 B2/C1 days.) | `grammar_items.guided_items`: from B1, a repair never asks for the card's ✓ sentence or the warm-up's answer when other pairs exist; otherwise the warm-up gives way. | `test_the_essai_never_asks_to_rewrite_what_the_card_or_warm_up_printed` |
| F3 | P1 | **Grading was unfair in both directions.** «Il à mangé», «je parles», «les enfants mange», «Je ne bois pas du café» and «Si tu viendras» were all accepted for the right form: everything was accent-folded, and `SequenceMatcher ≥ 0.92` let them through. «euh je ne sais pas» was accepted for «pas» (word containment; found on 4 days of the walk). «soeur» was refused for «sœur», because the fold deleted «œ». | New `app/services/answer_acceptance.py`, the one contract, with these rules: **typography never counts**; **accents are lenient but named**, and strict for homographs and a verb's «-é»; **one typo never makes another form or another word**; **elision is French**; **optional articles** must have the right gender; **opt-in alternatives** for est-ce que / inversion and on / nous. The journey (`answer_matches`, `fold_for_comparison`) and the erratum review are routed through it. Containment is limited to words and short phrases in a short frame. | `tests/test_answer_acceptance.py`: 156 cases, a 40-row table run through `judge`, the journey grader and the erratum review |
| F4 | P1 | **A miss on an accent showed nothing.** «Il à mangé» was refused, but `build_correction` dropped the correction because the strings matched once accents were folded. The learner saw «Noch nicht» with no expected answer. | `build_correction` treats typography as a no-op but not accents. The why comes from the verdict («Hier ändert der Akzent das Wort: «a», nicht «à»»). A forgiven slip is met with no correction (existing policy `test_journey_correction_policy`); naming it is owner decision 8. «s il vous plaît» (apostrophe typed as a space) is typography. | `test_a_refused_form_says_why`, `test_a_forgiven_accent_is_met_without_a_correction` |
| F5 | P1 | **Retyping an accent erratum filed it as repaired.** In `error_memory`, «probleme» counted as repaired against «problème», and the target was matched as a bare substring. | `review_answer_repairs`: strict accents when the erratum was an accent, and word-boundary windows. | `test_an_accent_erratum_is_not_repaired_by_retyping_the_error` and the table |
| F6 | P2 | **The same item twice, or a word produced in the block that printed it.** Two identical «Tippe die Paare an» grids on one day (A2, days 2, 4 and 28). «Wie sagt man „nie“?» came right after a cloze whose card was «jamais». | `journey_planner._repeats_the_day` is applied in the fill and in the scene top-up. | `test_two_match_grids_…`, `test_no_production_of_a_word_in_the_block_that_printed_it` |
| F7 | P2 | **«Bring den Satz von clerk_2 …» / «Bau nach, was clerk_2 gesagt hat».** An unnamed walk-on speaker was printed as an id. | `scene_items.named()`; a nameless line uses «Bring den Satz aus der Szene …» with its meaning, or is not posed. | `test_an_unnamed_speaker_is_never_printed_as_an_id` |
| F8 | P2 | **Gaps with no sentence around them:** «La ___», «___.», «___ chacune.» | `build_cloze_task` needs at least 2 context words. | `test_a_gap_needs_a_sentence_around_it` |
| F9 | P2 | **«Wort/Wörter», «word(s)», «mot(s)»** in the Épreuve paragraph erratum and the Journal word count. | `learner_copy.word_count` (French counts 0 as singular); `cahier-copy.ts` gains `word_count_one`. | `test_word_counts_are_pluralised…`, `tests/test_exercise_copy_languages.py` |
| F10 | P2 | **Éclair's server folded accents**, while the page keeps them. A minimal pair «a/à» would be graded differently on the two sides. | `eclair._normalize` = `fold_typography`. | `test_eclair_keeps_the_accent_of_a_minimal_pair` |
| F11 | P3 | **The band check printed «l'haricot», «l'honte».** | `band_check.H_ASPIRE`. | `test_the_band_check_never_elides_before_an_aspirated_h` |

**Language hygiene (step 5).** `tests/test_exercise_copy_languages.py` renders all 258 trilingual tables of the exercise modules in en, de and fr. It fails on:
- a missing language;
- mismatched or left-over `{placeholders}`;
- English under «de» or German under «en»;
- slash plurals.

It found F9.

**Level fit (step 6).** I sampled 50 items per band from the 30-day walks and checked them against lexicon v3 bands, the reviewed v2 detectors, and the presence of a goal or translation:

| Band | Words above band + 1 | Grammar above band + 1 | Drill with no goal |
|---|---|---|---|
| A1 | 0 | 0 | 0 |
| A2 | 0 | 0 | 0 |
| B1 | 0 | 1 | 0 |
| B2 | 0 | 0 | 0 |
| C1 | 0 | 0 | 0 |

The B1 grammar hit is «la femme dont le fils travaille ici», matched by `FR2_C11_RELATIVE_CHAINS`; that detector is approximate and over-matches a B1 «dont».

**Before / after (A1, German native, from the walk)**

| | Before | After |
|---|---|---|
| Cloze | «Ergänze den Satz aus der Szene. `La ___`» (lettre / vendre / clé) | not posed; a line with context is used instead |
| Accent miss | «Il à mangé.» → Noch nicht, no correction | → «Il a mangé.» · «Hier ändert der Akzent das Wort …» |
| Give-up | «euh je ne sais pas» → **Richtig** (key «pas») | → Noch nicht + «pas» |
| B2 Essai | card «tu [sois] là» → repair «Corrigez : Je suis content que tu es là.» | the repairs use the other two traps |

## 3. Reported to other packages (I did not edit these)

1. **Story (season/page.py `convince_as_turn`).** «Convaincre» objections are said by `solve.to`, a cast id. The reply prints «augustin_de_roncourt : Marchand ? Il veut fermer le café !» and `speaker_name: "augustin_de_roncourt"` (T3, walk days 17–18). The walk filters exactly this symptom (`walk_checks.KNOWN_DEFECTS`); remove the entry with the fix.
2. **Story.** A reply written in German («Ich weiß nicht.») routes and continues the page as if it were French (`task_outcome: met`). It should get a gentle «en français ?».
3. **Story.** The C1 objective «Dis qui tu es» is in *tu*, while all other French chrome addresses the learner as *vous* («Construisez», «Complétez»).
4. **Forge.**
   - The test-out's free-use item passes on a detector hit alone (`atelier._test_out_local_grade`), even when the French is wrong, and a miss shows no expected line (`RuleTestOut.expectedOf` ignores `example_answer`).
   - `atelier._normalize` and `item_bank.normalize` fold accents for fill / classify, so an accent-only trap would pass.
   - `_close_enough_transform` accepts anything containing «pas de».
   - The A1 tile follow-up cannot be correct when the corrected sentence has an inner comma (`classify_follow_up` vs `foldSentence`).
   - These should adopt `answer_acceptance`.
5. **Practice.** `who_said` has no producer left. Delete the enum value, the `WhoSaid.tsx` UI and the grader branch.

## 4. Owner decisions, ranked

1. **Vocabulary drill and conjugation are graded only on the client.** The server trusts `correct` (`vocab_fsrs.earned_rating`), and the client folds differ (`review.tsx` folds œ; `conjugation.tsx` does not). The options are server grading through `judge`, or a TS port of `answer_acceptance` with a shared fixture table.
2. **B1 `main_traps` hold one ✗→✓ each** (the other traps are prose). The card's traps cover the gap now. Should the TSV be re-authored to three explicit pairs, as at A1/A2/B2?
3. **Two C1 units and `FR2_A12_ER_SPELLING` still cannot be introduced** from their authored material: `FR2_C12_SUBJ_PLUS_QUE_PARFAIT`, `…PASSE_ANTERIEUR`, `…SUBJ_IMPARFAIT` (one or no repair). They are now skipped rather than blocking. They need authored pairs or a recognition-only Essai.
4. **Classify options «masculin / féminin»** are French for a German A1 learner. Should they be translated, or kept as grammar terms?
5. **Accents in production items** are lenient-but-named by default. Should accent-strictness be turned on for the -cer/-ger units (ç, «mangeons»)? The contract supports it per item (`accents="strict"`).
6. **No retry after a miss** on Revue headline choice, Correcteur, radio dictée, Carte and Relecture. Is that by design?
8. **Name a forgiven slip on a hit?** «Richtig — achte auf den Akzent: «très»» is authored (`answer_acceptance.NOTE_COPY`) but the journey policy says a met answer carries no correction.
7. **Courrier objective notes** keep English literals in stored payloads (missions.py :3325–3562). They are hidden by the frontend filter today.

## 5. Verification

- `pytest`: full suite 6,005 passed; the remaining failures are outside this package and fail without it: `test_wp69_schema_guard` (unapplied password-reset migration), `test_revue_relecture` (pydantic forward ref `Rubric`), `test_mobile_capture_harness`. Every suite touching the changed graders passes after aligning with the existing correction policy. New suites:
  - `test_answer_acceptance` (156)
  - `test_exercise_qa_fixes` (15)
  - `test_exercise_copy_languages` (258)
  - `test_learner_walk` (16 + 5 long)
- `web-frontend`: `npm test` 887/887; `npx tsc --noEmit` clean. No schema change, so no `types:generate`.
