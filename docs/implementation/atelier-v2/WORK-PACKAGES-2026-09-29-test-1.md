# Work packages — 2026-09-29: the owner's first test, and a day with a theme

Two things came out of the owner's first hands-on test of WP-88..99 (day 2 of an
English-speaking A1 learner, test copy of the database):

1. **WP-103 · Retour d'essai** — the concrete faults the owner saw, each with its
   root cause in code and a fix that can be checked.
2. **WP-104..106 · La rubrique du jour** — the deeper finding: *the session has no
   theme.* The scene, the drills, the listening and La Forge each pull from their
   own queue, so a day at Le Mistral asking Romy to sit down also asks for «Une
   petite table blanche est dans la cuisine», «Vous cherchez une micro à la
   brocante» and «Lila cherche un grand poster». Words are covered by frequency
   rank and by the review queue, never as a coherent ambition.

A process note first, because it explains how these faults got through.
WP-90..99 were built from specs and proved by ~4,000 tests. Several agent reports
said "not verified in a browser" because the agents' preview pane could not
render pages, and they went on regardless. Ten minutes of real use found more than the tests did. From now on a
package is **done only when someone has used it**. That means an owner walk, or the
E-3 walk harness with a human (or reviewer agent) judging the screenshots
against three questions:
*does the learner know what to do, whether they were right, and how to go on?*

---

## WP-103 · Retour d'essai (the owner's test, 2026-09-29)

