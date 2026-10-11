# WP-134A — claims audit (proposal, 2026-10-04)

**Status: proposal for the owner's approval. No copy has been changed.** Several of these files belong to other Wave 1 agents, so the orchestrator applies the approved wording one file at a time.

Sources: package WP-134 «A» ([WORK-PACKAGES-2026-10-04-experience.md](WORK-PACKAGES-2026-10-04-experience.md)), review §5 and owner decision 10 ([EXPERIENCE-REVIEW-2026-10-04.md](EXPERIENCE-REVIEW-2026-10-04.md)). Inventory taken at worktree commit `6da2995` (base `cab1fb5`), backend and frontend, in en/de/fr. Line numbers are the line of the key or string.

## 1. What a claim may say

The level the app shows is one of four things. Copy must name which one.

| Class | What it is | Honest wording |
|---|---|---|
| **Self-declaration** (SD) | «Nouveau / Quelques bases / À l'aise» at sign-up, or the Réglages level list. Stored in `cefr_estimate` with `estimate_source = declared`. | «niveau déclaré» / "the level you gave" / "angegebenes Niveau". Never «votre niveau» or "current level" on its own. |
| **Placement estimate** (PE) | 4–6 written turns, with a confidence value (`placement.py`). | «niveau estimé» / "estimated level". Never "measured" and never "solid". |
| **Syllabus coverage** (SC) | The app's own sub-band (A1.1 … C1.2). It is covered when 85 % of its units are «tenues», 80 % of its core words are known and its épreuve is passed (`level_coverage.py`, `cefr_progress.py`). | Name it as the app's course: «cours {band}» / "{band} course" / "Kurs {band}". The Cahier already says «Cours · {level}». Never a bare CEFR level that someone «is» or has «validé». |
| **Demonstrated proficiency** (DP) | A unit used twice unaided, a can-do met in a written scene, the épreuve scene. | Say what was done and how: «à l'écrit», "in writing", "schriftlich", once or twice. |

**Limits that apply everywhere:**
- **Not CEFR.** No external CEFR validation exists until WP-134B. «A1.1/A1.2» are the app's sub-bands, not official CEFR levels.
- **Forecasts.** A forecast is a modeled date for the app's course milestone (`level_forecast.py`). It is labelled an estimate *and* names the milestone.
- **No audio.** None is deployed. Practice is read and written, so nothing may claim listening or speaking: no «écouter», «à l'oral», "speak", "listening" as a skill trained or shown.
- **No speed comparisons.** No claim about learning speed against Duolingo, classes or other apps.

### Problem codes

- **P1:** equates internal completion or modeled speed with CEFR attainment.
- **P2:** comparative learning-speed claim.
- **P3:** implies listening or speaking competence.
- **P4:** presents an estimate or a self-declaration as fact.
- **P5:** other overclaim, such as "mastered", "the rule is yours", "native speaker" or "held" from a single sitting.

## 2. Findings

### 2.1 P2: comparative speed claims

**There are none in learner-facing copy.** Searches for Duolingo, Babbel, «classe», classroom, faster, schneller, «plus vite», «fois plus», "twice as", fluent, fließend, «couramment», DELF, DALF, TCF and Goethe found the following:

- **Code comments only.** These are owner goals, not shown to learners: `band_check.py:3`, `concept_life.py:36`, `level_coverage.py:232`.
- **Exam names on two rule cards** (row 40 below). They mention an exam but claim no equivalence.
- **The Terms disclaimer:** "a learning aid, not a certification".

The landing page (`pages/index.tsx:53`), `_document.tsx:11` and `manifest.webmanifest:4` make no level claim.

**Keep it that way.** The review's §5 «twice as fast as the Duolingo model» is a modeled comparison. It must not reach a learner.

### 2.2 Top problems, by learner exposure

