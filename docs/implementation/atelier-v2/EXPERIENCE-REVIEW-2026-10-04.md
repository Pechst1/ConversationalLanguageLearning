# Experience review — 2026-10-04

**The question.** Is a learner's minute in L'Atelier well spent, and will they come back tomorrow? This review answers it as the chief learning designer and as the product's most demanding learner.

**The method.** I lived 15 months of the product: five learners, each played as a strong, an average and a struggling learner, for 30 days each, through every surface. I read the transcripts in order, timed every step, judged the result against the evidence, read season 1 as an editor, fixed what was safe, and walked again.

**Related documents.**
- [CONTENT-PROGRAM-2026-10-03.md](CONTENT-PROGRAM-2026-10-03.md)
- [EXERCISE-QA-2026-10-03.md](EXERCISE-QA-2026-10-03.md)
- [SEASON-LEVELS.md](SEASON-LEVELS.md)
- [WP-111-FIRST-10-DAYS-LIVE.md](WP-111-FIRST-10-DAYS-LIVE.md): the only paid read of generated days, used here as evidence.

---

## 0. The verdict on one page

**What is already excellent**
- **The authored season (the tentpoles).** It is genuinely good fiction. It has a mystery with fair clues: the calendar, the Polaroids, the whiter patch of kitchen wall. It has a set-up that pays off three weeks later. It has comedy, mainly from Gus and Marin. Its choices change later pages. And every day ends on a real hook. The level variants hold the plot at A1 and gain colour at C1.
- **The grading contract.** `answer_acceptance` is fair and named. The walk found only two edge cases.
- **The design.** It stays calm throughout. The month had no fake streaks, no mascots and no praise that was not earned.

**What a learner actually met, worst first.** Every item below is quoted from the transcripts in §2.
1. **A lost day breaks the story.** When a generated day fails, the learner gets an authored café scene in which Margaux greets them as a stranger, and the season stops moving. In the paid A2 read, 3 of 8 generated days were lost this way. In the walk, a director that missed one guard sent B1, B2 and C1 learners into a three-scene loop for 28 days. *Owner decision 1.*
2. **Advanced learners spend their minutes on beginner words.** Before this review, 153 of the 259 vocabulary items that B1+ learners met were grammar words or numbers («pas», «moi», «elle», «cinq», «vingt»). Fixed.
3. **The "repair" items were often nonsense.** 418 items told a learner «Schreib richtig, was du gesagt hast» over a tapped card, a give-up («euh je ne sais pas»), or a whole letter, with a different word as the answer. Fixed.
4. **The level is set three days late.** A C1 learner can only tick «comfortable» (B1.1). The placement is offered on day 4. Then 8 vocabulary checks run back to back: 192 items, about 18 minutes. Their light checks later filled the word drill (300 due cards) and halved new words. The drill flood is fixed; the onboarding flow is *owner decision 2*.
5. **The time promise is wrong in both directions.** A1 days run 11–14 minutes against a 10-minute budget, and are over it on 24–29 of 30 days. B2 and C1 days run 4–5 minutes, with about 4 practice items. On top of the day come the drill (3–6 min), letters (2–3 min) and La Forge (offered as a 5-minute chip). *Owner decision 3.*
6. **Some corrections taught wrong French.** «Je veux comprendre qui elle était» was corrected to «je voudrais» (58 times). It then became the most frequent reply target of an A1 month (45 times). Fixed.
7. **Some feedback was dishonest.** With the corrector unavailable, a flawless C1 letter was told «il me manque encore ceci : Écrire un message qu'on pourrait vraiment envoyer» (242 times). Some replies leaked English («Achieve: …»). C1 learners were asked to «Placer une fois : Je suis, tu es». Fixed.
8. **The help gave the answer away.** The «hint» was the whole model answer, and the suggested reply was glossed with the character's question («Ma famille dit : fatiguée.» over «Warum ist Odile gegangen?»). Fixed.

**What I changed.** 19 fixes, each with a regression test (`tests/test_experience_review_2026_10_04.py`, 44 tests). There is a new 30-day life walk over every surface (`tests/experience_walk.py`, `tests/test_experience_walk.py`). The learner walk gained 6 new checks and lost 2 harness defects that had hidden the B1+ season and frozen the scheduler. **Across 15 lives, the walk's problems fell from 1,825 to 0** (counted by the final checks over both runs).

**What needs the owner.** Ten decisions, ranked in §8. The top three:
1. Lost days must stay inside the season.
2. Place the learner on day 1, and run the vocabulary check top-down.
3. Size the day per level.

---

## 1. How the month was lived

### The harness
- **The learner walk** (`tests/learner_walk.py`) was green, but it was blind to the B1+ season. Its scripted director wrote 6-word objectives. From B1 a gap day needs at least 10 words (`living_story._OBJECTIVE_MINIMUM_WORDS`), so every B1/B2/C1 gap day was refused and the authored stand-in served. B1+ learners never left day 2 of the season, and nothing failed. Fixed: `learner_walk.fit_level` writes B1+ moves.
- **The life walk** (new, `tests/test_experience_walk.py`, `-m walk`) plays one learner for 30 days through the real HTTP surface, as the app actually works:
  - **Sign-up** uses `starting_point` (new / some / comfortable), not a typed CEFR level.
  - **The placement** is taken when `/placement/offer` says so. A grader scores by the persona's true level.
  - **The vocabulary check** follows the placement, with the answer key read server-side.
  - **Every day:** La Une (`/daily-journeys/today`), the day (the page via `/story-engine/episodes`, the help when the struggling learner asks for it), one drill session as `review.tsx` asks for it (`/vocabulary/due-context`, `/anki/review` with typed answers), the Courrier (`/missions/today`, a reply, completion) and the Cahier (`/progress/cefr` daily; notebook and can-dos on days 1, 7, 14 and 30).
- **The clock.** The journey's own clock fixture moved only the journey. The word scheduler, a unit's «Tenue», the intake throttle and the forecast all stayed at real time, so a "30-day" walk never aged a card. The life walk installs E-3's test clock (`app.core.test_clock`) over every `app.*` module, one day at a time.
- **The qualities** (`experience_walk.LifeAnswerer`):
  - **strong:** about 95 % right, the season's own example replies, and it uses the reply's targeted unit;
  - **average:** phone typography, accent slips, one tap in four wrong;
  - **struggling:** about 50 % right, sometimes a first reply in German or English, the hint and the suggestion before replying, the drill every other day, one letter in two.
- **The timing model** (`experience_walk.Timer`) prices what the learner reads and does:
  - French reading: 45 / 70 / 100 / 140 / 180 wpm at A1…C1;
  - native reading: 220 wpm;
  - composing French: 5 / 8 / 11 / 15 / 19 wpm;
  - a tap: 2 s plus reading time;
  - moving on: 1.5 s;
  - multipliers: ×1.12 for average, ×1.4 for struggling.
  - "French minutes" are minutes spent reading or producing French. "Explanation" is rules and notes in the native language. "Support" is tasks, instructions and translations. "Overhead" is navigation.

### What is real and what is scripted

| Part | In the walk |
|---|---|
| Tentpole pages (16 of 59 season days), replies routed, choices | **Real**: the bible and its level variants |
| Generated gap days (43 of 59) | **Scripted**: the season suite's fake director. Its English placeholder prose is never judged. Real generated days are judged from the paid A2 read of 2026-09-30. |
| Grading, planner, practice items, rule cards, drill, band check, placement ladder | **Real** |
| The Courrier | **The authored or deterministic fallback**: `ATELIER_LLM_ENABLED` is off in tests. Production generates letters, but this fallback is what a learner gets whenever the model fails. |
| Placement grader, story classifier | Scripted, scored by the persona's true level |

