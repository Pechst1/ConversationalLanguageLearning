# «Le Papier» — premier tirage: the first run on a real model (2026-11-22)

Branch `claude/papier-integration`. Every Revue prompt ran for the first time on a real model: OpenAI
`gpt-6-luna` (production's `OPENAI_MODEL`, `render.yaml`), `reasoning_effort=low`, JSON mode. The desks that
default to a Claude model (`REVUE_COMPTOIR_MODEL=claude-haiku-5-5`) ran on `gpt-6-luna` for this run only
(process environment; no committed default changed); Anthropic was refused in-process. One illustration with
the production image model (`gpt-image-2.5-sunburst`, the worker's value).

## Money

A spend meter (scratchpad `meter.py`, the pattern of `tests/gold_transcripts/runner.py`'s `Meter`) wrapped
`OpenAIProvider._generate_once` (every HTTP attempt) and `plates._call` in every process of the run (desk
scripts, edit script, the walk's API): each call reserved its worst case in a file-locked ledger before it was
sent and was refused past US$3.00 (pictures: US$0.20). Nothing was refused.

| | calls | US$ |
|---|---:|---:|
| intake over the RSS fixtures (6 dossiers) | 6 | 0.0056 |
| builder on the six real stories (twice: builder v3, v4) | 12 | 0.0142 |
| lead desk | 6 | 0.0021 |
| «Au comptoir» desk (4 runs) | 33 | 0.0559 |
| «Le fil» desk (2 runs) | 10 | 0.0040 |
| «Le titre» desk (7 runs) | 92 | 0.0859 |
| «L'intox express» desk (6 runs) | 79 | 0.1178 |
| «Le micro» desk (5 runs) | 63 | 0.0887 |
| Romy's edits, 32 learner texts | 32 | 0.0079 |
| the browser walk (three sessions, real Romy) | 9 | 0.0024 |
| one story illustration | 1 | 0.0600 |
| **total** | **343** | **0.4445** |

Costs are the repo's own (`LLMResult.cost`, `TEXT_PRICES_PER_1K_TOKENS`; the image at
`picture_cost_usd()`). One morning's desks on one story cost about **US$0.011** (all desks, up to three
tries each), plus US$0.06 when its picture is painted.

## The stories

- **The RSS fixtures** (`tests/fixtures/revue_rss`, fetch disabled, real builder): 6 dossiers built, none
  rejected (Matisse au Grand Palais, les vendanges en Bourgogne, la ligne 14 à Orly, la Nuit blanche, l'Arc,
  le budget 2027), the shooting in Lyon and the English item filtered at intake as designed. They are
  synthetic and thin (four sentences an article), so the desks ran on real reporting instead:
- **Six real stories**, built by the real builder (`LLMDossierProvider`) from the verbatim source excerpts the
  repo holds for week 40 (`app/services/revue/weekly/2026-W40/sources/*.txt`, franceinfo, ActuaLitté, ICI,
  Equidia/AFP, ABC Bourse/Insee, La finance pour tous): culture (Goncourt), food (fresh-produce prices), city
  (Paris heat plan; the fuel cheque), sport (the Arc), politics (budget 2027 — the one the comptoir must skip).
  Throwaway database `papier_tirage_run`, period 2026-W40, dropped at the end.
- **Desks** exactly as `app/tasks/revue.py` chains them (leads → comptoir → photos → fil → titre, intox, photo,
  micro), all switches on.

## Pass rate per desk (non-sensitive stories; the budget story is a correct `skip` everywhere)

| desk | first run (as shipped) | after the fixes | what refused |
|---|---|---|---|
| builder | 6/6 | 6/6 | repaired: a visual word dropped, one claim not grounded in its quote, a lead headline too long |
| leads | 6/6 (built with the dossier) | 6/6 | one headline too long, repaired |
| Au comptoir | 3/5 (+budget skipped ✓) | 3/5 | the Arc and the heat plan: Gus's lie had no distractor of its kind |
| Le fil | **0/5, all `skip`** | 0/5 | honest: no story's claims state four events in an order (see below) |
| Le titre | **0/5** | **4/5** | Goncourt: a name not in the claims |
| L'intox express | **0/5, all `skip`** | 0–1/5 | distractors, false values found in the article, lines one word too long |
| Le micro | **0/5 (3 `skip`)** | 2/5 | a1 answers that paraphrase instead of saying the value |
| La photo | 0/5 | not reached | no story had two pictures (Commons, below) |

«Repaired on retry»: of the passes after the fixes, titre 4/4 needed the 2nd or 3rd try, micro 1/2, comptoir 1/3.
Every refusal, raw answer and retry is in the run's records (scratchpad `out/desks-*.json`, not committed).

## Read like an editor and a teacher

### Goncourt — «Le Goncourt retire un roman de sa première sélection» (culture)

Claims: «Le 25 septembre 2026, l'Académie Goncourt retire C'était ça ou mourir de sa première sélection.» ·
«L'Académie Goncourt estime que le roman est probablement largement produit par une intelligence artificielle.» ·
«Thélyson Orélien conteste avoir utilisé l'intelligence artificielle et dénonce une volonté de le faire taire.» ·
«Le roman reste dans les premières sélections du Renaudot, du Femina, du Médicis et du Prix Décembre.»

- Lead a1: «L'Académie Goncourt retire un roman de sa sélection. Le livre est de Thélyson Orélien. Il reste dans 4
  autres sélections.» — really A1, clean. «4 autres» in digits reads like a form (the lead rules ask for digits).
- **Au comptoir** «Faut-il garder ce roman dans la sélection ?» — the best material of the run.
  Lila (contre, b1): «Mais si on commence à soupçonner tout le monde, qui va lire les livres ?» Gus (nuance) lies
  about the author's first name, «Théodore Orélien», and when caught: «Thélyson, bien sûr. Mon carnet a fourché.»
  Romy's quote «Un soupçon n'est pas une preuve.» Characters sound like themselves (Romy's «voyons donc», Gus's
  «Règle numéro un de La Méthode»). Weak: Romy is «pour» (keep the novel) but her a1/a2 say «le 25 septembre, le
  Goncourt le retire» — a learner reads her as being for the withdrawal. The pick after the catch is «l'Académie
  Goncourt» vs «Thélyson Orélien» for «le vrai nom de l'auteur»: guessable.
- Le titre (refused in the final run; earlier passes): honest «Le Goncourt retire un roman», exaggerated
  «Le roman vient sûrement de l'IA» — **wrong for the wrong reason**: «sûrement» means "probably" in French; the
  check refused it (stretch_kind) and the prompt now names the certainty words.
- L'intox express (refused): «Un éditeur produit probablement largement le roman.» as a false «who» — not
  guessable, good; but the round fell on «4 autres prix» as a distractor for a date and lines a word too long.
- Le micro (refused): fact 5 quoted prize names the claim does not carry; a1 answers dropped the value.
- Photos: «Tour Eiffel» (the stage, not the story), «roman» → *Roman Theatre in Orange 2008* (kept!), «sélection»
  → *Selection on the ramp at Auschwitz-Birkenau, 1944* (refused only by the person rule). Fixed, see below.

### Les prix des produits frais accélèrent (food)

Claims: 3 % (prix à la consommation), 9,9 % (produits frais), 1,5 % après 1,1 % (alimentaires), résultats le 15 octobre.

- Lead a2: «En septembre 2026, les produits frais augmentent de 9,9 % sur un an. Les prix alimentaires montent de
  1,5 %, après 1,1 % en août. …» — correct, A2-ish, flat.
- **Au comptoir** «Les produits frais vont-ils coûter trop cher ?» (v8) — the question is a forecast, so «pour»
  and «contre» make no sense: Romy: «Je suis pour cette hausse : … Au Québec, on sait qu'un bon repas vaut son
  prix.» and in b1 «voyons donc, on ne va pas dîner au hockey» (nonsense). Gus's lie «19,9 % sur un an» against
  «9,9 %», distractor «1,5 % sur un an» — fair. Margaux: «ça fait mal au portefeuille» — fine, ordinary.
- **Le titre** (final): honest «Les produits frais montent de 9,9 %», exaggerated «Les produits frais montent
  toujours de 9,9 %» — **ambiguous**: «toujours» here reads as "still", which is true; the why («une hausse en
  septembre, pas une hausse permanente») only works for one reading. Off «Les résultats arrivent le 15 octobre» ✓.
  An earlier pass (v6) offered build tiles «Les prix alimentaires» + «progressent de 9,9 %»: **a false headline a
  beginner could print** — now refused (pair check).
- **Le micro** (Margaux): five facts, tiles correct («De combien est-ce que les prix alimentaires progressent ?»),
  answers flat: «Les produits frais affichent une hausse de 9,9 % sur un an.» — no voice at all. Romy's note
  «Combien augmente la hausse ?» is bad French (a rise that rises). An interview with a barmaid «qui était là»
  about national Insee figures does not hold as fiction, and her shrug «l'article ne donne pas cette
  information» breaks it outright.

### Paris prépare la ville aux fortes chaleurs (city) — the illustrated story

Claims: 100 voiles d'ombrage pour l'été 2027 · baignade dans la Seine plus tôt si la température le nécessite ·
une salle rafraîchie dans chaque école, crèche et collège dès 2027.

- The **illustration** (`tirage-a2de-titre-1-lire.png`): a giant thermometer over a map of Paris, yellow and red
  shade sails, a swimmer in the Seine, a class under a sail («À l'ombre on apprend mieux» on the board). Beautiful,
  and the story can be told from it. Invented: the thermometer's 36–40°.
- **Le titre** (played in the browser): honest «Paris annonce 100 nouveaux voiles pour l'été 2027», exaggerated
  «… 200 nouveaux voiles …» (why «Der Artikel kündigt 100 Sonnensegel an, nicht 200.»), off «Dès 2027, chaque école
  aura une salle fraîche». The exaggeration is the laziest one (a number doubled) and the trap that follows asks
  the same question again. The «off» one is arguably news, not a detail. The trap struck «200 **nouveaux voiles**»
  as «saying too much» — true words struck; fixed (`titre-desk-v3`, `too_wide`), the final desk's wrong_fr is «200».
- Au comptoir refused (Gus's year «2028» had only a month as distractor); intox refused («juin» not in the claim —
  the builder's v4 claim dropped it); micro refused (a1 answers ungrounded).
- Early comptoir draft (refused, v1) had the run's funniest line: Romy «Je cours dehors, mais je ne suis pas une
  friteuse.»

### Seize chevaux au départ de l'Arc de Triomphe (sport)

- Lead a1: «Le 4 octobre 2026, 16 chevaux courent à ParisLongchamp. La course fait 2 400 mètres. Le gagnant
  reçoit plus de 2,8 millions d'euros.» ✓
- **Le titre** (final): honest «16 chevaux courent à ParisLongchamp», exaggerated «30 chevaux courent…» (why
  «L'article annonce 16 chevaux, pas 30.»), off «La course fait 2 400 mètres» — correct, clean, a bit dry.
- **Le micro** (Margaux, v7): six good tiles («Combien de mètres est-ce que la course fait ?»), but her lines:
  «Le 4 octobre 2026. J'ai rien entendu.» (contradicts itself) and «2 400 mètres. Ça finira bien, ou ça finira.
  Bois.» (nonsense).
- Comptoir (v4, later refused): Gus «plus de 8,2 millions d'euros» for 2,8 — a good digit-swap lie; distractor
  «16 chevaux» for a sum — guessable (now refused for the intox express; the comptoir keeps its old rule, see below).
- Intox first try (v2): «La course fait 5 millions de mètres» — absurd, guessable; the prompt now asks for
  plausible values.

### Un chèque pour les grands rouleurs (city/consumer)

- **Au comptoir** «Ce chèque aide-t-il les grands rouleurs ?»: the landlord Marchand «Vous comptez vraiment sur 100
  euros pour tout payer ?», Gus lies «200 euros» (distractor «40 centimes par litre» — a sum for a sum, fair).
- **Le titre** (final): honest «Chèque de 100 euros pour grands rouleurs» (a1 and b1 identical — the b1 band is
  wasted), exaggerated «Chèque de 200 euros…»; an earlier pass used «tous» («100 euros pour tous les grands
  rouleurs», why «il n'est pas promis à tous») — the better exaggeration.
- **L'intox express** (v6, the one round that passed): «Un chèque de 90 euros est prévu» / «Le plafond passe à 120
  euros par an» against true 100 and 140 — each false for one number, not guessable without reading. ✓
- The story mixes the fuel cheque with the gas price and medical franchises (the source's «ce qui change au 1er
  octobre»): the off headline «Le prix du gaz augmente de 6,3 %» is a different story, not a detail.

### Le budget 2027 (politics) — the sensitive one

Comptoir `skip` → titre, intox, photo, micro and fil all `skip` without a call. ✓ Leads written (a1: «Il propose
de moins augmenter les pensions de plus de 1 260 euros.» — correct). Photos were still searched (see below).

### Le fil, on every story: `skip`

The wire needs four events whose order the claims state. Real dossiers carry 3–4 claims, mostly states
(«le roman reste…», «la course fait 2 400 mètres»), rarely dated events. The model was right to skip; the fil will
almost never be dealt with today's builder. Not loosened (an order the claims do not state would teach a guess).
The builder now keeps the quote's absolute date in each claim (v4), which is the precondition; it was not enough
on these six stories.

### Verdict

Where a regular argues with the learner, it is good and sometimes funny (Lila, Marchand, Gus's lies and catches).
Where the material is a set of checked fragments (headline triplets, statements, interview facts), the small
model writes correct but flat French and fails the checks' word limits more often than it fails the facts.
Wrong-for-the-wrong-reason and guessable items were real (sûrement, toujours, «200 nouveaux voiles», cross-kind
distractors, a false build tile) and are now refused where code can tell.

| the five best lines | the five worst lines |
|---|---|
| «Mais si on commence à soupçonner tout le monde, qui va lire les livres ?» — Lila | «Combien augmente la hausse ?» — Romy's interview note |
| «Thélyson, bien sûr. Mon carnet a fourché.» — Gus, caught | «Le 4 octobre 2026. J'ai rien entendu.» — Margaux |
| «Je cours dehors, mais je ne suis pas une friteuse.» — Romy (draft) | «2 400 mètres. Ça finira bien, ou ça finira. Bois.» — Margaux |
| «Vous comptez vraiment sur 100 euros pour tout payer ?» — M. Marchand | «Les produits frais montent toujours de 9,9 %» — the "exaggerated" headline that reads as true |
| «Court pour le bruit, bon pour la caisse.» — Margaux on the Arc | «Je suis pour cette hausse … on ne va pas dîner au hockey.» — Romy |

## Romy's edits on real learner French

Through the loops' own proofread functions (`comptoir_loop._proofread`, `fil_loop._proofread`,
`titre_loop._proofread`, `rubrique_proof.proofread` for photo and micro), real provider, «Le pourquoi» on, the
explanation language forced to the learner's (de / en). «Raconter» used the shipped bac wire (no real story got a
wire). Four texts per surface: A2 German (de), B1 English (en), one correct, one with a stylistic choice.

| surface | case | learner text (errors) | marks | verdict |
|---|---|---|---|---|
| Ton avis | A2 de | «…parce que un prix est pour les écrivains et la machine n'a pas écrit son livre seul. Je suis sicher que…» | «que un»→qu'un (orthographe), «seul»→seule (accord), «sicher»→sûr (mot) | 3/2 — all right; «seule» was a real slip I had not counted. Hints in German, no answer given. |
| Ton avis | B1 en | «…c'est actuellement un scandale… Les jurés ont devenu des juges.» | «ont devenu»→sont devenus | 1/2: the false friend «actuellement» (grammatical, wrong meaning) not marked; the hint was refused as too long, so no hint showed |
| Ton avis | correct | «À mon avis, ça dépend, parce que l'Académie n'a pas de preuve, mais le roman reste dans quatre autres sélections.» | clean ✓ | |
| Ton avis | style | «Franchement ? Un roman écrit par une machine, non merci. Moi, je veux lire des humains.» | clean ✓ | untouched |
| Raconter | A2 de | «…beaucoup de élèves… les élèves sont content.» | «de élèves»→d'élèves, «content»→contents | 2/2 ✓; the de-hint «mit dem folgenden Artikel verkürzt» is imprecise (there is no article) |
| Raconter | B1 en | «…le premier examen a lieu en 1809 … bien que les élèves le préférent.» | «préférent»→préfèrent | 1/1 (the historical present «a lieu» is acceptable); the why teaches the subjunctive, the slip was the accent |
| Raconter | correct / style | (telegraphic «1808 : naissance du bac.») | clean ✓ ✓ | |
| À toi (titre) | A2 de | «16 Pferde courent le Prix de l'Arc à ParisLongchamp» | «Pferde»→chevaux | ✓, «Im Artikel: … 16 chevaux doivent courir …» a real match |
| À toi (titre) | B1 en | «… seize chevaux vont couru à ParisLongchamp» | «couru»→courir | ✓ hint «the verb after « aller » stays in the infinitive» — rule, not answer |
| À toi (titre) | correct / style | «Arc de Triomphe : seize chevaux, deux minutes, un vainqueur» | clean ✓ ✓ | |
| À toi (légende) | A2 de | «Die Seine à Paris. … pour les école en 2027.» | «Die»→La, «école»→écoles | ✓ ✓, both with a real «Im Artikel» sentence |
| À toi (légende) | B1 en | «… a decidé … il faut que les gens peuvent nager …» | «decidé»→décidé, «peuvent»→puissent | ✓ ✓ subjunctive hint names the rule |
| À toi (légende) | correct / style | «La Seine, en plein été. Bientôt, on pourra s'y baigner plus tôt — si la chaleur l'exige.» | clean ✓ ✓ | |
| Relis tes questions | A2 de | «Combien de chevaux est-ce que courent ? Quand la course commence ? Combien d'argent le gagner reçoit ?» | **before the fix**: «chevaux» (manque), «courent ? Quand» (ordre) — **wrong marks**, across two questions; after: «que»→qui, «Quand»→Quand est-ce que, «d'argent» + est-ce que | 3 marks, all inside their question; «gagner»→gagnant fixed in the target but unmarked (three-mark cap) |
| Relis tes questions | B1 en | «… Daryz va gagné ?» | «gagné»→gagner | ✓ |
| Relis tes questions | correct | | clean ✓ | |
| Relis tes questions | style | «Seize chevaux, vraiment ? Et la course, elle dure combien de temps ? Le vainqueur, il gagne quoi ?» | three «ordre» marks: rewritten to inversion | **touched a stylistic choice** — the edit rule asks for written question form, so it is policy, not a bug; the owner should decide |

**Every wrong mark** a learner would have seen: (1) «chevaux · manque» and «courent ? Quand · ordre» (marks
across questions; fixed, `proof_marks` and the pourquoi fixes sentence by sentence); (2) in the browser,
«que il · Wortwahl» for an elision (fixed: «que il» → «qu'il» is spelling, every time it stands); (3) in the browser,
«De combien est la hausse des produits frais ?» marked «est · Wortstellung», «frais · Wortstellung» in round 1 and
accepted unchanged in round 2 — a correction the next check did not stand by (not fixed); (4) the spoken-style
questions rewritten (policy). The printed text was right in every case («DANS LE JOURNAL · CORRIGÉ PAR ROMY»).
`why_hint` was in the learner's language every time and never gave the corrected form; `why_full` teaches (once
with a German neologism, «pluralisch»). Every «Im Artikel / Dans l'article» example was a real sentence of the story
with the form in it.

## Photos: the live Commons API

Reached only through HTTP/2 and only intermittently: every httpx HTTP/1.1 request was answered 403 «Please
respect our robot policy» whatever the User-Agent (curl and HTTP/2 got 200 or 429), and the shared egress was
rate-limited (429) for most of an hour. Three of six stories were searched, between 429s.

| story | subjects searched | Commons returned | the filter kept | shows the story? |
|---|---|---|---|---|
| budget 2027 | «Arc de Triomphe, place Charles-de-Gaulle», «budget», «pensions» | the Arc at night (CC0); EU/NZ budget charts and the Ukrainian defence budget infographic; a Czech guesthouse «pension U rytíře» | all three: the Arc, the infographic (JPEG), the guesthouse | **no** — the stage landmark, a war-ministry chart, a homograph |
| Goncourt | «Tour Eiffel» (429), «roman», «sélection» | Roman theatre in Orange, Roman (Romania); sexual-selection diagrams, **the Auschwitz-Birkenau ramp, 1944** | the Roman theatre; Auschwitz refused only as «person» | **no** |
| others | 429 | — | — | — |

Fixed (guards first, both answers recorded and trimmed as fixtures, `tests/fixtures/commons/live_2026-11-22_*.json`):
HTTP/2 client; a failed search records nothing and stops the morning (it was stored as «searched, 0 photos», never
retried); a stage place is searched only when the story names it; single-noun objects are not searched (homographs);
charts, diagrams, maps, logos are not photos; Holocaust, massacre, war crimes, corpses, weapons, military are
refused as «sensitive» with or without people. Licence allow-list and the no-person rule unchanged.
**No story got two pictures, so «La photo» was never dealt and no real photo was seen in the browser.**

## What changed (commits on this branch) — before → after on the same stories

| change | before | after |
|---|---|---|
| intox/micro fit: skip only for sensitive stories or < 3 claims (`intox-express-v2`, `micro-desk-v2`) | intox 5/5 skip, micro 3/5 skip | no skip; intox 1/5, micro 1/5 passed |
| titre certainty words (`sûrement` excluded), facts in the claim's verbs (`titre-desk-v2`) | 0/5 | 1/5 (same stories) |
| comptoir: a number's distractor is a number of the same kind (`comptoir-takes-v4`) | 3/5 (canicules: month for a year) | 5/5 on the v3 stories, 3/5 on v4 |
| builder v4: numbers in digits, the quote's date in each claim | «Seize», «Cent» in words; dates dropped | digits and dates; fewer number refusals |
| retry carries the refused answer + how to read the codes; 3 tries | second try rewrote everything | titre 0/5 → 1/5 (2 tries) → 4/5 (3 tries) |
| micro: a refused fact is left out while 5 stand | 0/5 | 2/5 |
| intox express: distractor of the same kind (`value_kind`) | «4 autres prix» for a date accepted | refused (0–1/5) |
| titre: `wrong_fr` never a word the honest headline says (`titre-desk-v3`) | trap struck «nouveaux voiles» | wrong_fr «200», «toujours», «tous» |
| titre: every subject × fact tile pair rests on one claim; a refused tile is left out | a false build tile shipped (v6, 4/5 incl. 1 false) | 1/5 without salvage → **4/5** with it, all pairs true |
| marks per sentence; elision is spelling; hint for every occurrence | wrong marks across questions, «Wortwahl» | marks inside their question, «Rechtschreibung» |
| La page: `%`/thousands never break; headline typeset | «9,9» / «% sur un an» on two lines; «d'ombrage» | `tirage-a2de-micro-6-page-after.png` |

The comptoir's own distractor check keeps `numeric`: four authored evergreens pair a count with a date or an age
(«près de 2 millions de visiteurs» / «depuis 1570», Tour de France, rentrée, marché) — the same guessable pick,
which needs an editor, not a code change. **Recommended next:** salvage for the intox express (write seven
statements, keep three true and two false that pass), and a builder rule for dated event claims so «Le fil» can be
dealt at all.

## The browser walk (real provider)

The walk stack's pieces (throwaway `atelier_walk_tirage_*` database, migrations, lexicon, `next dev`) with the
**real** Revue provider behind the spend meter, Romy's vignette pictogram on its fake (out of scope); the run's six
dossiers seeded as week-47 rows (walk-only, not committed), the painted picture served from local storage;
three new German A2 learners (one Papier per learner and week), the deal pinned per story for the walk only
(Goncourt → Au comptoir, heat plan → Le titre, fresh produce → Le micro), the latter two started through
`POST /revue/sessions` because the chooser offers three stories. 375 × 812, deviceScaleFactor 2; the API, the web
server and the database were stopped and dropped at the end.

Seen: the chooser and the comptoir from the real takes; Gus's false name caught; a real A2 opinion with four slips
marked over two rounds, printed corrected under «Toi, au comptoir · corrigé par Romy»; the real illustration on Lire
and on La page; a 3-line honest headline in the proof with loop and strike; the learner's headline fixed and
corrected; a real interview with a shrug; the questions marked and printed in the Q&A page.
Layout faults real text exposed, and fixed: the pull quote's «9,9 %» broke across lines; straight apostrophes in the
printed learner headline; the trap struck true words (content). Long answers, three-line headlines and the
four-mark notes all fit at 375 px; no horizontal scroll on the screens checked (the driver read `scrollWidth` after each act).

### Screenshots (19, ≤ 750 px, 128 colours)

Open first: `tirage-a2de-titre-5-page.png` (the real illustration under the learner's corrected headline),
`tirage-a2de-comptoir-4-avis-done.png` (real slips and whys), `tirage-a2de-titre-3-trap.png` (the trap fault),
`tirage-a2de-micro-6-page-before.png` / `-after.png` (the % break and its fix).

`tirage-a2de-0-chooser` · `tirage-a2de-comptoir-2-takes` · `-3-fixed` · `-4-avis-marked` · `-4-avis-done` ·
`-5-page` (+ `-dark`) · `tirage-a2de-titre-1-lire` · `-2-right` · `-3-trap` · `-4-marked` · `-5-page` (+ `-dark`) ·
`tirage-a2de-micro-2-prepare` · `-3-interview-done` · `-5-marked` · `-6-page-before` · `-6-page-after` · `-6-page-dark`.

## Not run / not seen

- «La photo» with real photos, «L'intox express» and «Le fil» in the browser (no story carried them with real material).
- English B1 in the browser (the B1 English cases ran through the edit loops only).
- «Trois mots», memory lines and «La une» were on (no model call); the une and the press card were not opened.
- Painting more than one story; R2/S3 storage (the variables exist; local storage served the picture).
- The fixture-intake dossiers were built but not sent through the desks (synthetic, four sentences an article).