1. **The weekly forecast reads as «A2.1 by November»** (row 1). It has no "estimate" and no milestone name. This is exactly the «B2 in N months» case decision 10 rules out.
2. **CEFR level-ups and band closures carry no qualifier** (rows 2–7): «Niveau A1.2 → A2.1», «A1.2, bouclé», «Niveau A1.2 validé» after a two-minute word-recognition check, and the Relevé headline.
3. **"Held" and "mastered" are granted on one sitting** (rows 16–22). A 3-item rule check says «La règle est acquise. Tenue dès aujourd'hui». The Forge test-out says the same after 5 items. Both contradict the definition the Dossier itself gives (used twice, unaided). «maîtrisée» / "proficient" names the stage *below* «tenue». German «gefestigt» is used for both «solide» and «tenue».
4. **Self-declared levels are shown as fact** (rows 8–13): «Niveau actuel», «Prénom · A2», «Édition Nº n · A2», and «… un cran au-dessus de ton niveau» in every above-band scene objective. The "CEFR target" the learner picks is hinted «Estimée selon votre rythme réel».
5. **Speaking and listening are implied with no audio** (rows 23–33):
   - Le Carnet stamps oral can-dos from typed scenes: «présenter un exposé structuré devant un auditoire», «défendre une position dans un débat contradictoire», «parler de sa famille».
   - The épreuve pass line says «Tout le monde t'a compris ce soir».
   - The listen-first hint says «c'est cette partie-là qui travaille l'écoute».
   - The voice studio is still reachable: «Commencer à parler».
   - Other places: «à l'oral» capability evidence, "Speak to the right person the right way", the Réglages descriptors B2 «Échanger avec spontanéité» and C2 «proche d'un locuteur natif», and the grader-facing voice rubric note, which reaches the learner through `rubric_native`.
6. **Placement is called "measured"** right under "Estimated level" (row 14). The app's coverage is shown as «Couverture CECR» (row 37) and «Niveau mesuré dans l'application» (row 15).

## 3. Inventory and proposed wording

Proposed text stays terse, uses the learner's language and the file's existing register (vous/Sie or tu/du), and adds no praise. Where one string serves three languages, the rows sit together. «{band}» stays the app's sub-band code (A1.1 …).

### 3.1 Forecasts, level changes, band closure (P1)