**No paid model call was made.**

### Limitations
- **La Forge** was recorded as offered (a 5-minute chip at Régulier) but not played.
- **No audio** is deployed, so `listen_tap` reads as recognition.
- **Database timestamps** are written by the SQL server default and do not move with the test clock. The *measured* forecast after day 14 is therefore unreliable in the walk; the time-to-level model in §5 is computed directly instead.

### Reproduce

```
WALK=1 EXPERIENCE_OUT=<dir> venv/bin/python -m pytest tests/test_experience_walk.py -m walk   # 15 lives, ~15 min
WALK=1 WALK_ALL_DAYS=1 WALK_TRANSCRIPTS=<dir> venv/bin/python -m pytest tests/test_learner_walk.py -m walk
SEASON_REPORT=<file> SEASON_REPORT_DAYS=60 SEASON_REPORT_BAND=C1.1 venv/bin/python -m pytest tests/test_season_one.py -k owner
```

---

## 2. Lived findings

Quotes are from the baseline transcripts (before any fix), unless marked *after*.

### 2.1 Sign-up and placement

- **F-1. The level arrives three days late.** Sign-up asks one question, «Votre français ?», with the answers new / some / comfortable, which map to A1.1 / A2.1 / B1.1. A B2 or C1 learner therefore plays days 1–3 at B1.1. They read the A2 lines (there are no B1 variants), get B1 rules, and get B1 drill words («néanmoins, toutefois, notamment»). `/placement/offer` opens only after 3 completed days (`PLACEMENT_OFFER_MIN_DAYS`). On day 4 the C1 learner is placed at «C1.1, conf 0.74», after essays such as «Un musée doit-il restituer les œuvres acquises dans un contexte contesté ?».
- **F-2. A beginner is offered a placement that cannot tell them anything.** The A1 strong learner was offered the placement on day 5. It took about 9 minutes and returned «A1.1». The cause: `journey_placement_evidence` counts replies met at a band *equal to or above* the current one as evidence of being above it.
- **F-3. The vocabulary check is a marathon, and noisy.**
  - After placement, every sub-band below is checked from the lowest up: 8 × 24 = 192 items for C1, about 18 minutes.
  - B2.1 failed at 21/24 while B2.2 passed at 23/24. A learner who knows 92 % of a band fails a 24-item, 90 % gate about 30 % of the time.
  - The C1 *struggling* learner sat through 6 checks (144 items, about 27 minutes of onboarding in all) and was credited 0 words.
- **F-4. The credited words then came back as a flood** (*fixed*). The check credits each word with a light check in 10–45 days, which is 2,771 words for a B2 learner. From day 14 they came due at about 45 a day. The drill takes 30 due cards a session, so the backlog hit the 300 shown. The intake throttle then cut new words from 8 to 3–5 a day. For three weeks the B2 learner reviewed words they had just proved they knew, and their level fell from «B2.1 · 5 %» to «4 %».

### 2.2 La Une

- **On a tentpole day** the headline is good: «#1 «Le mauvais accueil»», with yesterday's «À suivre…» as the teaser.
- **On a generated day** it is title-less by design: «nothing is invented».
- The estimate on the card (`available.estimated_seconds`) said 384–480 s on the A1 learner's first days. The A1 day actually took 7–14 minutes (§3).

### 2.3 The story day

- **The tentpoles work** (see §6).
- **F-5. A lost day breaks the season.**
  - The A1 walk on day 3: the director failed a guard («gendered_agreement»), so `order_at_cafe` was served: «Tiens, bonjour ! Vous vous installez ou c'est à emporter ?». Margaux has known the learner as Odile's family since T1. The panel lines carried no translation for the A1 learner (`text_native: ""`). The poor learner got «Pardon, je n'ai pas bien saisi. Qu'est-ce que je vous sers ?» three times, word for word.
  - Before the harness fix, the B1/B2/C1 walks rotated «Margaux s'apprête à fermer…», «Lila voudrait vous montrer le marché du Canal…» and «Le métro reste bloqué…» from day 3 to day 30. The season never reached T2. The stand-ins address the learner as «vous» («Lila voudrait vous montrer…»), where the season's friends say «tu».
  - The paid A2 read shows the same in production: «Jour 5 — jour perdu : scène d'auteur «order_at_cafe» … g1.3 attend», and again on days 6 and 7.
  - An authored stand-in does not advance the season (`bind_serial=False`). So repeated failures stall the story indefinitely.
- **F-6. A decisive choice got no answer on the page.** T2 day B, «Une clé pour moi ? Je peins ici, avant l'école.» The learner taps «Donner une clé à Lila»; the reply is «…» and the day ends. Only «Pas encore» has a beat («Pas encore. D'accord. J'aime bien "encore".»). The flag is real: it decides where Lila paints in gap 2 and the T5 location, and it pays off at T8. But the learner who gives the key sees nothing happen. *Owner decision 7: a bible line.*
- **F-7. Speaker ids and placeholders on screen** (*fixed*).
  - «lila_bonnet : Pardon ? Je ne comprends pas… Et en français ? Même avec des fautes, ça ira.»: a «choix» turn has no `to_name` (A1 day 27, A2 day 9).
  - «Ici, c'est « vous » : {counterpart} vous vouvoie. {reason}» in a B2 register note: the template was printed unformatted.
- **F-8. Help gave the answer away** (*fixed*). The struggling A1 learner on T2:
  - HINT: «Zum Beispiel: «Ma famille dit : fatiguée.»»
  - SUGGESTED: «Ma famille dit : fatiguée.» — native: «Also? Warum ist Odile gegangen?»

  The hint was the answer, and the suggestion's gloss was the question's translation.

### 2.4 The rule step and the Essai

- **F-9. «Welcher Satz folgt der Regel von heute?»** (*fixed*).
  - At A1 and A2 the three options are one use of the rule and two sentences that do not use it, all of them correct French: «Vous vous installez ou c'est à emporter ? / Margaux essuie le zinc. / Il pleut sur le canal.» «Follows the rule» suggests that the others break it.
  - The same words were used for a Rappel of a rule learnt days earlier. On A1 day 13 the Rappel of the -er verbs came before that day's own rule (Ne…pas) and called it «die Regel von heute».
  - This happened 536 times in 15 lives.
- **F-10. The A1 Essai asked for the sentence it had just printed** (*fixed*, found after the first fixes). «Was ist richtig? … Je voudrais un café, s'il vous plaît.» was followed by «Korrigiere: Je voudrais de un café.» → «Je voudrais un café.»
- **Tentpole days carry no rule step** (3 of 147 tentpole days in the walk). This is by design (T-1): the review moves to La Forge, which is a separate 5-minute chip at Régulier. On 16 of 59 season days the grammar track therefore depends on a surface the learner may skip.

### 2.5 Practice items and repairs

- **F-11. The first item a beginner ever sees is a guess** (*fixed*). On day 1, before the scene, the item is «Maskulin oder feminin? appartement», for a word not met yet.
- **F-12. "Repair what you said" over things the learner never said** (*fixed*; 418 items before, 0 after). All from the German A1 and A2 lives:
  - «Schreib richtig, was du gesagt hast. | clé» → tiles of «Vous allez vendre l'appartement d'Odile ?». The «clé» was a wrong cloze tap.
  - «Schreib richtig, was du gesagt hast. | euh je ne sais pas» → «un appartement».
  - «Schreib richtig, was du gesagt hast. | der Schlüssel» → «quoi». «Der Schlüssel» was a tapped native card.
  - «Schreib richtig, was du gesagt hast. | merci pour ta lettre. hier je suis alle au mistral…» → «clé». That is a whole letter, and «clé» is a word the letter did not use.
  - The target label next to them was English for a German learner: «The word appartement needs another repair in context.» (749 English strings in the German lives.)
