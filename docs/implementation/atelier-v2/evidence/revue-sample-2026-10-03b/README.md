# WP-119 §10e · Acceptance rerun «La voix de Romy», 2026-10-03

The same ten Papier sessions and the same scripted learner as the first sample
(`../revue-sample-2026-10-03/`), rerun with the real provider and the real critic after phase 6.
Read by hand with the same reader's criteria. No expected-failure markers; what fails is reported as
failing.

## Method

- **Harness**: `revue_sample.py`, a copy of the first sample's script with three changes. It writes
  here. It meters each call's cost per thread (reply, guest and critic now overlap). It records
  each call's start time and the prompt versions. The database is the same throwaway SQLite with the
  `DATABASE_URL` override and the same assertion. The OpenAI key comes from `.env` and is never
  printed.
- **Kiosk, learners, script**: unchanged. The kiosk is the six live W40 dossiers plus the same four
  evergreens. There is one new user per session, with bands A1 ×3, A2 ×4, B1 ×3 and the same gloss
  languages. The script is `start` → «D'accord, je t'aide.» → an answerable question → a question
  only an uncertainty covers → an opinion plus one use of the plan's first le/la word (the article
  is wrong in sessions 2, 5 and 8) → `make_options` → the recommended option → `close`.
- **Models**: `gpt-5-mini`, `reasoning_effort="low"`, JSON mode. Temperature is 0.4, and 0.0 for
  the critic. The vignette stamp uses `FakePictogramProvider`, as in the first sample.
- **Prompt versions** (recorded on every event that carries a `cost_usd`):

  | Prompt | Version |
  |---|---|
  | reply | `revue-reply-v2` |
  | guest | `revue-guest-v2` |
  | close | `revue-close-v2` |
  | question | `revue-question-v2` |
  | vocabulary | `revue-vocabulary-v2` |
  | headline | `revue-headline-v2` |
  | critic | `revue-critic-v1` |
  | rubric | `revue-rubric-v1` |

  In the first sample the prompts were unversioned, with hash `d9b68538d1f6`.
