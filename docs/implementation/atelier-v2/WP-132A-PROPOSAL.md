# WP-132A — two story beats (proposal, 2026-10-04)

**Status: proposal for the owner's approval. No story text is committed.** The bible lines and level variants below exist only in [WP-132A-PROPOSAL.patch](WP-132A-PROPOSAL.patch). The validator support they need is committed, and it does nothing until the data changes (`scripts/season_levels.py`, `tests/test_wp132a_validators.py`).

Sources: review §2.3 F-6 and §6, owner decision 7 ([EXPERIENCE-REVIEW-2026-10-04.md](EXPERIENCE-REVIEW-2026-10-04.md)), package WP-132 «A» ([WORK-PACKAGES-2026-10-04-experience.md](WORK-PACKAGES-2026-10-04-experience.md)), and [SEASON-LEVELS.md](SEASON-LEVELS.md).

**To apply after approval:** run `git apply docs/implementation/atelier-v2/WP-132A-PROPOSAL.patch`, then the two validators below. The patch touches `app/data/season/s1/t2.json`, `levels_a.json`, `levels_b.json` and the bible `docs/story/season-1/02-la-haut.md`. The source/approval record and the data change together.

---

## 1. T2 day B: the «double» gets an answer on the page (F-6)

**Today.** In T2 day B (`t2.json:1055`, solve `b.key`, mechanic `choix`), Lila asks «Tu me prêtes une clé ?». The option «Pas encore» has a beat (`b.key.pas_encore.r1`, «Pas encore. D'accord. J'aime bien "encore".»). The option «Lui faire un double» (`t2.json:1070`) sets `s1.lila_has_key = true` and has no beat. The learner who gives the key sees «…», and the day ends.