| # | file:line | lang | current text | class | problem | proposed text |
|---|---|---|---|---|---|---|
| 1 | web-frontend/components/atelier-v2/journey/recap-copy.ts:108 | en | At this rhythm: {level} around {month}. | SC forecast | P1, P4: a CEFR code plus a month, no "estimate" | Estimate at this rhythm: the {level} course covered around {month}. |
| | …recap-copy.ts:116 | de | In diesem Rhythmus: {level} etwa im {month}. | | | Schätzung in diesem Rhythmus: Kurs {level} etwa im {month} abgedeckt. |
| | …recap-copy.ts:124 | fr | À ce rythme : {level} vers {month}. | | | Estimation à ce rythme : cours {level} couvert vers {month}. |
| 2 | …recap-copy.ts:42 (+ JourneyRecap.tsx:300 `{from_level} → {to_level}`) | en | Level | SC | P1: a CEFR level-up with no qualifier | Course |
| | …recap-copy.ts:58 | de | Niveau | | | Kurs |
| | …recap-copy.ts:73 | fr | Niveau | | | Cours |
| 3 | web-frontend/components/releve/Releve.tsx:323-325 | all | `{estimate} → {nextLevel}` (e.g. «A1.2 → A2.1») | SC | P1, no source line in the measured case | Prefix with the existing Cahier word: «Cours A1.2 → A2.1» / "Course A1.2 → A2.1" / "Kurs A1.2 → A2.1". In the declared and placed cases the existing source lines stay. |
| 4 | web-frontend/lib/can-do-copy.ts:104 | en | {band}, closed | SC + DP | P1: a one-day épreuve "closes" a CEFR-coded band | {band} course covered |
| | can-do-copy.ts:142 | de | {band}, abgeschlossen | | | Kurs {band} abgedeckt |
| | can-do-copy.ts:66-67 | fr | {band}, bouclé · Sceau du numéro spécial · {band} bouclé | | | Cours {band} couvert · Sceau du numéro spécial · cours {band} couvert |
| 5 | web-frontend/components/atelier-v2/band-check/band-check-copy.ts:140 | en | Level {band} confirmed | SC | P1: a 2-minute recognition check "confirms" a level | {band} words recognised |
| | band-check-copy.ts:188 | de | Niveau {band} bestätigt | | | Wörter aus {band} erkannt |
| | band-check-copy.ts:92 | fr | Niveau {band} validé | | | Mots de {band} reconnus |
| 6 | band-check-copy.ts:156 / :204 / :108 | en / de / fr | The levels below yours are already known. / Die Niveaus unter Ihrem sind schon bekannt. / Les niveaux sous le vôtre sont déjà acquis. | SC on top of SD/PE | P1, P4: "yours" may be only declared | The words of the courses below {band} already count as known. / Die Wörter der Kurse unter {band} gelten schon als bekannt. / Les mots des cours sous {band} comptent déjà comme connus. |
| 7 | web-frontend/components/atelier-v2/dossier/dossier-copy.ts:206 / :340 / :474 (forecast_prior), :207 / :341 / :475 (forecast_measured) | fr / en / de | «Estimation avant mesure, d'après votre rythme : {target} dans {span}…» / "Estimate before measuring, from your chosen pace: {target} in {span}…" / "Schätzung vor der Messung, nach Ihrem Rhythmus: {target} in {span}…" (measured: «Estimation sur vos quatorze derniers jours : {target} dans {span}…») | SC forecast | P1 (mild): `{target}` reads as a CEFR level | Replace «{target}» with «le cours {target} couvert» / "the {target} course covered" / "Kurs {target} abgedeckt". The rest stays (it is already labelled an estimate). |
| 7a | web-frontend/lib/settings-copy.ts (rhythm cards, from `level_forecast.rhythm_prior`, `level_forecast.py:344-376`, target collapsed to «A1») | all | per rhythm, "{target} in {range_months}" (rendered from the API) | SC forecast | P1: «A1 en N mois» pairs a CEFR level with a modeled duration | Render as «Cours A1 couvert : estimation N–M mois» / "A1 course covered: estimate N–M months" / "Kurs A1 abgedeckt: Schätzung N–M Monate". |

### 3.2 Self-declared and placed levels shown as fact (P4)