- **F-13. Advanced learners practised beginner words** (*fixed*).
  - The B2 and C1 lives' vocabulary items were, in order: «pas, moi, plus, jour, quoi, autre, huit, avant, elle, toi, nous, depuis, devant, mon, dire, ses, ils, ton, cinq, vingt, ces, son, tout».
  - The C1 learner was asked «Complétez la phrase de la scène : Tu en penses … ?» → «quoi».
  - The cause: `_new_vocabulary_anchor` had a difficulty ceiling and no floor. The scene's most frequent uncarded word is always a grammar word, and nobody cards those.
- **F-14. Two match grids that share three of four pairs** on the same morning (A1 day 4: «vendredi/pas/chose/lettre», then «chose/lettre/pas/votre»). Not fixed: a low cost to the learner.

### 2.6 Grading

- **F-15. A wish was corrected to a request** (*fixed*). «Je reste encore un peu. Je veux comprendre qui elle était.» got «„Je veux“ klingt im Laden oder Amt schroff. „Je voudrais“ ist die Bitte.», and Lila asked in-story: «Pardon, je veux ou voudrais ?».
- **F-16. «ca» for «ça» was refused** (*fixed*). «Elles ont beau essayer, ca ne marche pas.» was refused, because «ca» was listed as a homograph of the literary «çà».
- **F-17. The in-story recast offered two different words** (paid A2 read; *fixed*):
  - «Pardon, On commence maintenant ou quand ? ?»
  - «Pardon, Je suis un peu perdu ou perdu(e) ici. ?»

  The first is a change of content posed as a choice of form. The second asks about an agreement nobody can judge without the learner's gender.

### 2.7 The word drill

- **Intake.** 8 new words a session (`review.tsx` `new_limit: 8`) plus the journey's share made about 7–8 new words a day for strong learners and about 2 for struggling ones.
- **The words come in frequency order:**
  - A1: «pas, plus, oui, ici, très, bien, aussi», then «trois … dix», «onze … trente», «quarante … mille, premier, deuxième, dernier». That is 30 numbers in 4 days.
  - C1: «islamiste», «bombardement», «tueur», «colonel». These are newspaper-corpus words, and they are jarring next to the story.
- **The drill alone cannot reach the Soutenu and Intensif quotas.** The session cap is 8 new words, «Encore» adds none, and the journey's share is 8 or 12.

### 2.8 The Courrier

The Courrier was played on its deterministic fallback, which is what a learner gets whenever the model fails.

- **F-18. Every reply claimed something was missing** (*fixed*). «Je comprends l'idée, mais il me manque encore ceci : Écrire un message qu'on pourrait vraiment envoyer. Ajoutez ce point et je pourrai avancer.» The verdict was «unassessed», and it came with the outcome «partial» and «Neutre : rien à rattraper, rien d'acquis.»
- **English leaked into the replies** (*fixed*): «… il me manque encore ceci : Achieve: Marin Lévêque sait ce que tu en penses et ce que tu comptes faire ensuite..» and «… : Use évidemment naturally.»
- **The letter's grammar ignored the learner's level** (*fixed*; 389 times). C1 learners were asked for «Placer une fois : Je suis, tu es : les pronoms et être», «Avoir : j'ai, j'ai 20 ans, j'ai faim», «Il y a». The fallback took the catalogue's first units.
- **The fallback letters repeat** (*not fixed*: they rotate only when the model fails). «Plus de pain blanc» arrived 6 times in a month to a B1 learner who answered every letter, and a C1 learner was sent «Il n'y a plus de pain blanc. Vous voulez un autre pain ?».
- **The volume is large.** A learner who answers gets a letter nearly every day: 15–23 in 30 days, 2–6 minutes each.

### 2.9 The Cahier

- **Two notions of "learnt" disagree.** On day 30, the notebook shows «Solide» (mastery 8.5) for «Je suis, tu es» and «Il y a». The level shows «units held: 0 of 17».
- **Held needs «Tenue»**: free use on two days at least 7 days apart, and a spaced success at least 14 days after introduction. The *after* walk shows that strong learners use the unit on the day it is introduced. The second free use waits until stability reaches 10 days and the reply asks for the unit again. That is about 5–6 weeks (median hold lag 41 days). So nobody's grammar half of the level moves in the first month, and the learner sees «A1.1 · 35 %» made almost entirely of words.

### 2.10 The five learners

**A1, German, beginner**
- **strong:** a rich, long day, 11 min mean, 24 of 30 over budget. 237 drill words, 196 known on day 30, «A1.1 · 35 %».
- **average:** the same, plus slip notes. The «je voudrais» correction followed them all month.
- **struggling:** asks for the hint, gets the full answer, copies it, and is graded «met». About 62 new words in 30 days, 42 known, «A1.1 · 7 %». At that intake A1 is about 16 months away (§5).
- The day-1 gender guess, the garbled repairs and the English labels hit all three.

**A2, German, placed («some»)**
- The placement on day 4 confirms A2.1, after 4 essays and 2 vocabulary checks (15–19 minutes).
- From then on it is the best-fitted persona: A2 lines, 8–10 minute days.
- The struggling learner failed both checks, so nothing was credited.

**B1, English**
- Reads the A2 lines, which is sensible.
- Days of 5.6–7.3 minutes with 4 items, against a 10-minute budget.
- 13 rules in 30 days.
- Before the fix, most of their vocabulary items were A1 words (across B1–C1: 153 of 259 were grammar words or numbers).

**B2, English**
- Placed on day 4, after three days at B1.1.
- The drill flooded from day 14. New words fell to 3–5 a day, and the level fell from 5 % to 4 %.
- The day is 4.4–6 minutes of story with 3–4 items.

**C1, German**
- The most time lost to onboarding: about 18 minutes for strong, about 27 for struggling.
- Letters asking for «j'ai faim».
- Vocabulary items «cinq», «vingt», «pas».
- The C1 *story* is a pleasure («Tu étais au parfum ?», «menés en bateau»). The day around it is not yet worth a C1 learner's minute.

---

## 3. Time

