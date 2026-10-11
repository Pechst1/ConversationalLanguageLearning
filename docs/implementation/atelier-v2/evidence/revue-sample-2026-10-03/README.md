# WP-119 §10d · Real-model sample, 2026-10-03

Ten Papier sessions with the real provider and the real critic, read by hand. No expected-failure
markers; what fails is reported as failing.

## Method

- **Harness**: `revue_sample.py` (a copy of the scratchpad script). It builds a throwaway SQLite
  database (every table of `Base.metadata`, the PG types compiled to SQLite), overrides
  `DATABASE_URL` in the environment so the `.env` database is never opened, and asserts that it
  did. The OpenAI key comes from `.env` through `app.config.settings` and is never printed.
- **Kiosk**: `weekly.available_for_week("2026-W40")` (the six live dossiers) plus four evergreens
  (`marche-du-dimanche`, `greve-transports`, `beaujolais-nouveau`, `rentree`). One new user per
  session (one Papier per learner per week). Bands come from `cefr_estimate`: A1 ×3, A2 ×4, B1 ×3.
  Gloss and translation languages are `en` or `de`.
- **Code path**: `RevueEncounter(db, provider)` with `OpenAIRevueProvider` subclassed **only** to
  record each `ask_json` call (label, seconds, cost, payload, response). The critic is
  `scorer_for(provider)` = `LLMRubricScorer`. `season_position` is real: a learner with no serial
  thread is checked against `s1` with the global must-not list. The vignette's pictogram provider
  is set to `FakePictogramProvider`, because the stamp is outside §10d's scope.
- **Script per session**: `start` → «D'accord, je t'aide.» → a question the dossier answers → a
  question only an uncertainty covers → a short opinion plus one use of the plan's first le/la
  target word (correct in 7 sessions, with the wrong article in sessions 2, 5 and 8) →
  `make_options` → the recommended option (reader_question: `propose`, then `send` of the
  proposal; headline_choice: pick the answer) → `close`.
- **Models and prompts**: `OPENAI_MODEL=gpt-5-mini`, `reasoning_effort="low"`, `max_tokens=1600`,
  JSON mode. Romy, guest, vocabulary, headline, question and close temperature 0.4. Critic
  temperature 0.0. Prompt versions: the encounter prompts (`encounter._SYSTEM` and `_TASKS`) **carry
  no version constant**; their content hash at HEAD 914692f is `d9b68538d1f6`. The rubric is
  `revue-rubric-v1` (critic prompt hash `d0ed057abbf0`). The dossiers are `revue-v1`. No call fell
  back to the secondary provider, and no call errored.
- **Records**: `sessions/NN.json` holds the dossier, plan vocabulary, every turn's `RvTurnResult`,
  the make offer and result, the closing (dispatch and kept), the final thread (every item kind),
  all state events, the evidence events, the guest events, `state.cost_usd`, and every model call
  with timing, payload and raw response. `verdicts.json` holds the per-session verdicts and notes.

## Totals

| | |
|---|---|
| Cost | **US$0.157** for 10 sessions (`state.cost_usd` equals provider spend in every session); mean **$0.0157**/session, min $0.0123, max $0.0200 |
| Calls | 118 (vocabulary 10, reply 42, guest 20, critic 17, headline 10, question 9, close 10); 0 errors |
| Latency per call | p50 **3.8 s**, p95 **8.2 s**, max 11.8 s (reply p50 4.6 / p95 8.0; vocabulary p50 8.0 / p95 11.7) |
| Latency per learner action | start p50 8.1 s / p95 11.7 s; turn 1 p50 5.1 s; turn 2 p50 6.7 s; turn 3 p50 7.6 s; **turn 4 p50 11.3 s / p95 14.9 s / max 16.6 s** (reply, guest and critic run in sequence); make_options p50 5.1 s; close p50 4.4 s |
| Simplify | 0 support changes, 1 false breakdown counted (session 6) |
| Knowledge | 0 must-not hits in 118 responses; 0 refusals. The check was never exercised because no turn probed it (see below) |

## Verdicts

