# Season level variants (T-2, content program 2026-10-03)

The bible lines stay in `app/data/season/s1/t*.json`; their a1 / b2 / c1 variants live in `levels_a.json` (season question, t1–t4) and `levels_b.json` (t5–t8), checked by `scripts/season_levels.py`.

## t1–t4 and the season question (`levels_a.json`, T-2a)

**Status 2026-10-03:** 243 lines × a1/b2/c1, and 52 example slots × 2 replies × a1/b2/c1 (315 replies).
`scripts/season_levels.py --file <season|t1|t2|t3|t4> --todo` reports 0 problems and 0 to write.
A1 coverage runs from 95.5 % to 97.9 % per file, B2 from 96.9 % to 98.5 %, and C1 from 95.6 % to 98.3 %. No `b1` variants were written, because the A2 line reads fine at B1.

How the A1 lines were written:
- Every A2.1+ detector counts as "above A1", so A1 lines use the present tense and the futur proche only. They avoid the passé composé, the imparfait, object pronouns before the verb, `ne … jamais/rien/plus`, `tout le/tous les`, `personne ne`, `quelqu'un/quelque chose`, adverbs in -ment, `premier/moitié/jusqu'à`, `pour + infinitive`, and `dans/depuis + number`. Odile's past is told in the present ("Odile ne donne pas cette clé. À personne.").
- Each A1 line is ≤ 10 words. Long speeches and documents get an easy-read version of 30 words or more (Marin's co-op pitch, Gus's account of the fire, Margaux's confession, the season question, the t4 hooks).
- The budget is one word per line outside the A1 list. Words like *vendre, feu, mur, garder, promesse, Solvel, Paris* and *Mistral* all count against it ("Mistral" and "Solvel" are not in the name list), so A1 often says "le café" for the Mistral.
- C1 detectors also apply to B2 and below, and some are coarse. `REGISTER_QUESTIONS` flags "Vous êtes qui ?". `NARRATION_LITERARY` flags any "<word> Lila" before a later verb. `PERCEPTION_INFINITIVE` flags "laisser partir/tomber". The affected lines were rephrased.

Kept fixed at every level: the enquête and déchiffrer evidence (the calendar entries, LARTSIM / la poêle / la fumée, "14 mars. 23 h.", 1 h 30 downstairs vs 23 h upstairs), names, dates, and the 8 January deadline. Lines addressed to Toi avoid agreement. For example, Gus's "Mystérieux" became "Un secret ! / Du mystère !", and "Mon cher, les photos mentent" was rephrased without "cher".

Simplified at A1 (the plot information holds; colour is lost):
- t1: Gus's duc line loses "pour ce siècle".
- t3: "Mille euros chacune" is dropped from Marin's co-op line, which keeps "deux cents amis, une banque".
- t3: The SMS no longer says "à l'ONG".
- t3: The two t3 hooks use «Deux "oui"» for «deux promesses».

## t5–t8 (`levels_b.json`, T-2b)

**Status 2026-10-03:** 281 lines × a1/b2/c1 and 63 example slots × 2 replies × a1/b2/c1 (378 replies). Keys already in `levels_a.json` (for example «Oui.») are not redefined.
`scripts/season_levels.py --file <t5|t6|t7|t8> --todo` reports 0 problems and 0 to write.

| File | a1 | b2 | c1 |
|---|---|---|---|
| t5 | 96.7 % | 99.1 % | 99.4 % |
| t6 | 95.7 % | 99.2 % | 99.0 % |
| t7 | 95.6 % | 96.7 % | 96.7 % |
| t8 | 95.8 % | 98.5 % | 98.4 % |

No `b1` variants were written. The same A1 rules as t1–t4 apply: present tense and futur proche, at most 10 words per line, an easy read of 30 words or more for long texts, and one word per line outside the A1 list. After the name-list change, *Solvel, Mistral* and *Berlin* no longer count against that budget.

**Letters and documents (easy read at A1):**
- T5: the Berlin residency letter and Lila's unfinished card. The card still ends on "et je".
- T6: Odile's 13/15 March notebook. "Margaux n'est pas responsable" carries the "ne la punissez pas" point, and the A1 *carnet* is a *cahier*.
- T8: Odile's last letter is told in the present. The clue «Cherche / regarde bien derrière le tableau du Mistral» is kept at every level.

**Wording kept fixed, because solves and evidence depend on it:**
- the residency dates (9 Jan / 15 Dec), Lila's train on 8 January, the Mistral closing on the 7th, the 46 bus, 187/200, «Rue de Lancry», 1970, and «L.»;
- the déchiffrer answer sets: T5 invitation/excuses/adieu, all of them true; T6 "elle oublie, et elle a honte" and "Odile"; T8 "derrière le tableau";
- the T7 option labels, which at A1 are «Solvel achète» and «La coop achète».

**Detector workarounds:**
- `PERCEPTION_INFINITIVE` fires on «regarder derrière», so the A1/B2 wording is «Chercher derrière le tableau» and «regarde bien derrière».
- `REGISTER_NE_DROP` fires on «ne vous aime pas» and «n'y tenait pas», so those lines were rephrased.
- Where «À suivre…» plus one plot word (*tableau*) would break the A1 budget, three A1 captions end in «La suite…».

**Simplified at A1 (the plot holds; colour is lost):**
- T5: the "trois semaines" in Marin's caption.
- T6: Marchand's "succession Ferrand" joke becomes «la famille Ferrand», and the 10 h signing detail goes from his own line (the caption keeps it).
- T7: «Le Mistral fait son réveillon» becomes «Grande fête au Mistral». Gus's petition becomes «le papier de Gus».
- T8: the "fausse lumière" SMS keeps only «il peint d'en haut, de la fenêtre d'Odile».

## QA-STORY pass (2026-10-03, after the owner's A1/German test of T1 day A)

**What was wrong.** An A1 variant replaced the French, but the translation shown beside it was still the A2 line's («C'est son café.» with «Das hat sie immer genommen.»). Several A1 lines also made no sense out of context or in sequence («C'est son café.», «Bravo, Gus. Sept sur vingt.», «Vous êtes trop beau» for «élégant»).

**What changed.**
- Every a1 variant that is not the A2 line carries its own `a1_native` {en, de} in `levels_*.json`. `apply_levels` folds it into `Say.native_a1`, and `page.py` serves the translation of exactly the French it serves (`Say.native_served`). An A1 line never borrows the A2 translation. `scripts/season_levels.py` now fails on a missing one.
- Every a1 line of t1–t8 was re-read in day order at A1. 182 were rewritten (t1–t2: 32, t3–t4: 39, t5–t6: 53, t7–t8: 55, plus 3 in the read-through), in the speaker's voice, with the plot and clues kept. Examples:
  - «Le café d'Odile. Toujours le même.»
  - «Bravo, Gus. Belle gaffe.»
  - Gus asks «C'est qui, vous ? Et pourquoi ici ?» (the task wants both).
  - «14 mars. 23 h.» is restored.
  - T6 has the bus 46 and 10 h again.
  - The A1 T7 promise: «Tu appelles… moi !».
- Reactions that quoted words the A1 example replies never say were reworded: T2 «"Un peu", c'est bien», T3 «"Pas encore" ?», T5 «Ce n'est pas bête».
- To bring every file back to the 95 % floor, colour words were dropped:
  - «tarte» became «gâteau» except in the calendar evidence «3/5 … tarte aux pommes»;
  - Marchand's café crème became a café au lait;
  - «deux cents mètres» became «très près»;
  - «C'est signé» became «Quatre. D'accord. Oui.»
- `tasks.json` (new) holds two things for each turn and solve:
  - a plain one-sentence task (en/de/fr). It is served instead of the bible's literary wording, for example «Sag, wer du bist und warum du hier bist.»
  - for each turn, an «ask again» line in the addressee's voice, with a `{name}` variant that echoes the learner's own name. Five catch-all turns have `null`: T7 midnight and the fourth promise, and T8 Margaux's last words, the platform and Camille. T3's yes/no wall question has an ask-again line, so an off-topic reply no longer counts as a «yes».

**Doubts for the owner.**
- The T1 opening caption at A1 drops «Paris, 11 novembre» (10-word cap). The date stays in the day header.
- T2 has «gâteau» in speech but «tarte aux pommes» on the calendar.
- At A1 Gus's duke is «il» («duc» would be a second word outside the list).