| # | file:line | lang | current text | class | problem | proposed text |
|---|---|---|---|---|---|---|
| 8 | web-frontend/lib/settings-copy.ts:333 | en | Current level | SD | P4 | Your declared level |
| | settings-copy.ts:552 | de | Aktuelles Niveau | | | Ihr angegebenes Niveau |
| | settings-copy.ts:775 | fr | Niveau actuel | | | Votre niveau déclaré |
| 9 | settings-copy.ts:378-379 | en | CEFR target · Estimated from your real pace. | SD | P4, P1: a picked target is called "estimated" | Course target · Your choice. The forecast below is estimated from your pace. |
| | settings-copy.ts:596-597 | de | GER-Ziel · Geschätzt nach Ihrem echten Tempo. | | | Kursziel · Ihre Wahl. Die Prognose darunter ist nach Ihrem Tempo geschätzt. |
| | settings-copy.ts:819-820 | fr | Objectif CECRL · Estimée selon votre rythme réel. | | | Objectif de cours · Votre choix. La prévision dessous est estimée sur votre rythme. |
| 10 | web-frontend/pages/settings.tsx:882 | all | kicker `{firstName} · {proficiencyLevel}` (e.g. «Prénom · A2») | SD | P4: bare code, no source | `{firstName} · {proficiencyLevel} ({source})`, using the source words the Dossier already has: «déclaré» / "declared" / "angegeben", «estimé» / "estimated" / "geschätzt", «cours» / "course" / "Kurs". |
| 11 | web-frontend/pages/atelier.tsx:2671-2672 | fr (one string for all) | Édition Nº {n} · {cefr.estimate} | SD/PE/SC | P4 | Édition Nº {n} · cours {cefr.estimate}, when `estimate_source = measured`. Otherwise drop the band: «Édition Nº {n}». |
| 12 | web-frontend/lib/can-do-copy.ts:101 / :139 / :63 (and :100 / :138 / :62) | en / de / fr | "Your level: {band}" / "Dein Niveau: {band}" / «Votre niveau : {band}» ("Level {band}. Next step: …") | SC/SD | P4: aria label with no source | "Course {band}" / "Kurs {band}" / «Cours {band}» (and "Course {band}. Next step: …") |
| 13 | app/services/journey_content.py:169 | en | This scene is written at {band}, a step above where you are. | SD/PE | P4: "where you are" may be a declaration | This scene is written at {band}, one step above your course. |
| | journey_content.py:170 | de | Diese Szene ist auf {band} geschrieben, eine Stufe über deinem Niveau. | | | Diese Szene ist auf {band} geschrieben, eine Stufe über deinem Kurs. |
| | journey_content.py:171 | fr | Cette scène est écrite au niveau {band}, un cran au-dessus de ton niveau. | | | Cette scène est écrite en {band}, un cran au-dessus de ton cours. |
| 14 | web-frontend/components/atelier-v2/dossier/dossier-copy.ts:305 | en | Measured by the placement test, on {answers}. {confidence} | PE | P4: "measured" under "Estimated level" | Estimated by the placement test, from {answers}. {confidence} |
| | dossier-copy.ts:438 | de | Gemessen im Einstufungstest, anhand von {answers}. {confidence} | | | Geschätzt im Einstufungstest, anhand von {answers}. {confidence} |
| | dossier-copy.ts:171 | fr | Mesuré par le bilan de niveau, sur {answers}. {confidence} | | | Estimé par le bilan de niveau, sur {answers}. {confidence} |
| 15 | dossier-copy.ts:300 / :433 / :166 (src_measured; also :313 / :447 / :180 "measured on your answers in sessions") | en / de / fr | Level measured in the app / In der App gemessenes Niveau / Niveau mesuré dans l'application | SC | P1 (mild): "measured level" beside a CEFR code | Course covered in the app / In der App abgedeckter Kurs / Cours couvert dans l'application |
| 15a | web-frontend/lib/placement-copy.ts:113 / :159 / :67 | en / de / fr | Let's find your level / Finden wir Ihr Niveau / Trouvons votre niveau | PE | P4 (mild) | Let's estimate your level / Schätzen wir Ihr Niveau / Estimons votre niveau |
| 15b | placement-copy.ts:135 / :181 / :89 | en / de / fr | A solid estimate / … | PE | P5 (mild): "solid" on ≤ 6 answers | A firmer estimate / Eine belastbarere Schätzung / Une estimation plus sûre (keep "fair" and "provisional") |

### 3.3 "Held" and "mastered" from a single sitting (P5)