**Proposed.** Add one beat to option `double`: panel `b.key.double.r1`, with no new `visual` (it keeps P8's framing at the door). Lila says one line, `mood: happy`. The direction is «her hand closes on nothing, as if the key were already in it». Directions are for the art and the owner; the reader does not print them, so the line itself carries the reaction.

| Level | Where it lives | French | en | de |
|---|---|---|---|---|
| A2 (bible) | `t2.json` `…b.key.options[double].beats[0].lines[0].say.a2` | Un double… pour moi ? Sept heures, alors. Tu ne m'entendras pas. | A copy… for me? Seven o'clock, then. You won't hear me. | Ein Zweitschlüssel… für mich? Also um sieben. Du wirst mich nicht hören. |
| B1 (bible) | same `say.b1` | Un double… rien que pour moi ? Alors à sept heures. Promis, tu ne m'entendras même pas. | (B1 reads without a translation) | |
| A1 | `levels_a.json` `lines.9d8f939acdaa.a1` / `a1_native` | Un double ? Merci. Sept heures. Toi, tu dors. | A copy? Thank you. Seven o'clock. You'll be asleep. | Ein Zweitschlüssel? Danke. Sieben Uhr. Du schläfst dann. |
| B2 | `levels_a.json` `lines.9d8f939acdaa.b2` | Un double… pour moi ? Va pour sept heures. Je serai discrète : tu ne m'entendras pas. | — | — |
| C1 | `levels_a.json` `lines.9d8f939acdaa.c1` | Un double… rien qu'à moi ? Sept heures, donc. Je serai plus discrète qu'une souris. | — | — |

The bible gets the same line. `02-la-haut.md:155` reads «→ `s1.lila_has_key = true`. LILA *(her hand closes on nothing, as if the key were already in it)* · A2 «…» · B1 «…» In gap 2 she starts painting here at 7 a.m. …», so `season_check` keeps the bible and the data in step.

**Why this wording, and not the review's.** The review suggested «Un double… *(elle le serre dans sa main)* Sept heures. Tu ne m'entendras pas.». But the card says «Lui faire un double»: the copy is still to be made, so Lila cannot hold it yet. Her hand closing on nothing keeps the gesture and stays true. «pour moi ?» gives the moment the weight the «Pas encore» branch already has. Neither branch is cold, as the bible's note asks.

**Consequence trace (nothing downstream changes):**
- **Flag.** `s1.lila_has_key = true` is unchanged (`t2.json:1079`; `season.json:41`: set in T2 B, read in the gaps, T5 B location and T8 F4).
- **Gap 2.** «Sept heures» is exactly the gap brief:
  - `gaps.json:144` `by_flag.s1.lila_has_key.true`: «paints in Odile's flat at 7 a.m. before school»;
  - `gaps.json:99` and `:141`;
  - `t2.json` `for_next_gap`: «in gap 2 she starts painting in the flat at 7 a.m., and you find her coffee cup in the sink»;
  - `t3.json:10`.

  «Tu ne m'entendras pas» sets up the cup in the sink: she came and went while you slept.
- **T5 B.** With the key, Berlin is discovered in Odile's flat (`t5.json:826`, `:1016`), where she paints in the mornings. The line makes that location expected rather than arbitrary.
- **T8 F4.**
  - Romance with the key (`t8.json:1450`): she keeps it, «Je la garde. Pour revenir.».
  - Friendship with the key (`:1485`): she gives it back.

  The hand closing on the not-yet-key in T2 is the first half of that gesture. The no-key variants (`:1464`, `:1504`) are untouched.
- **Rendering.** `page._option` already serves option `beats` (as for «Pas encore»), and `runtime.py:259/283` plays them. A render check at A1.1/A2.1/B1.1/B2.1/C1.1 served the right French at each band, the A1 line with its own translation and the A2 line with its own; B1+ gets no translation, as designed.

**Validator result.** See §3.

---

## 2. A1: Odile's past reads as past

**Today.** The A1 rule «present and futur proche only» (SEASON-LEVELS.md) makes a woman who left in April 2023 and died in 2026 (bible §2) read as if she were alive, or leaving now. Examples: «Pourquoi elle part, Odile ?» and «Odile sait une chose sur Lila».

**Proposed.** Allow three glossed past chunks at A1, «elle est partie», «c'était» and «elle savait», with the subject «elle» or «Odile» only. Use them only where the present misleads. Each changed A1 line carries its own `a1_native` (en, de). That translation is the gloss: `Say.native_served` shows the translation of exactly the A1 French served beside it. Only the `a1` field changes; A2, B1, B2 and C1 are untouched. The bible is untouched too, because A1 variants live in `levels_*.json`.

I read every A1 variant whose A2 line, or the A1 line itself, refers to Odile, her departure or her past (script: every `say` matching Odile / grand-mère / partir / past forms of «elle», in all nine files).

### 2.1 Changed (11 lines)

| # | File (A2 source) · level key | Speaker / place | A2 (bible, unchanged) | A1 today | **A1 proposed** | en | de | Chunk |
|---|---|---|---|---|---|---|---|---|
| 1 | `t2.json:159` · `levels_a.json:651` `8fc9b9dfbe87` | Lila, day A p5, the rumour | En bas, tout le monde dit : "Elle est rentrée chez sa famille. Elle voulait partir depuis longtemps." | En bas : "Elle veut partir depuis des mois." | **En bas, on dit : "Partir, c'était son idée."** | Downstairs they say: "Leaving was her idea." | Unten heißt es: "Wegzugehen war ihre Idee." | c'était |
| 2 | `t2.json:175` · `levels_a.json:660` `749219271c9c` | enquête prompt | «Elle avait tout prévu ?» Montre. | Elle veut partir ? Montre. | **C'était son idée ? Montre.** | It was her idea? Show me. | Es war ihre Idee? Zeig es mir. | c'était |
| 3 | `t2.json:288` · `levels_a.json:741` `7a7fc80c9768` | Lila, turn a.turn1 | Alors ? Pourquoi elle est partie, à ton avis ? | Alors ? Pourquoi elle part, Odile ? | **Alors ? Pourquoi elle est partie, Odile ?** | So? Why did Odile leave? | Also? Warum ist Odile gegangen? | elle est partie |
| 4 | `t2.json:538` · `levels_a.json:831` `7e4271f31265` | caption, day A hook | Odile savait quelque chose sur Lila. Lila ne dit rien. À suivre… | Odile sait une chose sur Lila. Lila, silence. À suivre… | **Odile savait une chose sur Lila. Lila aussi. À suivre…** | Odile knew something about Lila. So does Lila. To be continued… | Odile wusste etwas über Lila. Lila auch. Fortsetzung folgt… | elle savait |
| 5 | `t2.json:886` · `levels_a.json:966` `3fd4cd99849b` | Lila, day B p6, the notebook | Elle voulait acheter le Mistral. Avec tout le monde. Marin va devenir fou. | Elle veut acheter le Mistral. Avec nous. Marin va adorer. | **C'était son idée. Le Mistral à nous. Marin va adorer.** | It was her idea. Le Mistral, ours. Marin is going to love this. | Das war ihre Idee. Das Mistral, unseres. Marin wird das lieben. | c'était |
| 6 | `t2.json:1134` · `levels_a.json:1083` `6e1789e7fe4a` | caption, day B hook | Odile avait un plan pour le Mistral. Et une question pour Lila. À suivre… | Odile a un plan. Une question pour Lila. À suivre… | **Odile : un plan. Une question pour Lila. À suivre…** | Odile: a plan. A question for Lila. To be continued… | Odile: ein Plan. Eine Frage an Lila. Fortsetzung folgt… | none (no verb) |
| 7 | `t1.json:206` · `levels_a.json:192` `88291ad8517b` | Margaux, a.turn2 | Elle ne donnait jamais cette clé. | Odile ne donne pas cette clé. À personne. | **Cette clé ? Avec Odile, c'était non. À personne.** | This key? With Odile, it was no. Not to anyone. | Dieser Schlüssel? Bei Odile hieß es nein. Für niemanden. | c'était |
| 8 | `t3.json:672` · `levels_a.json:1371` `bb8bc81227f0` | Marin, b.turn1.c | Justement. C'était son plan. Regarde. | Oui, voilà. C'est l'idée d'Odile. Regarde. | **Oui, voilà. C'était l'idée d'Odile. Regarde.** | Yes, exactly. It was Odile's idea. Look. | Ja, genau. Das war Odiles Idee. Schau. | c'était |
| 9 | `t3.json:680` · `levels_a.json:1380` `7ddbf002eb1a` | Marin, b.turn1.c | Elle me connaissait. | Odile me comprend. | **Odile savait tout de moi.** | Odile knew everything about me. | Odile wusste alles über mich. | elle savait |
| 10 | `t4.json:145` · `levels_a.json:1632` `60e2d4537a95` | Lila, the Polaroid wall | Ta grand-mère voyait tout. Même ça. | Ta grand-mère voit tout. Même ça. | **Ta grand-mère ? Elle savait tout. Même ça.** | Your grandmother? She knew everything. Even that. | Deine Großmutter? Sie wusste alles. Sogar das. | elle savait |
| 11 | `t8.json:169` · `levels_b.json:1947` `66e45f5ae64c` | Marchand, e1.a.turn1.b | Elle non plus, elle ne savait pas. Elle est restée quatorze ans. | Odile aussi, au début. Et elle reste quatorze ans. | **Odile aussi, au début. Après, c'était quatorze ans ici.** | Odile too, at first. Then it was fourteen years here. | Odile auch, am Anfang. Danach waren es vierzehn Jahre hier. | c'était |

**What stays intact:**
- **Clues.** The T2 enquête still contradicts the rumour. «Partir, c'était son idée» / «C'était son idée ?» is the claim the 3 May pie disproves, exactly as «Elle avait tout prévu ?» was at A2. The answer set (calendar entries) is untouched.
- **Branch meaning.** Lines 8 and 9 are Marin's answer on the co-op branch (b.turn1.c); his meaning holds. «Le Mistral à nous» (5) is the notebook page's own title (`for_next_gap`), so A1 now names the plan the gaps and T3 use.
- **Dates.** «quatorze ans» (2009 → 2023), 3 May, 14 March and «1 h 30 / 23 h» are kept. No changed line touches a date.

**Line 4 is a small meaning shift.** «Lila aussi» is shorter than «Lila ne dit rien», which uses `ne … rien` (above A1), or «Lila, silence» («silence» is outside the A1 list, and a chunk takes the line's one outside word). It says Lila knows too, which is true (bible §3: the 2021 offer, «Elle part ou elle reste ?»), and it keeps the hook. If the owner prefers silence over knowledge, «Odile savait une chose. Lila, silence. À suivre…» passes only if «silence» is accepted as the line's outside word *instead of* the chunk. That is not possible under the rule as proposed.

### 2.2 Read and deliberately left unchanged

| Level key (A1 today) | Why it stays |
|---|---|
| `2bad939c3077` (t4, Margaux's easy-read account: «Un mois après, ta famille vient ici… Odile part avec eux…») | A narrative in the historical present, anchored by «Un mois après» and «Cette nuit-là». Changing one verb would mix tenses inside an easy read. |
| `349434b40cd7` (t4, Marchand: «…pendant des années, je pense : elle part, et c'est ma faute.») | The present is his quoted thought at the time, which is correct French at any level. |
| `0e5076066e57` (t6, Marchand: «Le 13 mars, je dis… Et elle part.») | A dated easy-read narrative in the historical present; same reason as `2bad939c3077`. |
| `5aaec44a205e` (t8, Odile's last letter) | Odile writes in her own present, so the present is right in a letter. A trial with «C'était bien aussi. C'était une autre chose.» failed the rule: the letter already spends its one outside word on «tableau», and the clue «Cherche derrière le tableau du Mistral» must stay. |
| `69c4759cb0aa` (t6, «Pourquoi elle part ? Vous savez, vous ?») | **Candidate, not changed:** «Pourquoi elle est partie ? Vous savez, vous ?» passes the validator (checked: 0 problems, reported as a t6 chunk line). I left it out only to keep the first change small; owner's call. |
| `817e4d7417ed` (t4, Marchand: «Là-bas… Et moi ? Elle dit mon nom ?») | **Candidate, owner's call:** «Là-bas… Et moi ? Elle savait mon nom ?». It reads past, but it shifts «did she speak of me» toward «did she still know me». That is poignant after «Elle oublie des choses» two lines earlier, but it is a change of meaning. It passes the validator (checked: 0 problems). |
| t6 déchiffrer answers «Elle oublie, et elle a honte» / «Elle veut partir» / «Elle n'aime pas M. Marchand» | Answer sets are fixed (SEASON-LEVELS.md), and they read Odile's notebook, which she wrote in her present. |
| «Ma grand-mère dit…» (t1 `0b8a00924507`, t3 `012a9b543053`, t8 `dde2f8273c33`) | The speaker's own grandmother, not Odile. |
| Season question `28c28d1160e4` («Ta grand-mère te donne son appartement…») | The inheritance, not the departure; it reads correctly. |

### 2.3 Learner support for the chunks

- **Translation beside every changed line.** That is the gloss.
- **Optional, not in the patch:** tentpole `lexicon` rows, such as T2 day A `{"surface_fr": "est partie", "lemma": "partir", "gloss": {"en": "(she) left", "de": "(sie) ist gegangen"}}` and `{"surface_fr": "c'était", "lemma": "être", "gloss": {"en": "it was", "de": "es war"}}`. «combien de temps» sets the precedent for multiword entries. But `runtime._lexicon` serves only the first five entries found in the page, and T2 day A already has five or more, so adding them displaces scene words in the day's drills. If the owner wants the chunks drilled, the place is the top of the list, at the cost of one scene word each.

---

## 3. Validators

### 3.1 Change to `scripts/season_levels.py` (committed, `6da2995`)

A narrow, documented phrase exception, `A1_PAST_CHUNKS`:

- **Scope.** A1 variants only. Three patterns: `(elle|Odile) est partie`, `c'était`, `(elle|Odile) (ne )?savait`. Nothing else is masked: «il est parti», «elles sont parties», «elle était», «elle a dit» and «Marin savait» all still fail.
- **Detectors.** Each chunk is rewritten to its present form (`elle part`, `c'est`, `elle sait`) before the above-band grammar detectors run. The rest of the line stays fully checked: «Elle est partie. Il était triste.» still fails `FR2_A22_IMPARFAIT`.
- **Coverage.** Words are counted one by one on the real text, never as one token: «est partie» is two running words. The chunked lines are listed apart («glossed A1 past chunks (lines)»), so token coverage and supported chunks are reported separately.
- **Budget.** At most one distinct chunk per line, and the chunk takes the line's one word outside the A1 list. A chunk line with any other outside word fails. That is why lines 1 and 4 and the letter were reworded or dropped.
- **Inert today.** On the current data the output is identical to before (0 problems, no chunk section).

Tests: `tests/test_wp132a_validators.py` (18 cases): masking per chunk, nothing else masked, other past forms still detected, a full-script run on a scratch copy of `s1` (passes, reports apart, coverage grows by the chunk's real word count), and three narrowness failures (two chunks; chunk plus an outside word; an un-listed past form).

### 3.2 Results on the proposed text

Applied temporarily (`git apply` equivalent on the working copy), then restored (`git status` clean for `app/data/season/s1` and `docs/story`).

**`venv/bin/python scripts/season_check.py`**: all ok, the bible and data in step (the new bible line is carried verbatim).
```
t1: ok
t2: ok
t3: ok
t4: ok
t5: ok
t6: ok
t7: ok
t8: ok
```

**`venv/bin/python scripts/season_levels.py --todo --strict`**: exit 0, «0 problems», «still to write:» empty.

A1 coverage (known running words), before → after:

| File | Before | After | Chunk lines |
|---|---|---|---|
| season | 97.9 % of 48 | 97.9 % of 48 | — |
| t1 | 95.6 % of 361 | 95.6 % of 362 | 1 (`88291ad8517b`) |
| t2 | 95.7 % of 304 | 95.9 % of 315 | 5 (`8fc9b9dfbe87`, `749219271c9c`, `7a7fc80c9768`, `7e4271f31265`, `3fd4cd99849b`) |
| t3 | 95.1 % of 426 | 95.1 % of 428 | 2 (`bb8bc81227f0`, `7ddbf002eb1a`) |
| t4 | 95.4 % of 689 | 95.4 % of 690 | 1 (`60e2d4537a95`) |
| t5–t7 | unchanged | unchanged | — |
| t8 | 95.4 % of 539 | 95.4 % of 540 | 1 (`66e45f5ae64c`) |

- **B2/C1 t2**, after the new beat's variants: b2 98.3 % of 479 (was 463), c1 98.1 % of 474 (was 458).
- **Every file stays above the 95 % floor.** t3 A1 is the tightest, at 95.1 %, and is unchanged.

**Iterations the validator forced** (kept for the record):

| Line | First draft | Rejected because | Final |
|---|---|---|---|
| A1 beat | «Tu dors, je peins.» | *peindre* and *double* are both outside the A1 list | «Toi, tu dors.» |
| Line 1 | «Elle est partie. C'était son idée.» | two chunks on one line | «Partir, c'était son idée.» |
| Line 4 | «…Lila, silence.» | a chunk plus an outside word | «Lila aussi.» |
| Line 9 | «Odile savait qui je suis.» | `FR2_A21_SAVOIR_CONNAITRE` and `FR2_B11_INDIRECT_QUESTIONS` fire on the present form too: a real structure, not a chunk artefact | «Odile savait tout de moi.» |
| Letter | «C'était bien aussi…» | a chunk plus «tableau» | dropped (§2.2) |

**Season tests with the proposal applied:** `pytest tests/test_season_one.py tests/test_season_levels.py tests/test_season_story_qa.py tests/test_wp98_99_season_horizon.py tests/test_wp_l7_level_coverage.py tests/test_story_correspondence.py` gave 132 passed, 1 skipped (SEASON_REPORT).

---

## 4. For the owner

1. **The T2 «double» beat**, all five levels (§1).
2. **The three A1 chunks and the eleven lines** (§2.1), including the small meaning shift in line 4 («Lila aussi»).
3. **The two optional candidates** in §2.2 (`69c4759cb0aa`, `817e4d7417ed`).
4. **Whether to drill the chunks** via the tentpole lexicon (§2.3), at the cost of one scene word each.

On approval: apply the patch, run both validators and the season tests, and add a line to SEASON-LEVELS.md under «How the A1 lines were written» naming the three chunks as the one exception to the present-tense rule.