**Before** (15 lives × 30 days, mean minutes a day; the journey's budget is 10 minutes at Régulier):

| Life | Day (journey) | Planner's estimate | Days over budget | Drill | Letters | Onboarding (total) | All surfaces | French share | Items/day | Rules/30 d | New words/30 d | Due peak | Known words d30 | Level d30 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| A1 de strong | 11.2 | 7.7 | 24 | 3.7 | 3.0 | 8.9 | 18.2 | 87 % | 11.3 | 16 | 237 | 19 | 196 | A1.1 · 35 % |
| A1 de average | 12.4 | 7.6 | 25 | 4.8 | 3.2 | 9.9 | 20.7 | 86 % | 11.5 | 14 | 216 | 19 | 182 | A1.1 · 33 % |
| A1 de struggling | 13.7 | 7.3 | 29 | 2.7 | 2.1 | 0.0 | 18.5 | 84 % | 11.6 | 8 | 62 | 24 | 42 | A1.1 · 7 % |
| A2 de strong | 8.4 | 7.8 | 4 | 5.1 | 2.6 | 13.6 | 16.5 | 82 % | 11.2 | 16 | 237 | 33 | 189 | A2.1 · 22 % |
| A2 de average | 8.8 | 7.6 | 7 | 5.8 | 2.2 | 15.3 | 17.4 | 82 % | 11.4 | 10 | 167 | 60 | 138 | A2.1 · 16 % |
| A2 de struggling | 10.2 | 7.5 | 15 | 3.1 | 1.8 | 18.9 | 15.7 | 80 % | 11.7 | 8 | 53 | 29 | 30 | A2.1 · 3 % |
| B1 en strong | 5.6 | 6.6 | 0 | 5.2 | 2.5 | 15.1 | 13.8 | 81 % | 4.2 | 13 | 206 | 103 | 183 | B1.1 · 17 % |
| B1 en average | 6.5 | 6.7 | 0 | 6.0 | 2.3 | 16.9 | 15.3 | 81 % | 4.4 | 13 | 202 | 98 | 161 | B1.1 · 15 % |
| B1 en struggling | 7.3 | 6.5 | 5 | 2.9 | 1.2 | 21.0 | 12.1 | 77 % | 4.3 | 8 | 63 | 25 | 39 | B1.1 · 3 % |
| B2 en strong | 4.4 | 6.4 | 0 | 4.2 | 1.6 | 17.2 | 10.8 | 78 % | 3.5 | 11 | 185 | **300** | 69 | B2.1 · 4 % |
| B2 en average | 5.1 | 6.5 | 0 | 5.2 | 1.6 | 19.3 | 12.5 | 77 % | 3.7 | 11 | 186 | **300** | 102 | B2.1 · 7 % |
| B2 en struggling | 6.1 | 6.4 | 0 | 3.6 | 1.5 | 26.6 | 12.1 | 75 % | 3.9 | 8 | 65 | 156 | 19 | B2.1 · 1 % |
| C1 de strong | 3.8 | 5.8 | 0 | 4.1 | 1.5 | 18.4 | 10.0 | 77 % | 3.4 | 11 | 185 | **300** | 55 | C1.1 · 2 % |
| C1 de average | 4.5 | 6.5 | 0 | 4.7 | 1.1 | 20.5 | 11.0 | 75 % | 3.9 | 11 | 170 | **300** | 55 | C1.1 · 2 % |
| C1 de struggling | 6.3 | 6.5 | 0 | 2.9 | 1.1 | 26.6 | 11.3 | 75 % | 4.3 | 8 | 65 | 29 | 33 | B2.1 · 2 % |

**After** (same lives, all fixes): 

| Life | Day (journey) | Planner's estimate | Days over budget | Drill | Letters | Onboarding (total) | All surfaces | French share | Items/day | Rules/30 d | New words/30 d | Due peak | Known words d30 | Level d30 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| A1 de strong | 13.7 | 7.6 | 20 | 3.6 | 3.5 | 8.9 | 21.1 | 88 % | 11.4 | 16 | 237 | 21 | 194 | A1.1 · 35 % |
| A1 de average | 13.1 | 7.4 | 23 | 4.1 | 2.3 | 9.9 | 19.8 | 87 % | 11.6 | 12 | 182 | 21 | 132 | A1.1 · 23 % |
| A1 de struggling | 12.6 | 7.3 | 26 | 2.8 | 1.9 | 12.5 | 17.8 | 84 % | 11.5 | 8 | 62 | 25 | 43 | A1.1 · 7 % |
| A2 de strong | 9.8 | 7.7 | 16 | 3.8 | 2.3 | 13.7 | 16.4 | 84 % | 11.5 | 16 | 237 | 16 | 190 | A2.1 · 22 % |
| A2 de average | 8.8 | 7.4 | 8 | 3.9 | 2.3 | 15.4 | 15.5 | 82 % | 11.6 | 8 | 120 | 17 | 93 | A2.1 · 11 % |
| A2 de struggling | 9.8 | 7.4 | 10 | 3.0 | 1.5 | 19.0 | 14.9 | 80 % | 11.6 | 8 | 55 | 27 | 34 | A2.1 · 4 % |
| B1 en strong | 7.3 | 6.6 | 4 | 3.9 | 2.5 | 15.1 | 14.2 | 84 % | 3.8 | 16 | 240 | 19 | 190 | B1.1 · 17 % |
| B1 en average | 7.6 | 6.7 | 6 | 5.0 | 1.3 | 16.9 | 14.5 | 82 % | 4.0 | 16 | 240 | 23 | 189 | B1.1 · 17 % |
| B1 en struggling | 6.6 | 6.2 | 1 | 3.0 | 1.3 | 21.0 | 11.6 | 78 % | 3.0 | 8 | 66 | 29 | 45 | B1.1 · 4 % |
| B2 en strong | 5.9 | 6.5 | 0 | 3.9 | 1.9 | 17.2 | 12.4 | 80 % | 3.5 | 16 | 240 | 16 | 164 | B2.1 · 11 % |
| B2 en average | 5.9 | 6.6 | 1 | 5.1 | 1.3 | 19.3 | 13.0 | 78 % | 3.7 | 16 | 240 | 29 | 165 | B2.1 · 11 % |
| B2 en struggling | 5.6 | 6.2 | 0 | 2.9 | 1.1 | 26.6 | 10.5 | 75 % | 2.9 | 8 | 71 | 25 | 36 | B2.1 · 2 % |
| C1 de strong | 5.1 | 6.1 | 0 | 3.8 | 1.5 | 18.3 | 11.0 | 79 % | 3.3 | 16 | 240 | 31 | 167 | C1.1 · 6 % |
| C1 de average | 5.1 | 6.6 | 0 | 5.0 | 1.0 | 20.5 | 11.8 | 76 % | 3.4 | 16 | 240 | 26 | 167 | C1.1 · 6 % |
| C1 de struggling | 5.6 | 6.1 | 0 | 2.7 | 1.3 | 26.7 | 10.4 | 75 % | 2.7 | 8 | 69 | 26 | 36 | B2.1 · 2 % |

*Strong lives write longer replies after the fixes. The walk's strong learner now uses the reply's targeted unit (`LifeAnswerer.enrich_reply`), which is what made «Tenue» observable. That accounts for the A1/A2 journey minutes rising (A1 strong 11.2 → 13.7); the product's day did not get longer.*

*Average lives: the intake throttle enters below 80 % review accuracy and exits at 85 % (`intake_throttle`). An average learner at about 78 % sits on that edge, so their new words swing between 8 and 3 a day on noise, in both runs (A1 average: 216 before, 182 after; A2 average: 167 before, 120 after). The strong lives are the clean comparison.*

**What the numbers say**

- **The «10-minute» Régulier day is not 10 minutes.**
  - With everything La Une offers (journey, drill, letters, and La Forge's 5 minutes, not counted above), it is **15–26 minutes for A1–A2 and 10–16 for B1+**.
  - The journey alone overruns at A1. The planner's prior, 0.45 s a token (about 133 wpm, «a beginner reading French with a native gloss»), is about three times a true beginner's French reading rate (40–60 wpm). The measured pace that should correct it is clamped at 0.70 s a token (about 86 wpm).
  - At B1+ the journey is about half its budget, because the B1+ practice slot allows only production formats, and few targets qualify.
- **Most minutes are French.** The French share is 75–87 % across all surfaces. Explanations are about 1 % and support about 8–10 %. Almost no minute is dead; the problem is *which* French.
- **The minutes that teach French at the learner's level**, before the fixes:
  - A1: about 85 % of the day.
  - B2/C1: about 40 % of practice minutes went to A1 grammar words, light checks of known words and A1 letter objectives.

---

## 4. The verdict against the evidence

| Part of the day | Best use of the minute? | Evidence |
|---|---|---|
| **The page** (comprehensible input) | **Yes**, the strongest part. Level variants keep A1 at 95.5–97.9 % coverage, which is inside the 95–98 % band where unassisted comprehension and incidental learning are possible (Hu & Nation 2000; Laufer & Ravenhorst-Kalovski 2010). Narrative transportation drives return (Green & Brock 2000). | Tentpoles at A1, A2 and C1 (§6). |
| **The reply** (output) | **Yes, with a gap.** The reply is pushed output in a meaningful context (Swain 1985), and the choices matter. But a reply in German still routed and continued until QA-CLOSE, and a struggling learner can copy the hint (the full answer) and be graded «met» — now the hint is a sentence opening (desirable difficulty: Bjork & Bjork 2011). | F-8, struggling lives. |
| **Corrective feedback** | **Mostly right**: prompts and elicitation, which beat recasts (Lyster & Saito 2010), and explicit notes in the native language. **Wrong where the detector was wrong**: «je veux comprendre» → «je voudrais», and forced choices between two different words. Both are fixed. | F-15, F-17. |
| **The Règle** (explicit instruction) | **Yes.** Explicit instruction outperforms implicit (Norris & Ortega 2000; Spada & Tomita 2010), and the cards are good. **But** the recognition wording misled (fixed), and tentpole days skip the rule, so a sixth of the season has no grammar intake in the journey. | F-9. |
| **The Essai and Rappel** (retrieval, spacing) | **Yes in design**: guided → free, spaced by the memory model (Roediger & Karpicke 2006; Cepeda et al. 2006). **No in execution, before the fixes**: copy items (F-10), «today's rule» on a Rappel (F-9), and repairs of give-ups (F-12). | |
| **Interleaving** | **Weak.** Rappels of several units do appear on one day (A1 day 13: the -er verbs, Ne…pas, articles). But practice is mostly blocked by today's unit, and the Essai is a single-unit block. Interleaved contrasts between partner units (`contrast_partners` exist in the catalogue) would discriminate better (Rohrer & Taylor 2007; Nakata & Suzuki 2019 for L2 grammar). | Owner decision 4. |
| **The drill** (retrieval of words) | **Yes for A1–A2** (FSRS, typed recall). **Wasteful for placed learners before the fix**: 30 light checks a day of proved words (F-4), and frequency-corpus words unrelated to the story. | F-4, §2.7. |
| **The Courrier** (written output) | **Yes when the model answers**. **No on the fallback**: it claimed things were missing without assessing, used A1 objectives for C1, and repeated the same letters. The first two are fixed. | §2.8. |
| **Motivation through visible competence** | **Half there.** The level label is honest, but the grammar half cannot move for about 6 weeks (Tenue), and the notebook's «Solide» contradicts it. Self-determination theory needs *perceived* competence (Ryan & Deci 2000). | §2.9, owner decision 5. |
| **Desirable difficulty** | **Too easy** for B1+ before the fixes (A1 words and clozes); **too hard** for A1 struggling learners (11–14-minute days at 50 % accuracy). | §3. |

---

## 5. Time to each level versus Duolingo

### The app's own model

**The inputs.**
- Quotas: Léger 5 words a day and 2 units a week; Régulier 10 and 4; Soutenu 18 and 6; Intensif 30 and 8.
- Gates per sub-band:
  - 85 % of the band's units held («Tenue»);
  - 80 % of its core words known;
  - an épreuve, one day per band.
- The bands: lexicon v3 and catalogue v2 (A1.1 to C1.2), using `level_forecast.forecast_days` and its hold-lag model.
- The hold lag (median days from introduction to «held»): 41 days at 90 % accuracy, 44 at 80 %, 101 at 60 %.

**From zero**, with the quotas as planned (retention 0.9). Hours are at the rhythm's nominal minutes:

| Rhythm | A1 | A2 | B1 | B2 | C1 |
|---|---|---|---|---|---|
| Léger (5 min) | 162 d · 14 h | 280 d · 23 h | 522 d · 44 h | ≥ 2 y | ≥ 2 y |
| **Régulier (10 min)** | **106 d · 18 h** | **164 d · 27 h** | **264 d · 44 h** | **407 d · 68 h** | **612 d · 102 h** |
| Soutenu (20 min) | 87 d · 29 h | 126 d · 42 h | 168 d · 56 h | 230 d · 77 h | 345 d · 115 h |
| Intensif (30 min) | 79 d · 40 h | 108 d · 54 h | 140 d · 70 h | 176 d · 88 h | 212 d · 106 h |

**Where the time goes.**
- **Grammar binds at every rhythm.** At Régulier, A1's words alone need 56 days. Its units need 104: 33 units arrive at 4 a week, which takes about 58 days, then the last one waits about 41 days to be held.
- Intensif doubles the units and triples the words, but saves only 27 days at A1, because the hold lag does not shrink.
- The épreuves add a day per band.

**Measured in the walk** (30 days, intake as actually played, from the placed band; minutes are all surfaces). Before the fixes:

| Life | Words/day | Units/week | Accuracy | Min/day | Next level | Two levels on |
|---|---:|---:|---:|---:|---|---|
| A1 strong | 7.9 | 3.7 | 0.93 | 18.2 | A1 in 106 d (32 h) | A2 in 173 d (52 h) |
| A1 average | 7.2 | 3.3 | 0.78 | 20.7 | A1 in 143 d (49 h) | A2 in 225 d (78 h) |
| A1 struggling | 2.1 | 1.9 | 0.51 | 18.5 | A1 in 479 d (148 h) | A2: more than 2 years |
| A2 strong | 7.9 | 3.7 | 0.93 | 16.5 | A2 in 104 d (29 h) | B1 in 252 d (69 h) |
| B1 strong | 6.9 | 3.0 | 0.87 | 13.8 | B1 in 183 d (42 h) | B2 in 397 d (91 h) |
| B2 strong | 6.2 | 2.6 | 0.88 | 10.8 | B2 in 235 d (42 h) | C1 in 574 d (103 h) |
| C1 strong | 6.2 | 2.6 | 0.93 | 10.0 | C1 in 321 d (53 h) | — |
| any struggling | about 2 | 1.9 | about 0.45 | 12–18 | more than 2 years | — |

After the fixes, the B2 and C1 learners' word intake is restored by the drill fix (B2 strong: 6.2 → 8.0 words a day and 2.6 → 3.7 units a week, so B2 in 235 → 182 days and C1 in 574 → 444. C1 strong: C1 in 321 → 243 days. B1 strong: B1 in 183 → 156 days. The throttle no longer engages on a pile of light checks, which also restores the units).

### Duolingo, for comparison

**The benchmarks**, with their caveats:
- **Duolingo French covers content up to CEFR B2** in 8 sections.
- **Duolingo's own study** (Jiang et al., *Foreign Language Annals* 54(4), 2021) found that learners who completed 5 units of the French or Spanish course matched four university semesters in reading and listening («Intermediate Low» reading, «Novice High» listening), «in less than half the time» ([press release](https://www.globenewswire.com/news-release/2022/01/12/2365800/0/en/Leading-Language-Research-Journal-Publishes-Study-Showing-Duolingo-Learning-Outcomes-Are-Comparable-to-University-Classes.html); [paper record](https://experts.nau.edu/en/publications/evaluating-the-reading-and-listening-outcomes-of-beginning-level-/)).
- **Classroom norms:** Alliance Française cumulative guided hours are A1 60–100, A2 160–200, B1 360–400, B2 560–650 and C1 810–950 ([AF Leeds](https://afleeds.org.uk/faq)).
- **A typical Duolingo session** lasts about 15 minutes.

**The model.** Take the Duolingo claim at face value (twice classroom efficiency, receptive skills) and a 15-minute day:
- A1 is 30–50 h, about 4–7 months;
- A2 is 80–100 h, about 11–13 months;
- B1 is 180–200 h, more than 2 years.

**The comparison.** On its own gates, L'Atelier's Régulier learner (about 15–20 real minutes a day) is forecast at A1 in about 3.5 months, A2 in about 5.5 and B1 in about 9. **On paper that is about twice as fast as the Duolingo model, at a similar daily time.**

**The honest caveat.** The app's hours (A1 18–32 h, B2 68–151 h) are 3–5 times below every classroom norm. The level label measures *syllabus coverage*: words known on cards (80 % of about 3,600 core words to B2, which is consistent with Milton 2010's vocabulary sizes for B2), units used twice unaided, and an épreuve. It does not measure four-skill proficiency. **Until the épreuves are validated against an external test, the product should not promise a CEFR level by a date.** It can show the forecast, as it does today, as «an estimate». *Owner decision 10.*

### The five changes that would most increase learning per minute and return rate

1. **Keep every day inside the season** (return rate). A lost day must never be a stranger's café scene, and must never stall the story. *Owner decision 1.*
2. **Place on day 1 and check vocabulary top-down** (learning per minute for every placed learner). This saves 3 days at the wrong level and about 15 minutes of checks. *Owner decision 2.* The drill-flood fix shipped with this review.
3. **Fit the day to the level** (both). A level-aware reading prior would make A1 days shorter and B1+ days fuller with retrieval at their level. Count the drill and the chips in the «minutes» the learner chose. *Owner decision 3.*
4. **Make grammar visibly progress** (motivation). Ask for a due unit in one reply turn a week after its introduction, so «Tenue» lands in about 3 weeks rather than about 6. Show «on the way» in the level. *Owner decision 5.*
5. **Practise the words of the scene at the learner's level** (learning per minute, B1+). *Implemented*: new words are now bounded below and grammar words are excluded from B1. The remaining step is to give B1+ tentpoles their own lexicon (today only A1 and A2 tentpole pages carry one).

---

## 6. The story — season 1 read as an editor

I read every tentpole, T1–T8, at A2 (the bible lines, which B1 learners also read), T2 at A1 and T4 at C1, in full. 60 days were generated for each of A1.1, A2.1 and C1.1 (`SEASON_REPORT`).

- **Stakes.** They are clear from day 2: Solvel's offer «finit le 8 janvier», and the café needs the first floor. The stakes are personal and ticking. They rise at T3, where two promises the learner made contradict each other, and at T4, where the fire «est parti de chez elle», so «les dommages… c'est vous, maintenant».
- **Character.** Each regular has a want, a mask and a crack:
  - Gus: «Moralement.», «Augustin, 15 ans. Il dit qu'il sera comte.»
  - Marin: «Il dira oui en pleurant.»
  - Margaux: «Bois, Gus.», then «Je le sais depuis le début.»
  - Lila: «Ce blanc n'est pas le même.», and the Berlin letter.

  The comedy is specific and kind.
- **Surprise and payoff.** Set-ups pay off within the season:
  - the whiter wall (T2) becomes the fire (T4);
  - «Tous les dimanches : M.» becomes M. Marchand;
  - the hidden Polaroid of Lila becomes Berlin (T4 → T5);
  - Gus's château becomes his scooter, then his real feeling for the zinc.

  T4's reveal is earned: the reversed neon «LARTSIM» proves the photo was taken from above.
- **The arc lands.** The second half keeps the first half's promises:
  - **T5 (Berlin):** Lila's unfinished card, «Un peu. Pas assez pour rester. Trop pour partir tranquille.»
  - **T6:** Marchand's «Six ans. Tous les dimanches. Le bus 46…» and Odile's notebook, «Je ne peux pas lui dire que j'oublie.», with a real dilemma: the notebook consoles Marchand but sinks Margaux.
  - **T7:** Margaux's «Personne ne m'a demandé ça depuis vingt-cinq ans. — La mer.» and the decision on the flat.
  - **T8:** Odile's letter, «Pour toi. Quand tu parleras français. … Paris était trop grand pour l'autre langue.» It ties the learner's own French to the story's climax; this is the best idea in the product.
  - **The gap after the finale:** from day 59 the generic generated days take over («Le quartier»). The epilogue and season 2 are still open in the content program, and a learner who finishes s1 meets the weakest days at the moment of highest attachment.
- **Hooks.** Every tentpole day ends on one:
  - «Deux clés pour la même porte. À suivre…»
  - «Odile savait quelque chose sur Lila. Lila ne dit rien.»
  - «Tu as fait deux promesses. Samedi, tout le quartier est là. Presque tout.»
  - «Et ce soir, Lila aussi cache quelque chose.»

  This is the strongest return mechanic in the product.
- **Choices that matter.** The letter choice in T1 gets different replies (Marin: «C'est un signe. Un mauvais.»; Margaux: «Huit janvier.»). T2's key, T3's promises and T4's answers to Gus, Margaux and Marchand all set flags that are read in later tentpoles (`season.json` flags; WP-113 endings diverge). **One gap: F-6**, the key's «double» path has no beat on the page.
- **Level variants.**
  - **C1** is a pleasure: «Tu étais au parfum ?», «Tu nous as tous menés en bateau !», «Lundi, le quartier en fera des gorges chaudes.»
  - **A1** keeps the plot, but the present-tense rule hurts in one place. «Pourquoi elle part, Odile ?» and «Odile sait une chose sur Lila» make a woman who left in 2023 and has since died read as if she were alive and leaving now. *Proposed rewrite (owner decision 7):* allow three glossed past chunks at A1 («elle est partie», «c'était», «elle savait»), each counted as the line's one word outside the list. The 95 % floor holds.
- **The generated gap days (43 of 59 days)** are the weak point. They are judged here from the paid A2 read, because the walk's director is fake.
  - **Quality.**
    - They are coherent and warm, but small in scope. Days 3, 8 and 9 are all «Lila helps with the ticket at the bakery».
    - Lila coaches like a teacher («Dis «je veux reporter mon billet». Non, dis «reporter» mieux.»), which breaks the fiction.
    - The recast glitch «Pardon, On commence maintenant ou quand ? ?» is now fixed.
  - **Robustness.** 3 of 8 days were lost to the authored stand-in (F-5).
  - The tentpoles are a 9/10. The generated days, as read, are a 6/10, with a reliability problem.
  - *Owner decision 8:* a paid live read of gap days at A1, B1 and C1 under a cost cap (about US$3 for 3 × 10 days, from the previous US$0.32 for 10 days) before season 1 goes to every new life.
- **Language and story together.** Measured over the baseline walk:

| | Tentpole days | Generated days |
|---|---|---|
| Rule days | 3 of 147 | 163 of 303 |
| The rule's example comes from the scene | 0 % | 100 %, but this is the walk director complying; production depends on the model |
| Vocabulary items whose word is in today's scene | 64 % | 39 % (fake prose) |
| Items rebuilding a line of the scene | 8 % | 4 % |

  **The verdict:** words are tied to the scene, but grammar is tied to it only on generated days, and only if the model complies. Tentpoles, the best French in the product, teach no rule in the journey.
  - **Proposed engine change** (owner): on tentpole days, a short «Rayons X» step after the ending. It would highlight one unit the page uses (`units.json` already lists them) in a line of the page the learner just read, with the existing rule card behind it. That is not a new unit: it is a review in context, and it keeps D7's «no new unit on a tentpole».

---

## 7. What I changed

Smallest correct change first. Each fix has a regression test in `tests/test_experience_review_2026_10_04.py` and a learner-walk check where it is an invariant of a day or a month.

| # | Finding | Change | Files | Walk check |
|---|---|---|---|---|
| 1 | The B1+ walk never left day 2 (harness) | The walk director meets the B1+ objective floor; the owner's season report too | `tests/learner_walk.py` (`fit_level`, `B1_MOVES`), `tests/test_learner_walk.py`, `tests/test_season_one.py` | the long walk itself |
| 2 | A 30-day walk never aged a card (harness) | The life walk moves every app clock (E-3 `test_clock`) | `tests/experience_walk.py`, `tests/test_experience_walk.py` | `check_life` |
| 3 | «lila_bonnet : Pardon ?» | The ask-again turn gets its addressee's name from the season cast | `season/runtime.py` (`_named_turn`) | `check_strings` (existing) |
| 4 | «{counterpart} vous vouvoie. {reason}» | The register reason is formatted, or a nameless form is used | `journey_capabilities.py` | `check_strings` |
| 5 | «ca» refused for «ça» | «ca» removed from the homographs; «çà» stays strict | `answer_acceptance.py` | `check_grading` |
| 6 | A wish corrected to «je voudrais» | «je veux» is blunt only before an object («un café», «ça», «l'addition») | `pragmatics.py` | **new** `check_wishes_are_not_corrected` |
| 7 | Repairs of taps and give-ups | A practice miss lapses the word, but opens no vocabulary erratum. A give-up opens no correction erratum. A repair is posed only when the answer fixes the wording. | `vocabulary_credit.py`, `journey_learning.py` (`attempted_answer`), `journey_planner.py` (`_repairs_the_wording`) | **new** `check_repairs` |
| 8 | English erratum labels for German learners | The labels, whys and hints come from `learner_copy` in the learner's language; the Courrier no longer passes English | `vocabulary_credit.py`, `learner_copy.py`, `missions.py` | `check_language` |
| 9 | «Regel von heute» on a Rappel; «folgt der Regel» when all options are correct | A1/A2 recognition asks «In welchem Satz steckt die Regel …?». A Rappel says «diese Regel» and shows the rule as its goal. A Rappel repair says «eine Regel, die du gelernt hast». | `grammar_items.py`, `journey_contracts.py` | **new** `check_rule_of_today` |
| 10 | The A1 Essai repaired the sentence just printed | The repair takes a pair whose answer was not just shown | `grammar_items.py` | `check_duplicates` (existing) |
| 11 | A gender guess for a word not yet met | A new word is met only by its meaning before the scene | `journey_planner.py` (`_slot_formats(new_word=)`) | — |
| 12 | B1+ new words were grammar words | A floor at one level below the learner; closed-class words excluded from B1 | `journey_learning.py` (`_new_vocabulary_anchor`) | — (measured in §7.2) |
| 13 | The band check flooded the drill | The light-check window and stability scale with the distance below the learner's band: (20–90 d), (40–180 d), (90–365 d) | `band_check.py` (`credit_schedule`) | **new** `check_life`: no more than 150 due |
| 14 | «il me manque encore ceci» without assessment; «Achieve:» / «Use X naturally» | The fallback answers honestly when nothing was assessed, and never names a word or rule objective as «missing». The labels are French («Placer « X »», the outcome itself). | `missions.py` (`_unassessed_acknowledgement`, `_fallback_response`) | **new** `check_life` (unassessed, English) |
| 15 | C1 letters asked for A1 units | The letter's units are the learner's own (latest first), then their level's | `missions.py` (`_select_concepts`, `_learner_level_code`) | **new** `check_life` (2+ levels below) |
| 16 | A German letter day printed a French task | Story letters carry `desired_outcome_i18n` through `create` and `_custom_context` → `slim_payload.ask_by_language` | `story_correspondence.py`, `missions.py` | `check_language` |
| 17 | The hint was the answer; the suggestion was glossed with the question | The season hint gives the opening of the example («Zum Beispiel: «Je vends et je pars …»»). A suggested reply has no foreign gloss. | `season/runtime.py` (`hint_for`), `daily_journey.py` (`_help_content`) | — |
| 18 | «Pardon, on commence maintenant ou quand ?» | A forced-choice recast only between two forms of one word, and never over an agreement written with «(e)» | `journey_conversation.py` (`_same_word_two_forms`) | — |
| 19 | «Une fois rentrée, Marie a diné.» refused for «dîné» (found by the final run) | The participle's «-é» is strict only when the slip is in the ending | `answer_acceptance.py` (`_accent_strict_word`) | `check_grading` |

Tests updated for intended behaviour (each change is commented in the test):
- `test_rule_step_regressions.test_the_prompt_names_no_catalogue_title` now pins `_RECOGNISE_USE`.
- `test_journey_capabilities.test_a_slipped_register_explains_itself_rather_than_scolding` pinned the *unformatted* template, so the defect was in the test. It now expects the formatted sentence, which is what the live corrector shows.
- `test_wp36_self_repair.test_a_whole_sentence_choice_reads_as_one_question` pinned «Pardon, on commence maintenant ou quand ?». That is a change of content, so the prompt now asks again. The «Marie est venu ou venue ?» half is unchanged.

**CI.** Add `WALK=1 pytest -m walk tests/test_experience_walk.py` (about 15 minutes) to the walk job, next to the learner walk. I did not edit the workflow files, because another session is editing them.

### 7.1 Before and after — the defects

Counted by the walk's checks over the same 15 lives (the after run is the final code: 12 lives from the final run, and the three lives that still failed it re-played after the last two fixes).

| Measure (15 lives × 30 days) | Before | After |
|---|---:|---:|
| B1+ vocabulary items | 259 | 123 |
| B1+ vocabulary items on a grammar word or a number | 153 | 0 |
| English shown to a German learner | 749 | 0 |
| Rappel items calling another day's rule «today» | 536 | 0 |
| day 1 opening with a gender guess | 3 | 0 |
| days with > 150 words due | 60 | 0 |
| letters asking a learner for a unit 3+ levels below | 182 | 0 |
| repairs of a give-up | 115 | 0 |
| suggested replies glossed with the question's translation | 236 | 0 |
| unassessed letters told something is missing | 242 | 0 |
| **all walk problems** (the final checks over both runs) | 1,825 | 0 |
| wishes corrected to «je voudrais» | 58 | 0 |
| «Schreib richtig, was du gesagt hast» items | 418 | 0 |

*B1+ vocabulary items fell from 259 to 123: the grammar-word anchors are gone, and a scene does not always hold a word at the learner's band. B1+ practice volume is owner decision 4.*

### 7.2 Before and after — the month

The strong lives, before → after:

| Life | New words in 30 days | Rules in 30 days | Due peak | Words known, day 30 | Level, day 30 |
|---|---|---|---|---|---|
| A1 de strong | 237 → **237** | 16 → **16** | 19 → **21** | 196 → **194** | A1.1 · 35 % → **A1.1 · 35 %** |
| A2 de strong | 237 → **237** | 16 → **16** | 33 → **16** | 189 → **190** | A2.1 · 22 % → **A2.1 · 22 %** |
| B1 en strong | 206 → **240** | 13 → **16** | 103 → **19** | 183 → **190** | B1.1 · 17 % → **B1.1 · 17 %** |
| B2 en strong | 185 → **240** | 11 → **16** | 300 → **16** | 69 → **164** | B2.1 · 4 % → **B2.1 · 11 %** |
| C1 de strong | 185 → **240** | 11 → **16** | 300 → **31** | 55 → **167** | C1.1 · 2 % → **C1.1 · 6 %** |

The B2 and C1 learners' month changes most: the drill no longer re-checks proved words, so the throttle no longer halves new words and units. Their word knowledge on day 30 more than doubles, and their level line moves (4 % → 11 %, 2 % → 6 %).

### 7.3 The standard learner walk

`WALK=1 pytest tests/test_learner_walk.py -m walk`: **5/5 thirty-day lives pass**. After the harness fix they ran inside the season for every persona from day 3 on. The fast tier passes **16/16**. The new checks (`check_repairs`, `check_rule_of_today`, `check_wishes_are_not_corrected`, `check_life`) run in both tiers and in the life walk.

---

## 8. Owner decisions, ranked

1. **Keep a lost day inside the season.**
   - *Today:* when a generated day fails, an off-season authored scene stands in (a stranger's welcome, the vous of strangers), and the season does not advance. The paid A2 read lost 3 of 8 gap days this way.
   - *Recommendation:* (a) For a season life, the stand-in is a **reprise day** of the last season page: the page reread in the «Lecture» step, practice from its lines, and an honest one-line note («Aujourd'hui, on relit.»). (b) Two lost days in a row play the **next tentpole day**, which is authored and needs no model; the gap is shortened, never the story. (c) The three generic scenes are never served to a season life.
2. **Place on day 1, and run the vocabulary check top-down.**
   - *Today:* B2 and C1 learners live 3 days at B1.1. The placement is offered on day 4. Then the vocabulary check runs 8 checks bottom-up (192 items, about 18 minutes), and a 24-item, 90 % gate fails a 92 % learner about 30 % of the time.
   - *Recommendation:* (a) Offer the placement right after day 1's ending to «some» and «comfortable». (b) Add «B2» and «C1+» answers to «Votre français ?». (c) Check the highest band below the learner's first. A pass credits it and every band below; a miss steps down one band. (d) Pass at ≥ 21 of 24 (87.5 %).
   - (e) Never offer the placement to «Nouveau» on own-band evidence: fix `journey_placement_evidence` to count only *above-band* replies. *Small, but it changes WP-75's rule.*
3. **Make the time promise true.**
   - *Today:* the Régulier day is 10 minutes in name. The A1 journey runs 11–14 minutes (over budget 24–29 days of 30), and B1+ runs 4–7. With the drill, letters and La Forge's chip, the learner's real day is 15–26 minutes.
   - *Recommendation:*
     - a level-aware reading prior (A1 0.75, A2 0.6, B1 0.45, B2 0.38, C1 0.32 s a token) and a measured bound up to 1.0;
     - B1+ practice that fills its budget with production at the learner's level;
     - La Une says «10 min + mots (≈ 4 min)» rather than one number.
4. **Practice volume and interleaving at B1+.**
   - *Today:* about 4 items a day, mostly today's unit. *Recommendation:* 8–10 items, half of them interleaved contrasts with partner units (`contrast_partners`), as transforms.
5. **Let grammar progress be seen.**
   - *Today:* nobody holds a unit in the first month, while the notebook says «Solide».
   - *Recommendation:* (a) Pose one «Réemploi» reply target 7–10 days after a unit's introduction, instead of waiting for stability ≥ 10, so «Tenue» can land in about 3 weeks. (b) The level line shows «Grammaire : 6 en route · 0 tenues». (c) The notebook uses the same words as the level.
6. **A word missed in a letter is not an error.**
   - *Today:* a target word the learner did not use becomes an erratum and downgrades the verdict to «partial».
   - *Recommendation:* record it as a missed opportunity (the word stays due), never as a repair and never as a lower verdict.
7. **Two bible lines** (the bible is owner-approved; `season_check` guards it).
   - (a) T2 B «double»: give the key a beat on the page, e.g. Lila: «Un double… (elle le serre dans sa main) Sept heures. Tu ne m'entendras pas.»
   - (b) At A1, allow three glossed past chunks («elle est partie», «c'était», «elle savait») for Odile's past, so a dead woman does not read as leaving now.
8. **A paid read of generated days before s1 reaches every new life.**
   - Recommendation: 10 days each at A1, B1 and C1, **cap US$3**, read by hand like the A2 read.
   - Measure the lost-day rate after the fixes made since 2026-09-30.
   - Measure rule-in-scene compliance (`grammar_plan.introduce`) and the teacher voice.
9. **The drill's session cap against the quotas.**
   - *Today:* `review.tsx` asks for at most 8 new words a session, and «Encore» adds none. Soutenu (18) and Intensif (30) cannot reach their quota in one sitting.
   - *Recommendation:* ask for `new_limit = remaining quota`; the server already clamps it.
10. **Claims about levels.**
    - The app's own gates put Régulier B2 at about 68–151 hours, 3–5 times below classroom norms, because they measure syllabus coverage.
    - Recommendation: validate the épreuve against an external test (DELF sample papers) before any «B2 in N months» claim reaches a learner.

---

## 9. Verification

| Suite | Result |
|---|---|
| `tests/test_experience_review_2026_10_04.py` | 44 passed |
| Learner walk, fast tier (`tests/test_learner_walk.py`) | 16 passed |
| Learner walk, long tier (`-m walk`, 5 × 30 days) | 5 passed |
| Life walk (`tests/test_experience_walk.py -m walk`, 15 × 30 days) | 15 passed: 12 from the final run, plus the 3 that the last two fixes concerned, re-played |
| `pytest` (full backend, serial) | 6,151 passed, 35 skipped, 12 failed |
| web-frontend `npm test` | 887/887 (no frontend file changed) |
| `npx tsc --noEmit` | clean |
| `ruff` on every touched file | clean, apart from two warnings already in `season/runtime.py` at HEAD |

**The 12 full-suite failures.**
- **2 were order-dependent, and are fixed.** `test_journey_contract_parity::test_an_empty_queue_still_reaches_a_real_ending` and `test_journey_end_to_end::test_a_failing_learner_is_never_shown_a_success` already fail at HEAD after `test_core_lexicon_supply`. That suite left an imported «pas» card behind, and it became the next suites' scene word. Its cleanup now covers that deck, and the three files pass together.
- **10 are outside this review**, and were already reported in EXERCISE-QA:
  - `test_wp69_schema_guard` (8): the production-hardening session's migration `b9d1f3a5c7e0` is not applied to the test database.
  - `test_mobile_capture_harness` (1): that session edited the capture script.
  - `test_revue_relecture` (1): a pydantic forward reference, `Rubric`.

**Files.** Production: `answer_acceptance.py`, `band_check.py`, `daily_journey.py`, `grammar_items.py`, `journey_capabilities.py`, `journey_contracts.py`, `journey_conversation.py`, `journey_learning.py`, `journey_planner.py`, `learner_copy.py`, `missions.py`, `pragmatics.py`, `season/runtime.py`, `story_correspondence.py`, `vocabulary_credit.py`. Tests: `tests/experience_walk.py` (new), `tests/test_experience_walk.py` (new), `tests/test_experience_review_2026_10_04.py` (new), `tests/learner_walk.py`, `tests/walk_checks.py`, `tests/test_learner_walk.py`, `tests/test_season_one.py`, `tests/test_rule_step_regressions.py`, `tests/test_journey_capabilities.py`, `tests/test_wp36_self_repair.py`, `tests/test_core_lexicon_supply.py`. Nothing was committed; another session shares the checkout.