| # | file:line | lang | current text | class | problem | proposed text |
|---|---|---|---|---|---|---|
| 16 | web-frontend/components/atelier-v2/journey/rule-test-out.ts:154-155 | en | You know it. The rule is yours. · Held from today — no need to learn it again. | DP (one check) | P5: 3 items give "held" (definition: used twice, unaided) | 3 of 3. This rule skips the lessons. · It counts as held once you use it in a reply. |
| | rule-test-out.ts:179-180 | de | Sitzt. Die Regel gehört dir. · Ab heute gefestigt — du musst sie nicht neu lernen. | | | 3 von 3. Diese Regel überspringt die Lektionen. · Gefestigt ist sie, sobald du sie in einer Antwort verwendest. |
| | rule-test-out.ts:204-205 | fr | Vous la connaissez. La règle est acquise. · Tenue dès aujourd'hui — inutile de la réapprendre. | | | 3 sur 3. Cette notion saute les leçons. · Elle sera tenue quand vous l'emploierez dans une réponse. |
| 17 | web-frontend/lib/forge-copy.ts:58 / :64-65 | en | Five items, one of them your own sentence. Pass, and the rule is yours. · The rule is yours. · {correct} of {total} right, your own sentence included. It counts as held from today. | DP (one sitting) | P5 | Five items, one of them your own sentence. Pass, and the lessons are skipped. · Lessons skipped. · {correct} of {total} right, your own sentence included. Use it once more in a reply to hold it. |
| | forge-copy.ts:102 / :108-109 | de | … Bestanden, und die Regel sitzt. · Die Regel sitzt. · … Ab heute gilt sie als gefestigt. | | | … Bestanden, und die Lektionen entfallen. · Lektionen übersprungen. · {correct} von {total} richtig, der eigene Satz inklusive. Noch einmal in einer Antwort verwenden, dann ist sie gefestigt. |
| | forge-copy.ts:146 / :152-153 | fr | … Réussie, la règle est acquise. · La règle est acquise. · … Elle est tenue dès aujourd'hui. | | | … Réussie, les leçons sont sautées. · Leçons sautées. · {correct} sur {total}, votre phrase comprise. Encore une fois dans une réponse, et elle est tenue. |
| 17a | forge-copy.ts:74 / :118 / :162 | en / de / fr | Tested out: held / Direkt geprüft: gefestigt / Épreuve réussie : tenue | DP | P5 | Tested out / Direkt geprüft / Test réussi |
| | **Owner decision** | | | | | Rows 16–17 assume the test-out keeps crediting "held" in the data model. If the owner decides a test-out *is* sufficient evidence, the Dossier definition (row 21) must change instead. One of the two has to give. |
| 18 | forge-copy.ts:89 / :133 / :177; web-frontend/lib/momentum-copy.ts:102 / :153 / :204 (and :87 / :138 / :189 "{held} held · {proficient} proficient · …") | en / de / fr | proficient / sicher / maîtrisée (the stage *below* held) | SC | P5: "mastered" ranks below "held" | practising / in Übung / en cours (`{held} held · {practising} practising · …`) |
| 19 | web-frontend/components/atelier-v2/journey/recap-copy.ts:110 / :118 / :126 | en / de / fr | {w} words and {g} rules mastered. / {w} Wörter und {g} Regeln sicher. / {w} mots et {g} règles maîtrisés. | SC | P5 | {w} words known and {g} rules held. / {w} Wörter bekannt, {g} Regeln gefestigt. / {w} mots connus et {g} notions tenues. |
| 20 | web-frontend/components/epreuve/epreuve-copy.ts:489, 493 / :661, 665 / :317, 321 | en / de / fr | Already mastered · No mistakes / Schon gemeistert · Fehlerfrei / Déjà maîtrisé · Sans faute | DP (one session) | P5 | No mistakes today · Fehlerfrei heute · Sans faute aujourd'hui (drop the "mastered" title) |
| 21 | web-frontend/components/atelier-v2/dossier/dossier-copy.ts:460 | de | Um {band} abzuschließen: 85 % der Regeln sicher beherrschen und 80 % der Wörter kennen. … | SC | P5 (de only; en and fr say "hold") | Um Kurs {band} abzudecken: 85 % der Regeln gefestigt und 80 % der Wörter bekannt. … |
| 22 | web-frontend/components/cahiers/cahier-copy.ts:354 / :613 / :92 (and :353 / :612 / :91; :503 / :762 / :242); dossier-copy.ts:294 / :427 / :160, :297 / :430 / :163 (errata); components/releve/releve-copy.ts:244-245 / :337-338 / :151-152; components/stories/ChapterGrammarPreview.tsx:65; components/lexique/lexique-copy.ts:369, 371 / :606, 608 / :843, 845 and :831 | en / de / fr | mastered / gemeistert / acquis · solid / **gefestigt** / solide · Mastery {n} out of 10 · errata "Mastered" / «Acquis» · «Carte de maîtrise», «Atlas des acquis» | SC | P5: "mastered" for a score or for an error fixed three times. DE «gefestigt» doubles as «tenue». | One vocabulary, matched to the Dossier: «tenue / held / gefestigt» only for the evidence rule; a score is «{n}/10» with no adjective; errata «corrigée 3 fois» / "fixed 3 times" / "3-mal korrigiert"; DE "solid" becomes «sicher», never «gefestigt»; «Carte des mots» / "Word map" / "Wortkarte"; «Atlas des mots». |