- **Records**: `sessions/NN.json` has the same shape as the first sample. Every `turn_romy` and
  `turn_guest` event now also carries `refused`, `regenerated_for` (the first attempt's problems),
  `repaired`, `prompt_version` and `seconds`. `verdicts.json` holds the per-session verdicts and
  notes.
- **Not part of this run**: the vocabulary top-up changed after the run. It now accepts an
  infinitive or a singular whose stem the claim inflects, and it tops up with nouns that come with
  their article first. Unit tests cover the change, but this run did not measure it (see «What
  remains»).

## Totals

| | |
|---|---|
| Cost | **US$0.171** for 10 sessions, mean **$0.0171** per session, min $0.0125, max $0.0220. Three sessions are above $0.02: s1 $0.0205, s3 $0.0206, s5 $0.0220. `state.cost_usd` equals the provider's spend in every session. |
| Calls | 120 calls: vocabulary 10, reply 42, guest 20, critic 18, headline 10, question 10, close 10. 0 errors. |
| Regenerations | 2 of 42 replies (both `symbols`, s5 «km/h»: repaired to «km par heure»). 0 of 20 guest lines, 0 of 10 closes, 0 of 10 questions. `revue_id_leak` was logged 0 times: the model wrote no id at all. |
| Latency per call (p50 / p95) | reply 4.6 / 7.3 s · guest 3.5 / 5.0 s · critic 3.0 / 4.4 s · vocabulary 5.8 / 8.8 s · headline 4.6 / 5.3 s · question 2.2 / 3.1 s · close 4.6 / 6.2 s |
| **Latency per learner turn** | **p50 4.8 s, p95 7.9 s, max 10.7 s** (40 turns). turn 1: 4.5 / 9.2 s · turn 2: 5.7 / 8.1 s · turn 3: 4.9 / 7.2 s · turn 4: 4.8 / 6.7 s |
| Other actions (p50 / p95) | start 5.8 / 8.8 s · make_options 4.7 / 5.3 s · close 4.6 / 6.2 s |
| Late evidence | 0 of 40 turns. The critic starts with the reply and always answered within the 2 s window. |
| Simplify | 0 support changes, 0 breakdowns counted (the first sample counted 1 false breakdown, in s6). |
| Knowledge | 0 must-not hits, 0 refusals. No line mentions Le Mistral, Ferrand, Solvel, Odile or the letter. |

## Verdicts

| # | Dossier | Band | Cost | French | Grounding | Guest | Rubric | Simplify | Knowledge | §1 acceptance |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | budget-2027 | B1 | $0.0205 | pass | pass | pass (Marin, contre) | pass | pass | pass | pass |
| 2 | ce-qui-change-1er-octobre | A2 | $0.0174 | pass | pass | pass (Marchand, contre) | pass (incorrect→incorrect) | pass | pass | pass |
| 3 | goncourt-roman-retire | B1 | $0.0206 | pass | pass | pass (Lila, pour) | pass | pass | pass | pass |
| 4 | paris-plan-canicules | A1 | $0.0183 | **partial** | partial | pass (Marchand, pour) | pass | pass | pass | pass |
| 5 | prix-de-l-arc-de-triomphe | A2 | $0.0220 | pass | partial | partial (Gus) | pass (incorrect→incorrect) | pass | pass | pass |
| 6 | prix-produits-frais | A1 | $0.0153 | pass | partial | partial (Margaux) | pass | pass | pass | **pass** (was FAIL) |
| 7 | evergreen marché | A2 | $0.0125 | pass | pass | n/a | pass | pass | pass | pass |
| 8 | evergreen grève | B1 | $0.0149 | pass | pass | n/a | pass (incorrect→incorrect) | pass | pass | pass |
| 9 | evergreen beaujolais | A1 | $0.0129 | **partial** | pass | partial (Margaux) | pass | pass | pass | pass |
| 10 | evergreen rentrée | A2 | $0.0166 | pass | pass | pass (Lila, pour) | pass | pass | pass | pass |

Per criterion:

- natural French **8/10** (2 partial)
- grounding 7/10 (3 partial)
- guests 5 pass and 3 partial of 8 sessions with a guest; **8/8 entrances take a side**
- rubric 10/10, simplify 10/10, knowledge 10/10
- acceptance **10/10**

## Before → after (same sessions, same script)

| | 2026-10-03 (first sample) | 2026-10-03b (this rerun) |
|---|---|---|
| Natural French (reader's criteria) | **0/10** | **8/10** (s4, s9 partial) |
| Ids in what the learner reads | 40/40 replies; 26 translations; plus «(a1)», «(incert. 1)» | **0** in every reply, translation, guest line, proposal, close, headline and body |
| Symbols at A1–A2 shown | 7 replies («100→140 €», «≈0,40 €/L», «>60 km/h») | **0** (1 turn regenerated twice, then repaired) |
| Orders to the learner | 3 replies («Dis-lui:», «Dis : …», «Propose…, Précise…, Donne…») | **0** |
| New claims in the first reply | 2–4, with 9 of 10 sessions putting 3 or 4 on the table | 1–2 in every session; no turn shows more than 2 |
| Restated claims | e.g. s2: c1 and c2 in all three later replies | restated ids dropped by the service; 1 restatement in the text (s4, turn 4) |
| Reader question proposed | 33 of 40 replies, 10 sessions proposing it more than once | 10 of 40 replies, exactly once per session |
| Angle changes | 21, with 8 sessions flipping 2–3 times | **0** (no learner turn named the other angle) |
| Guest entrances with a side | 0 of 8 | **8 of 8** (`position` for/against) |
| Guest service offers | 8 of 12 follow-ups by the first reader (6 caught by `voice.is_service_offer`) | **0 of 20** lines |
| App words in the close | 10/10 («dans le dossier», «je ferme la session», «l'artefact») | **0/10** |
| Session 6 (uncertainty off by one) | `uncertainty_cited=2` dropped; the question recorded as answerable; acceptance **FAIL** | `u2` cited by id; recorded as unanswerable; filed as the reader question; **pass** |
| §1 acceptance | 9/10 | **10/10** |
| Credited evidence on a known can-do | 1 of 40 learner turns | **8 of 40** (6 correct, 2 incorrect) |
| Rubric | 10/10 | 10/10 |
| Turn latency p50 / p95 / max | 7.7 / 12.7 / 16.6 s (turn 4: p50 11.3 s) | **4.8 / 7.9 / 10.7 s** (turn 4: p50 4.8 s) |
| Cost per session (mean / max) | $0.0157 / $0.0200 | $0.0171 / $0.0220 |

## Failures, with quotes

### F-1 · A reply that restates and does not follow (s4, turn 4; partial)
The learner says «C'est bien pour les enfants. Pour moi, la baignade, c'est important.» Romy:
«Tu as raison, la baignade, c'est important. Mais d'après la Ville, la baignade dans la Seine
pourra commencer plus tôt.» This restates c3, which was shown a turn earlier. The service dropped
the restated id, but the text still says it. «Mais» follows nothing, and c3 comes from ICI Paris,
not the Ville. The no-restatement rule is enforced on the cited ids and only asked for in the
prompt. Nothing checks the text against the claims already shown.

### F-2 · A reaction in name only (s9, turn 4; partial)
«J'aime le vin rouge.» gets «Je comprends.» and then the 1985 sale date. In the first sample it got
c4 with no reaction at all. This time there is a reaction, but it is empty. In s6 and s5 the same
rule gives a real question back («Pourquoi le mois est important pour toi ?»).

### F-3 · Guests take a side, but not always on the story (s5, s6, s9)
- Gus (s5) enters with «le cheval avec le plus d'argent derrière peut gagner, parce qu'il y a de
  l'argent là-dedans, croyez-moi.» The voice is his, but it is a bet on the outcome, not a side on
  the angle. His later lines lean on «ma Méthode sculpte l'effort» twice.
- Margaux (s6) enters with «Je suis pour car ce que je sers vient du marché et me coûte plus cher.»
  It is not clear what she is for. She then says «Les tomates et la salade sont plus chères», a
  fact the dossier's own uncertainty says the sources do not have. The guest prompt forbids
  inventing, but no check compares a guest's statements with the claims.
- Margaux (s9) says «Pour : on en parle car on le vend partout en novembre.» The stance is
  telegraphic: the prompt's «for/against» comes back as a label. Lila (s10) also opens with «Pour :».

### F-4 · Romy offers what the sources do not have (s5, turn 3)
After «Les sources ne le disent pas», Romy says «Tu veux que je t'explique qui sont les
favoris ?». No claim names a favourite. The service-offer check runs on guests only. Romy's offers
are rare: 1 in 42 replies here, and 1 in s2 of the iteration run.

### F-5 · Answers that skip what is already on the table (s1 turn 2, s2 turn 2; pass with notes)
«Le gaz coûte combien maintenant ?» gets the bill increase (c2), because the price itself (c1) was
said a turn earlier and must not be restated. The prompt allows a reference in a few words, and
Romy did not make one. The same happens in s1 with the pensions (c2).

### F-6 · Cost above the per-session ceiling in 3 sessions
s1 ($0.0205), s3 ($0.0206) and s5 ($0.0220) are over US$0.02. The mean is $0.0171. The longer reply
prompt and reasoning tokens make each reply cost more than in the first sample (reply calls: 42 in
both runs). s5 also paid for 2 regenerations.

### Vocabulary
Credited evidence rose from 1 to 8 of 40 turns. Proper nouns, contractions, numbers, months and
grammar words no longer appear. What is left:

- Conjugated verbs and adjectives from the top-up: «courent», «chevaux» (s5), «compte» (s7),
  «publics» (s8), «retiré», «première» (s3).
- One wrong sense: «partir» from «à partir de» (s4).
- Two catalogue matches by form rather than meaning: «la gauche» (politics) credited to
  `CD_A12_DIRECTIONS` (s8), and «le nouveau» (s9) to the housing can-do.

The first point is addressed after the run (see Method). The other two are not.

### Grounding
Every fact Romy states traces to a claim or an uncertainty, except:

- the misattribution in s4 (F-1);
- the offer about favourites in s5 (F-4);
- Margaux's vegetables in s6 (F-3).

The first sample's s10 slip (the 2016 figure in a 2026 frame) is gone: «(constat de 2016)».

## What remains

1. **Restatement in the text** (F-1, F-5): check a reply's sentences against the shown claims
   (content-word overlap with a shown claim's `fr`). On a hit, either ask for a short reference
   instead or regenerate.
2. **Guest facts** (F-3): run the guests' assertive sentences through the same overlap test
   against claims and uncertainties. Give the stance prompt the angle's question («pour ou contre
   …»), so the side is about the story and is said in a sentence, not as a label.
3. **Romy's offers** (F-4): apply `voice.is_service_offer` to Romy too, but only for offers of
   content that is not in the claims.
4. **Cost** (F-6): the reply context could drop the knowledge rows that the Knowledge check
   refuses anyway. The guest and question calls could run at `reasoning_effort="minimal"`. Measure
   the effect before changing either.
5. **Vocabulary**: measure the post-run top-up. Map catalogue words by sense for the few
   homographs («gauche», «nouveau»), or leave them `capability_known=False`.