| # | Dossier | Band | Cost | French | Grounding | Guest voice | Rubric | Simplify | Knowledge | §1 acceptance |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | budget-2027 | B1 | $0.0164 | FAIL | pass | partial (Gus) | pass | pass | pass | pass |
| 2 | ce-qui-change-1er-octobre | A2 | $0.0143 | FAIL | pass | partial (Marchand) | pass (incorrect→incorrect) | pass | pass | pass |
| 3 | goncourt-roman-retire | B1 | $0.0200 | FAIL | pass | partial (Lila) | pass | pass | pass | pass |
| 4 | paris-plan-canicules | A1 | $0.0157 | FAIL | pass | FAIL (Marchand) | pass | pass | pass | pass |
| 5 | prix-de-l-arc-de-triomphe | A2 | $0.0174 | FAIL | partial | partial (Gus) | pass (incorrect→incorrect) | pass | pass | pass |
| 6 | prix-produits-frais | A1 | $0.0157 | FAIL | pass | partial (Margaux) | pass | **warn** | pass | **FAIL** |
| 7 | evergreen marché | A2 | $0.0149 | FAIL | pass | n/a | pass | pass | pass | pass (weak) |
| 8 | evergreen grève | B1 | $0.0142 | FAIL | pass | n/a | pass (incorrect→incorrect) | pass | pass | pass |
| 9 | evergreen beaujolais | A1 | $0.0123 | FAIL | pass | pass (Margaux, entry only) | pass | pass | pass | pass |
| 10 | evergreen rentrée | A2 | $0.0158 | FAIL | partial | pass (Lila, entry only) | pass | pass | pass | pass |

Per criterion: natural French **0/10**; grounding 8/10 (2 partial); guest voice 2 pass, 5 partial
and 1 fail of 8 sessions with a guest; rubric **10/10**; simplify 9/10 (1 warning); knowledge 10/10
(not stressed); acceptance **9/10**.

## Failures, with quotes