| # | What the owner saw | Root cause | Fix | Checked by |
|---|---|---|---|---|
| T1 | «Everywhere the horrible English accent» | Speech uses `tts-1-hd` with OpenAI's stock voices (`FEUILLETON_AUDIO_TTS_MODEL`, `cast_voices.py`); those voices read French with an anglophone accent | Move to a steerable speech model (e.g. `gpt-4o-mini-tts`) with per-character instructions: «locuteur natif, français de France, accent parisien neutre», the persona's age and warmth, and a pace per band (A1 posé, A2 naturel-lent, B1+ naturel). The cache key already includes model and voice, so old clips simply stop being served. Fallback to evaluate if it still sounds foreign: a native French voice provider (the owner's ElevenLabs plan answered 402) | **Owner listening sheet**: six characters × two lines × A1/B1 pace, approved by ear. No test can replace this |
| T2 | Radio («Écouter d'abord»): too fast, text can't be shown, the task is arbitrary | The listen stage hides text by design (predict → listen → verify); the predict question («Rester ou partir ?») comes from the scene's premise, not from what is heard | Pace from T1; a **«Afficher le texte»** toggle per line and for the whole page at every stage (hidden is the default, never a wall); the listening task becomes one concrete comprehension question shown *before* listening and answered after, drawn from a line the learner will actually hear | Owner walk; a node test that the text toggle exists in every stage |
| T3 | «Build the sentence. Some chips are not needed.» — no idea *which* sentence | `grammar_items.py:60`: the grammar Rappel's word bank carries no meaning and no source; the step header shows the *day's* objective («Ask Romy…») above an unrelated drill | Every drill states its goal: a word bank shows the meaning to build («Build: "A small white table is in the kitchen."») or quotes the scene line it comes from; the header of a drill names the drill, not the day's reply objective | A planner/contract check: no recall step without a goal line; a node test on the header |
| T4 | «Ask Romy if she wants to sit with you» — but Marin answers, and it is Marin's face | The engine lets the objective name a third person while `character_id` (the person you talk to) is someone else | Engine rule: the person the objective asks you to talk to *is* the addressed character. A draft whose objective addresses another cast member is refused with a precise hint (retry, then the objective is rewritten to the addressed character) | E-7-style fixture with this exact scene; unit test on the validator |
| T5 | Marin answers an A1 learner in 43 words | The voice lane allows A1 replies «up to 35 words» (`story_lanes.py:180-206`), and does not enforce even that; WP-89's caps (A1 12) cover authored scenes only | Engine replies at A1 ≤ 15 words and one or two short sentences, A2 ≤ 25, B1 keeps 85; validated with one retry, then trimmed at a sentence boundary; the lexical-coverage check from WP-89 applied to engine replies | Fixture with the owner's turn; unit tests per band |
| T6 | «No correction of errors» («ton place» went unremarked) | WP-89 shows a slip as a dotted underline that must be *tapped* to reveal the correction — undiscoverable | The corrected form is printed under the learner's bubble in small green Garamond («ta place»), always visible; tapping opens the one-line explanation. The closing verdict lists the turn's corrections | Node test; owner walk |
| T7 | «Not clear how one gets to the next task» in the conversation | Mid-conversation the field reopens silently; the exchange triangles are too subtle | Under the latest line: «À vous — répondez à Marin · échange 2 sur 3» in the learner's chrome language; on the last exchange «Dernier échange»; after the close the primary «Continuer» is the only action | Node test; owner walk |
| T8 | La Forge «Correct / À corriger»: sorting a sentence as wrong leads nowhere | The classify item ends at the sort | After «À corriger», the learner corrects it: a short field (or tiles at A1) scored like a transform item; «Passer» shows the corrected sentence. Either way the right form is seen | Forge node + backend tests |
| T9 | La Forge free production: «Right / Well done!», then 10 s later «3 corrections» | The instant local check (`forge_grading.production_local_check`) is shown as a verdict before the model grades | Locally, only an exact or normalised match to an accepted answer may say «Right». Otherwise the character's face shows «Je relis…» until the model's verdict, and **a verdict is never reversed** | Backend test: no local «right» without an accepted-answer match; frontend test: no verdict flip |
| T10 | The correction is wrong and reads badly: «poster» is French; the explanation repeats itself three times | The corrector treats «poster» as English; the displayed note concatenates the rule's note, the model's note and a second-check line | Accepted answers include «Lila cherche un grand poster» (and «une grande affiche»); the corrector's prompt may not call a French loanword English; one explanation per issue, deduplicated, at most two sentences, in the learner's language | E-7 fixture («Lila cherche un poster grand»): expected single correction «un grand poster», explanation about adjective position only |
| T11 | «Romy texts you from the newsroom and wants a quick answer. Say in French: "Lila is looking for a big poster."» — arbitrary | Forge templates wrap every item in a pseudo-scene that has nothing to do with the learner's day | Interim: drop frames that do not come from the learner's story, and use a plain «Say in French: …». The real fix is WP-104: the frame comes from *today's* scene | Template review: no frame without a story source |

**Model and effort:** backend (T4, T5, T9 logic, T10) Opus 5.5 · high; frontend (T2, T3, T6, T7, T8 UI) Sonnet 5.5 · high; voices (T1) Sonnet 5.5 · medium plus the owner's ear.

**Done when:** the owner replays a fresh day 2 with the same learner and every row above is closed on screen, the T1 listening sheet is approved, and the new fixtures pass.

---

## WP-104..106 · La rubrique du jour — a day with a theme, and words with an ambition

### Why a day needs a theme

Today a day is a playlist: the scene comes from the story engine, the new words
from a frequency rank (WP-93's «mots à placer»), the grammar unit from the
memory model, the drills from the review queue, the Forge items from templates.
Each part is correct on its own, but together they make no sense. The research is clear
about what does make sense:

- **Themes, not categories.** Teaching words from one semantic category together
  (colours, fruit, furniture) makes them interfere; words that co-occur in one
  *situation* (a café: s'asseoir, une table, un crème, l'addition, à emporter)
  support each other (Tinkham 1993, 1997; Waring 1997; Nation). So the day's
  theme is a **situation**, never a word category.
- **Situations have scripts.** A situation comes with roles, props, moves and a
  sequence (Schank & Abelson). The script *is* the natural lexical ambition:
  its things (nouns), its moves (verbs), its qualities (adjectives), and its
  formulas («C'est combien ?», «Je voudrais…»).
- **Need makes words stick.** A word the learner *needs* for the story's problem,
  has to look for and has to choose among alternatives is retained far better
  than a drilled one (involvement load: Laufer & Hulstijn 2001).
- **Four strands, one lesson.** A good lesson balances meaning-focused input,
  meaning-focused output, language-focused learning and fluency (Nation 2007).
  The theme turns those four strands into one lesson.
- **Chunks before rules.** «Je voudrais un café» is owned whole long before the
  conditional is explained (Lewis). The rule of the day should explain chunks
  the learner already uses.
- **Spacing across themes.** A word learned in the café comes back at the
  brocante and in a letter, not only in the same day's drills. Meeting it in a
  new situation is what makes it transfer.

### The idea: every edition has a «rubrique»

L'Atelier is a *quotidien*. Every edition gets one **rubrique**: a place, a
situation and a lexical ambition. A week-long **dossier** (the story's chapter,
WP-58's four beats) groups rubriques under one larger theme. For example, the
dossier «Le Mistral est à vendre» could run over four days:

- «Les murs», at the notary: papers, signing, price;
- «La visite», in the café: rooms, big/small, old/new;
- «Le prix», on the phone: numbers, «trop cher»;
- «La décision», with everyone at the table: agreeing, disagreeing.

The **story picks the dossier through its arcs**. The **curriculum tilts the
choice** towards situations whose words and can-dos are still uncovered. That is
a pull, not a timetable: the learner never sees a syllabus, they see Margaux
worrying about her walls.

### WP-104 · La rubrique du jour — the theme spine and the day built around it

**Model:** Opus 5.5 · xhigh for the design of the field data and the selection;
Opus 5.5 · high to build.

1. **Situation fields (data).** For each can-do in `fr_core_can_dos_v2.json`
   (58, A1.1–B1.2; they already name their grammar units and a few words),
   add a **field** of 20–40 lemmas plus 6–10 chunks, organised by script role
   (people · things · moves · qualities · formulas) and tied to the band's lemma
   list and French-5000 rank. It is drafted offline (the writers'-room idea) and
   a sample is owner-reviewed. Each recurring place (12 plates) hosts several
   situations: Le Mistral hosts ordering, paying and making a date; the
   apartment hosts housing and inviting; the brocante hosts buying and
   describing; the station hosts travelling.
2. **Choosing today's rubrique.** Before generation, the planner builds a
   shortlist of 3 situations. Each is scored on need (uncovered lemmas in its
   field, due words that fit it, an unstamped can-do, a due grammar unit among
   its units) and on variety (not the same place two days running, except in a
   «bottle» chapter). The director picks the one that fits the story's arc.
   This is the same pattern as WP-95's can-do menu, moved earlier and made
   binding.
3. **The words of the day.** 4–6 new lemmas from the field (by centrality to
   the script, then rank), 4–6 review words from *earlier* fields that fit this
   situation (cross-theme recycling), and one formula. This replaces WP-93's
   rank-only «mots à placer».
4. **The scene carries them.** The director's plan (like WP-92's grammar plan)
   requires each new word at least twice across the page and the formula at
   least once, in natural lines. The validator counts lemmas with the coverage
   guard's lemmatiser: one retry with a hint, then accept and record it. The
   day's rule is chosen among the situation's units when one is due, so the rule
   explains something the scene just used.
5. **The reply needs them.** The objective is built so that 2 of the words and
   the formula are *needed*. The help chips offer the formula, not translations.
6. **Every drill is cut from today.** Recall items are built from the page's own
   lines: cloze of a line just read, «qui a dit ça ?», dictation of a line, a
   word bank rebuilding a line with its meaning shown. La Forge's rule items are
   filled in with today's nouns and people (the template bank gets slots for
   the field's words). No «Lila cherche un poster» out of nowhere.
7. **The day is titled.** Home, the day card and the recap name the rubrique:
   «Rubrique Brocante — marchander une lampe». The Sunday edition (WP-100)
   becomes the dossier's *sommaire*.
8. **Done when:**
   - in a 28-day fake-provider harness, at least 90 % of a day's drill items use
     a word from the day's field or today's page;
   - each new word appears at least twice on the page on at least 80 % of days;
   - every A1.1 field lemma is met in at least 2 different situations by day 90
     on Régulier;
   - an owner walk of 3 days says «the day is about something».

### WP-105 · L'Imagier de Paris — the ambition you can see

**Model:** Sonnet 5.5 · high to build; the art direction is the owner's call.

The coverage of words should be visible without a percentage (the owner's
rule: the mark is the only gauge). The idea is **a picture dictionary of the
story's Paris** that fills in as the learner lives there.

1. **One imagier page per place:** the location plate redrawn once as a busy
   imagier in the approved screen-print style (in the spirit of Richard Scarry's
   busy towns), 30–60 objects and actions with **authored hotspots**. It is a
   one-time art job for about 12 places, drawn with the existing pipeline.
2. **Words appear as they are lived:**
   - unmet objects are quiet silhouettes;
   - a word met in a scene gets its label in Garamond;
   - a word the learner holds gets ink.
   - Tapping an object says the word, shows the scene line where the learner met
     it, and who said it.
   - Places open with the story: the station appears when Marin's father arrives.
3. **«L'accroche» — the first beat of a day.** Before the page, 60–90 s on
   today's place: the day's new words are *discovered* on the imagier. The
   learner taps the lamp, hears «une lampe», sees it written: picture and sound
   together, no translation drill.
4. **The recap inks it.** The recap shows today's corner of the imagier with the
   new labels appearing. The Cahier's Carnet (can-dos) and the imagier (words)
   become two views of one map of the learner's Paris.
5. **Done when:** the 12 imagier pages exist with hotspots for at least 80 % of their
   fields' concrete lemmas, a harness learner's imagier fills in over 30 days,
   and an owner walk rates L'accroche as quicker and clearer than today's warm-up
   drills.

### WP-106 · La trace — a small real piece of French every day

**Model:** Opus 5.5 · high.

A high-involvement output task at the end of the longer rhythms (Régulier and
up), 60–120 s. It produces **something the situation would really produce**, in
the learner's own words, and it is kept in the Cahier:

- the shopping list for tomorrow's scene;
- a note stuck on Margaux's door;
- the small ad to sell the lamp at the brocante;
- a postcard to Romy;
- the text message to Marin that says you'll be late.

It is graded lightly (does it do the job, are the day's words used right) with
one correction at most. The character it is addressed to answers it in the next
day's scene (a callback, WP-62). That is the *need* that makes the words stick.

**Done when:** the trace is planned on at least 80 % of Régulier+ days in the
harness, its words come from the day's field, and the next scene quotes it.

### Order

1. **WP-103** now: the owner is testing, and nothing else should be built on top of these faults.
2. **E-3** (the walk harness): nothing after this ships unseen.
3. **WP-104**, then **WP-105**, then **WP-106**.
4. Then **WP-100** (the Sunday edition, now the dossier's sommaire) and **WP-101**.

### Owner decisions

| # | Decision | Recommendation |
|---|---|---|
| R-1 | The day is titled by its rubrique and the week by its dossier | Yes: the newspaper metaphor finally carries the pedagogy |
| R-2 | Field data drafted by a model offline, sample reviewed by the owner | Yes: 58 fields × ~30 lemmas is too much to hand-write, too important not to check |
| R-3 | L'Imagier art: one busy page per place, drawn with the existing pipeline | Yes, at about US$0.25 per page and ~12 pages, plus hotspot authoring |
| R-4 | The Forge's pseudo-narrative frames are dropped until WP-104 gives real ones | Yes |
| R-5 | Voice: a steerable OpenAI speech model first; a native-French provider only if the listening sheet fails | Yes |