### 3.4 Listening and speaking with no audio deployed (P3)

| # | file:line | lang | current text | class | problem | proposed text |
|---|---|---|---|---|---|---|
| 23 | app/data/syllabus/fr_core_can_dos_v2.json:1209 (and :959, :1147, :73, :213, :492, :939, :10, :31, :94, :134, :153, :231, :290, :1126, :1334) | fr / en / de | «présenter un exposé structuré devant un auditoire» / "give a structured presentation to an audience" / "vor Publikum ein gegliedertes Referat halten"; «défendre une position dans un débat contradictoire»; «parler de sa famille»; «parler de ses projets d'avenir»; … | DP (one written scene) | P3: oral acts stamped from typed replies. The file is `review_status: "draft"`. | Keep the can-do; change how Le Carnet shows the stamp: «à l'écrit, une fois» / "in writing, once" / "schriftlich, einmal" (one source label, can-do-copy.ts). Retitle the three strongest: «rédiger un exposé structuré» / "write a structured presentation" / "ein gegliedertes Referat schreiben"; «défendre une position par écrit dans un débat» / "defend a position in writing in a debate" / "in einer Debatte schriftlich eine Position verteidigen"; and for C1 «défendre une position dans un débat contradictoire», «… par écrit». |
| 24 | web-frontend/lib/can-do-copy.ts:112 / :150 / :74 | en / de / fr | What you can do in French. Each line is stamped the first time the story shows it. | DP | P5: one occurrence becomes "can do" | What you have done in French, in writing. Each line is stamped the first time the story shows it. / Was du auf Französisch schon schriftlich getan hast. … / Ce que vous avez déjà fait en français, à l'écrit. … |
| 24a | can-do-copy.ts:124 / :162 / :86 | en / de / fr | first day / erster Tag / premier jour (stamp source) | ? | P5: a stamp not earned by the learner | Do not stamp from the authored first day. If it stays: "met on the first day" / "am ersten Tag erlebt" / «vu le premier jour». |
| 25 | app/services/living_story.py:6584-6585 (`EPREUVE_PASS_LINE_FR`, `…_VOUS`) | fr (diegetic) | Bravo ! Tout le monde t'a compris ce soir. On fête ça ? | DP | P3: "understood you" implies speech | Bravo ! Tout le monde t'a lu ce soir. On fête ça ? (vous: «vous a lu»). The host still celebrates, but in writing. Prompt `living_story.py:798-809` gets the same constraint: "the learner wrote; never imply they were heard". |
| 26 | app/services/journey_content.py:173-177 (`_VOICE_RUBRIC_NOTE`) | en / de / fr | The learner is speaking: judge meaning, not spelling or transcription artefacts. / … | n/a | P3, and grader text reaches `rubric_native` | Do not append to the learner-facing `rubric_native`; keep it grader-side only. If it must show: "Spoken reply: meaning counts, not spelling." / "Gesprochene Antwort: Der Inhalt zählt, nicht die Schreibung." / «Réponse orale : le sens compte, pas l'orthographe.» It shows only in voice mode, which is off today. |
| 27 | app/services/learner_copy.py:1119 (journey_capabilities.py:342; also web-frontend/components/atelier-v2/journey/journey-copy.ts:316 / :506 / :696, unused) | en | Speak to the right person the right way | DP (written) | P3 | Address the right person the right way (de «Die passende Anrede treffen» and fr «S'adresser comme il faut» are fine) |
| 28 | web-frontend/components/atelier-v2/dossier/dossier-copy.ts:372 / :506 / :238 | en / de / fr | spoken / mündlich / à l'oral (capability evidence modality) | DP | P3 if it can print while voice is off | Print only when the evidence row's modality is voice; with no audio deployed this branch is dead. No wording change; add a guard. |
| 29 | web-frontend/components/atelier-v2/journey/journey-copy.ts:348 | en | Guess what happens, listen without the text, then check. Harder, and the part that trains listening. | — | P3: competence claim (shown only with episode audio) | Guess what happens, listen without the text, then check. Harder. |
| | journey-copy.ts:538 | de | Rate, wie es ausgeht, hör ohne Text zu, prüfe dann nach. Schwerer — und genau der Teil, der Hörverstehen übt. | | | Rate, wie es ausgeht, hör ohne Text zu, prüfe dann nach. Schwerer. |
| | journey-copy.ts:728 | fr | Devinez ce qui arrive, écoutez sans le texte, puis vérifiez. Plus difficile — et c'est cette partie-là qui travaille l'écoute. | | | Devinez ce qui arrive, écoutez sans le texte, puis vérifiez. Plus difficile. |
| 30 | web-frontend/lib/studio-copy.ts:152-154 / :220-222 / :84-86 (and :177, 188 …) | en / de / fr | Conversation · 5 minutes · Your story and today's words, out loud. · Start speaking | — | P3: a voice page still reachable via the `studio` action (pages/atelier.tsx:1670-1672) | No wording change. Gate the `studio` action on the same server capability as voice reply (`canSpeak`), so the page is unreachable while no audio is deployed. |
| 31 | web-frontend/lib/settings-copy.ts:345-346 / :564-565 / :787-788 and the B2 hint (:343 / :562 / :785 range) | en / de / fr | C2 "Mastery · Close to a native speaker" / "Beherrschung · Nahe an einer Muttersprachlerin" / «Maîtrise · Aisance proche d'un locuteur natif»; B2 "Independent · Speaking with spontaneity" / «Indépendant · Échanger avec spontanéité» | SD | P3, P5 (CEFR descriptor names on a self-pick list) | Keep the bands; describe *what the app gives* at each: B2 «Textes et échanges longs» / "Longer texts and exchanges" / "Längere Texte und Gespräche"; C2 «Textes exigeants, nuances» / "Demanding texts, nuance" / "Anspruchsvolle Texte, Nuancen". Drop "native speaker". |
| 32 | app/services/learner_copy.py:1013-1017; app/services/item_bank.py:2189, 2267-2271; web-frontend/components/lexique/lexique-copy.ts:300 / :537 / :774 | en / de / fr | Say it aloud in French, then check the transcript. · Say it / Sprich es / Dis-le | — | P3 if the speak round is served without voice (it counts as PRODUCE evidence toward «tenue»: `srs/memory.py:126`) | No wording change. Do not serve the speak round when voice is off; if it is served, it must not count as evidence. Engineering follow-up, not copy. |
| 33 | app/data/season/s1/t6.json:28-31 (`can_do`) | en / de / fr | Listen to someone's side of a story; … / Die Version einer Geschichte von jemand anderem anhören; … / Écouter la version de quelqu'un ; … | task goal | P3 (mild) | Season text: owner item. Proposed: "Read someone's side of a story; …" / "Die Version einer Geschichte von jemand anderem lesen; …" / «Lire la version de quelqu'un ; …» |
| 34 | app/data/legal/legal_content.json:29, 57, 85 (and web-frontend/lib/legal-content.json) | en / de / fr | "…creates the story images and audio" | — | P3 (mild): describes audio the service does not deliver | Legal text: owner and legal item. Proposed: drop "and audio" until audio is deployed. |

### 3.5 CEFR labels on the app's own measure (P1)

| # | file:line | lang | current text | class | problem | proposed text |
|---|---|---|---|---|---|---|
| 35 | app/services/can_do.py:84-87 | en / de / fr | Level {band} / Niveau {band} / Niveau {band} (Carnet band page title) | SC | P1: A1.1 / A1.2 are not CEFR levels | Course {band} / Kurs {band} / Cours {band} |
| 36 | app/services/level_coverage.py:357 (`level_label`, e.g. «A1.1 · 60 %») | neutral | {band} · {percent} % | SC | P1 when rendered bare | The surface that renders it prefixes the course word (rows 3, 12) → «Cours A1.1 · 60 %». |
| 37 | web-frontend/components/lexique/lexique-copy.ts:361-362 / :598-599 / :835-836 | en / de / fr | CEFR coverage · words known per level / GER-Abdeckung · sichere Wörter pro Niveau / Couverture CECR · mots tenus par niveau | SC | P1 (mild): the app's word list presented as CEFR | Words per course · words known per band / Wörter pro Kurs · bekannte Wörter pro Stufe / Mots par cours · mots connus par niveau du cours |
| 38 | web-frontend/components/atelier-v2/band-check/band-check-copy.ts:121-122 / :169-170 / :73-74 (`intro_fine`) | en / de / fr | If you recognise at least {pct} %, the whole level counts as known: its words come back only for a light check. | SC | P1 (mild) | If you recognise at least {pct} %, this course's words count as known: they come back only for a light check. (de/fr analogous: «… les mots de ce cours comptent comme connus …» / "… gelten die Wörter dieses Kurses als bekannt …") |
| 39 | web-frontend/components/cahiers/cahier-copy.ts:391 / :650 / :129 | en / de / fr | {level} in progress / {level} in Arbeit / {level} en cours | SC | P4 (mild) | Course {level} in progress / Kurs {level} in Arbeit / Cours {level} en cours |
| 40 | app/data/grammar_review/units_B2.json:1307; units_C1.json:467 | en | "…DELF B2 productions…", "…the DALF essai argumenté" | n/a | P5 (low): names an exam, claims no equivalence | Keep. Optional: "B2-level essays" / "an argumentative essay". |

### 3.6 Already honest (keep)

These are reference wording for the changes above:
- The placement failure copy, «Nous préférons vous le dire plutôt qu'annoncer un niveau que personne n'a vérifié» (`placement-copy.ts:82-85` and equivalents).
- «Niveau estimé : {level}» and its confidence line, «Ce niveau guide vos premières séances…» (`placement-copy.ts:88-93`).
- Dossier: «déclaré à l'inscription · non vérifié», «estimé (bilan) · non vérifié», the coverage basis «Calculé sur votre travail dans l'application…», the "assumed known" vocabulary wording, «Vos compteurs… sont encore à zéro : ce niveau reste une estimation».
- Relevé: "Estimate: more than two years at this pace" / "Forecast after seven active days", and the declared and placed source lines.
- `journey_capabilities.py:25-26`: "it is not a level".
- The Terms disclaimer «C'est une aide à l'apprentissage, pas une certification».

## 4. Not changed here, and why

- **No code changed.** These files are owned by other agents in this wave (Dossier, Relevé, recap, band check, Forge, settings). The orchestrator applies approved rows one file at a time. Each row is a key-level replacement; none changes a key or a placeholder, except row 10 (adds `{source}`) and row 11 (a condition).
- **Owner items** (story or legal text): rows 23 (can-do titles, an LLM draft), 25 (épreuve line), 33 (season can-do), 34 (Terms).
- **Engineering follow-ups, not wording:** rows 28, 30 and 32 (gate voice surfaces and speak-round evidence on the deployment's audio capability), and the row 16/17 owner decision (does a test-out count as "held"?).
- **Unused strings** (`lib/atelier-v2-copy.ts:210/300/390`, `journey-copy.ts:311/316` `capability_shown`, `components/laune/laune-copy.ts:63/97/131`, used only by the mobile QA page; `app/services/analytics_service.py` vocabulary → CEFR heuristic; `app/data/syllabus/can_dos_C1.json`) can be deleted rather than reworded.
- **Not shown to learners:** API 409 error details (`level_checkpoint.py:238-251`, `progress.py:106`, English only) and code comments.
- **WP-134B:** after external calibration, rows 1–7 and 35–37 are the places a stronger claim could go back. Until then, «cours» is the honest noun.