### F-1 · Claim, uncertainty and angle ids are spoken to the learner (40 of 40 replies)
Every reply Romy shows contains a dossier id. Some examples:
«Il y en aura cent, d'après c2.» (A1, s4) · «Merci. D'après c1,c2,c3, les prix montent» (A1, s6) ·
«Les sources ne disent pas de combien exactement les pensions seront revalorisées (incert. 1).» (s1) ·
«On commence par «Ce que la rentrée change pour une famille» (a1).» (s10) ·
«Donne deux voix : le ministre (interprétation c3) et La finance pour tous (interpretation c4).» (s1).
The tags also reach the translations («laut c3», «according to c2»). In s4, s6, s9 and s10 the id
takes the place of the attribution: «d'après c4» names no source, and §5.3 wants interpretations
introduced as such («d'après plusieurs vignerons…»). Cause: the reply task says «Cite claims by id when
you use them» and also has a `claims_cited` field, and no deterministic check strips or refuses an
id in `reply_fr`.

### F-2 · The uncertainty is a list index, and an off-by-one breaks the acceptance test (session 6)
The learner asks «Quels légumes sont plus chers ?», which is uncertainty 1 of a 2-item list.
Romy answers «Les sources ne disent pas quels légumes ont le plus augmenté (incertitude 2).» She
names the gap correctly, but `uncertainty_cited=2` is out of range, so `_parse_reply` drops it. The
question is recorded `answerable=True`, the make offer recommends `headline_choice`, and the close
keeps no question (`question_kept_fr=None`). The model's indexing is inconsistent: 0-based in most
sessions, and in s6 `1` for that uncertainty on turn 1, then `2` on turns 3 and 4.

### F-3 · Romy does not converse: she recites, repeats and pushes the reader question
- **Fact dump at «D'accord»**: 9 of 10 first replies put 3–4 claims on the table at once, against
  «one or two at a time» in §5.3. Examples: «Seize partants (c1). La course fait 2 400 m, ~2
  minutes à >60 km/h (c2). Dotation 5 M€, 2,8 M€ au vainqueur (c3). Daryz…» (A2, s5).
- **Telegraphic symbols at A1/A2**: «Plafond franchises médicales 100→140 € (c3)», «le chèque
  vaut ≈0,40 €/L» (A2, s2), «rentrée 2026: 1er sept. en métropole» (A2, s10).
- **Meta-instructions, as if the learner were writing**: «Propose la question au lecteur… Dis que
  le gouvernement… Précise que… Donne deux voix» (s1), «Parfait. Dis-lui: Paris a 91 marchés»
  (s7), and «Merci. Dis : «Pourquoi tout le monde parle du beaujolais nouveau en novembre?»
  D'après c1 et c2.» (A1, s9, a first reply with no content at all).
- **Repetition**: in s2, c1 and c2 are restated in all three later replies. In s8, the same
  unrelated reader question («Que faut‑il prévoir pour mon trajet le jour d'une grève ?») is pushed
  three times. 33 of 40 replies propose a reader question.
- **Opinions get no answer**: «Je trouve ça cher.» gets the gas price again (s2), and «J'aime le vin
  rouge.» gets c4 (s9).
- **Wrong addressee**: «Veux‑tu que je rédige une question claire pour tes élèves ?» (s3). The
  pupils are Lila's.
- **French typography**: «Dis-lui:», «On propose:», «en novembre?»».
- **Jargon in the close**: «Je garde ta question telle quelle dans l'artefact.» (s9), «je ferme la
  session» (s1), and «ta question et ton texte» when no text exists (s10).
- **Relative dates**: none found in Romy's or the guests' lines. The two guards held.

### F-4 · Guests are helpful assistants, not characters, and never take a side
Of 20 guest lines, 0 set a `position` and 0 used `disagree` or `moved`. §7's «disagree, change their
mind» never happens. Of 12 follow-up lines, 8 are offers to do something for the learner:
«Voulez-vous que je demande au maire combien coûte le plan ?» (Marchand, s4, twice in one session),
«Voulez‑vous que je vous montre comment regarder la vitesse, la dotation et Daryz…» (Gus, s5,
twice), «Tu veux que je cherche lesquels ont monté ?» (Margaux, s6, twice; she «uses the fewest
words in the cast»), and «Tu veux que je vérifie si le Renaudot a publié un communiqué…» (Lila, s3).
Entry lines are mostly in voice: «Je dîne avec des gens de l'autre camp — c'est passionnant. Non :
fascinant.» (Gus), «Je gère des immeubles dans le dixième. […] voyez-vous.» (Marchand), «Ce que je
sers au comptoir vient de quelque part.» (Margaux). One follow-up is incoherent: «Vous avez une
offre indexée pour le gaz, ou c'est vos locataires qui paient la facture ?» (Marchand to the
learner, s2). Lila's entry is near-verbatim the same in s3 and s10. None of world.json's markers appear:
no Marseille exclamation or «sur vingt» from Lila, no procedure or «recommandé» from Marchand.

Guest line judgements against world.json, one per guest appearance:

| Session | Guest | Judgement |
|---|---|---|
| 1 | Gus | entry in character (superlatives that grow); follow-ups out (assistant offer, voiceless clarification) |
| 2 | Marchand | entry in (vous, voyez-vous, his buildings); follow-up 1 neutral; follow-up 2 out (incoherent) |
| 3 | Lila | entry in (tu, her class); follow-up 1 out (assistant offer); follow-up 2 in (looks at the evidence) |
| 4 | Marchand | out: two «Voulez-vous que je demande au maire» offers, no voice |
| 5 | Gus | entry in («Je sais toujours qui paie, croyez‑moi.»); follow-ups out (the same offer twice) |
| 6 | Margaux | entry in (few words, the counter); follow-ups out (the same research offer twice) |
| 9 | Margaux | in |
| 10 | Lila | in, but a near-verbatim repeat of s3's entry |

### F-5 · Vocabulary picks words the evidence cannot use
Target words included «Paris», «l'Insee», «du Renaudot», «aux familles», «de l'énergie», «compte»
(conjugated), «faire», «L'écrivain», «le Qatar Prix de l'Arc de Triomphe» and «Le marché d'Aligre»:
proper nouns, contractions taken for articles, and conjugated forms, against the task's «nouns with
their article, or infinitive verbs». Only **1 of 40** learner turns produced a credited outcome on a
known capability («les marchés» → `CD_A11_GOING`, a loose fit for «aller, venir, marché…»). Every
other correct use was judged correct and then credited `unscored` because the word is outside the
can-do catalogue. That is right by the Credit check, but it means the Revue writes almost no usable
evidence.

### F-6 · The reader question has no referent, and it becomes the dispatch headline
The question rewrite keeps the learner's words but does not add what the question is about: «Le
plan coûte combien ?» (s4), «Qui va gagner ?» (s5), «C'est moins cher qu'au supermarché ?» (s7,
sent unchanged). In 9 of 10 dispatches that bare question is `headline_fr` under «Le Papier de Romy ·
semaine 40», because `close` uses the artifact text as the headline for every kind except
`short_report`.

### F-7 · Angle oscillation and one false breakdown
- The model returns `shift: "angle"` on «D'accord, je t'aide.» and on most later turns. 7 of 10
  sessions flip a1↔a2 two or three times (21 angle choices in total). This changes the angle that
  the guest, headline and close contexts read.
- In s6, the opinion «C'est difficile pour moi.» (about prices) came back as `shift: "simplify"`
  and was counted as a breakdown (`counts=True`). One more such turn would have lowered the support
  level for a learner who understood perfectly.

### Grounding (partial in 2 sessions)
Every factual sentence Romy said traces to a claim or an uncertainty, except:
- s5: «Non, pas très longue.» is an evaluation no claim makes, and «2,8 M€ au vainqueur» drops c3's
  «plus de».
- s10: «D'après c4, les dépenses ont augmenté.» is said in a 2026 frame and drops the 2016 dating
  that the dossier's own uncertainty insists on.

The guests' facts («La dotation est de 5 millions, 2,8 pour le vainqueur») are grounded.

### Knowledge check
- No line matched Odile, Berlin, 310 000, Solvel or the letter. No line was refused.
- **Not stressed**: no learner turn probed a reveal, and the global must-not list has only three
  patterns. The prompts do carry season material:
  - Romy's knowledge context includes world.json's role «investigating Solvel's purchases of cafés»
    in every reply of s1–s6.
  - Margaux's context includes «as she did with Odile».
  - Marchand's context includes «la succession Ferrand».
- Nothing leaked, but the absence of a leak here is not evidence that the check would stop one.

### Rubric (fair on every target-word use)
- Correct uses were judged `correct` in all 7 sessions with a correct use.
- Wrong-article uses («la prix repère», «la Qatar Prix…», «la service») were judged `incorrect` in
  all 3.
- No mastery was claimed with `capability_known=False`: `credited()` turned every unknown-capability
  `correct` into `unscored`.
- `fact_fit` was sensible: «C'est bien pour les enfants» → unsupported; «l'école coûte trop cher» →
  supported.
- The critic was called only on turns that contained a target word (17 calls).

## Recommendations, ranked

1. **Never show an id.** Change the reply prompt to «reply_fr never contains ids; attribute
   interpretations to their `attributed_to`». Add a deterministic `id_in_text` check
   (`\(?\b[cau]\d+\b\)?`, `incert\w*\.? ?\d`) that retries once and then strips. Apply it to reply,
   guest, close and question text, and to `translation`. This fixes 100 % of replies.
2. **Give uncertainties stable ids (`u1`, `u2`) and resolve them by id.** Add a fallback: when the
   reply says the sources are silent and no valid id came back, match the learner's question to an
   uncertainty by content-word overlap. This turns s6 into a pass and makes §1 robust to the
   model's indexing.
3. **Rewrite the reply task as a conversation turn.**
   - Answer the learner's last line first, and react to an opinion.
   - Show at most two new claims per reply, and do not restate claims in `claims_shown`.
   - Propose the reader question at most once, and only after an uncertainty was named.
   - No instructions to the learner («Dis…»).
   - No →, ≈, ~, M€ or «/MWh» at A1/A2; French typography.
   - `shift: "angle"` only when the learner's words fit the other angle better, never on a meta
     line (`_META_LINES`), and at most once per session.
   - `simplify` only on comprehension trouble, not on an opinion about difficulty.
   - Add a prompt version constant (`revue-encounter-v1`) and record it on each turn.
4. **Guests take a side and keep their voice.**
   - On entry, require `position` for or against, grounded in a claim.
   - Forbid «Voulez-vous que je… / Tu veux que je…» offers.
   - Add a near-duplicate check against the guest's own earlier lines.
   - Give `personality` and one authored sample line per guest more weight than the knowledge
     rows.
5. **Vocabulary**:
   - Reject proper nouns, capitalised entries, contractions («du», «aux», «de l'») and non-infinitive
     verbs deterministically.
   - Prefer words in the can-do catalogue, so that a correct use can become credited evidence.
6. **The reader question should stand alone.** The question task should add the referent («le plan
   canicule de Paris»), and the dispatch should keep the dossier headline with the question as a
   «Question aux lecteurs» line, not as `headline_fr`.
7. **Latency**: the fourth turn takes 11–17 s. Run the critic concurrently with the reply and guest
   calls, or after the response. Precompute and cache the vocabulary per dossier, band and language,
   which removes ~8 s from `start`.
8. **Close copy**: forbid app vocabulary («session», «artefact») and claims about contributions
   that do not exist («ton texte»).
9. **Stress the Knowledge check** in a follow-up sample. Add a learner turn per session that asks
   Romy about Solvel, the price and Odile's letter, and decide whether world.json's `role` and
   `register_with_user` texts (Solvel, Odile, Ferrand) should reach a Revue prompt at all.

Cost is not a problem: $0.016 per session, 10 sessions for $0.16.
