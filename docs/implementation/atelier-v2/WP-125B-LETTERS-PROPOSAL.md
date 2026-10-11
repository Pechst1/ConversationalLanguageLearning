# WP-125B — new fallback letters (proposal, 2026-10-04)

**Status: proposal, not applied. Owner approval needed: every line below is new story text.**

Sources: review §2.8 «The Courrier» ([EXPERIENCE-REVIEW-2026-10-04.md](EXPERIENCE-REVIEW-2026-10-04.md)) and package WP-125 «Scope B» ([WORK-PACKAGES-2026-10-04-experience.md](WORK-PACKAGES-2026-10-04-experience.md)).

**To apply after approval:** run `git apply docs/implementation/atelier-v2/WP-125B-LETTERS-PROPOSAL.patch`, then `pytest tests/test_wp125b_fallback_letters.py tests/test_wp84_letter_level.py tests/test_missions.py tests/test_story_correspondence.py tests/test_wp99_facteur_depeches.py`. With the patch applied, those suites give 199 passed. The patch touches:

- `app/services/missions.py`: the letters, the follow-ups, the story frames, the success objectives and their translations.
- `tests/test_wp125b_fallback_letters.py`: three tests added. Every band has a month of credible letters, every follow-up names the earlier exchange, and C1 gets C1 frames.
- `tests/test_wp84_letter_level.py`: the A1-safe check now covers only the letters an A1 learner can be sent, those written at A1 or A2.

---

## 0. Why, and what the code already does without this

The committed WP-125B code is the selection logic only. It gives each existing canned letter a level, and it sends a fallback letter only when all of the following hold:

- the letter is within reach of the learner's band. A closed letter reaches one band above its own, an open one two;
- the letter is at most one band above the learner;
- it is not a reprint within 28 days;
- it is not a request the learner completed in the last 7 days;
- it is not a premise that Season 1 contradicts.

When nothing passes, **no letter is sent that day**. Without this proposal, that is the right result, and it is a thin one:

| Band | Credible canned letters on Season 1 today | With this proposal |
|---|---|---|
| A1 | 7 | 7 (+ 7 follow-ups) |
| A2 | 7 | 10 (+ 7 follow-ups) |
| B1 | 5 | 11 |
| B2 | **0** | 9 |
| C1 | **0** | 7 |

The story frame for a story-born letter is only the A2 one today (open, so it reaches B2). A C1 learner therefore gets no story-born letter either, provider-off. In the life walk, the C1 strong learner received **1 letter in 30 days** (Romy's first letter), down from 21. That count was 21 before, mostly the A1 bread question and its reprints.

A canned affair (letter 1, then a follow-up) also stops after letter 1 today: a reprint of letter 1 is not a letter 2. Follow-ups are new text, so they are proposed here too.

**Rules every proposed text keeps:**

- Strangers say «vous», and the cast is never named or contradicted.
- No adjective or participle agrees with the learner. This is the bible's `toi_agreement` rule: «disponible» is epicene, and «ce qui m'a étonné» agrees with «ce».
- No new facts about the learner beyond the letter's own premise.
- A follow-up never guesses what the learner answered. It thanks them for the answer and moves one step on.
- Each text passes the WP-84 level guard (`letter_level_verdict`) at its own band.

The letters were also checked against Season 1:

- The protagonist came to Paris for a week with a return ticket.
- They rent a short-let studio with a cold radiator.
- They live by the canal Saint-Martin.
- The future of the quartier's commerce is one of the season's arcs.

---

## 1. New letters: 9

Each letter has its own `domain`, an English `success_signal`, translations of that signal in `AUTHORED_SUCCESS_SIGNAL_I18N`, and success objectives in `MISSION_SUCCESS_OBJECTIVES`.

| # | Level | Kind | Title | From | First line of the letter |
|---|---|---|---|---|---|
| 1 | B1 | closed, `once` | Votre train retour est supprimé | Service voyageurs | «Bonjour, en raison d'une grève, votre train retour de dimanche est supprimé.» |
| 2 | B1 | closed | Un sac aux objets trouvés | Objets trouvés (métro) | «Bonjour, un sac de sport a été déposé chez nous hier soir, avec dans la poche intérieure une carte à votre nom.» |
| 3 | B1 | open | Le conseil de quartier vous écrit | Conseil de quartier du canal | «Bonjour, le conseil de quartier prépare une réunion sur la vie autour du canal, et nous aimerions entendre aussi les personnes qui viennent d'arriver.» |
| 4 | B2 | closed, `once` | Rester ou partir samedi | Hélène, votre hôte pour le studio | «Bonjour, j'espère que le studio vous convient, malgré ce radiateur capricieux.» |
| 5 | B2 | closed | Travaux de ravalement | Le syndic | «Madame, Monsieur, des travaux de ravalement de la façade commenceront lundi et dureront trois semaines.» |
| 6 | B2 | open | Des quais sans voitures ? | La Gazette du canal | «Bonjour, notre prochain numéro porte sur une question qui divise le quartier : faut-il fermer les quais aux voitures tous les dimanches ?» |
| 7 | C1 | closed | Le transporteur conteste | Service réclamations | «Madame, Monsieur, le transporteur nous indique que votre colis a été remis en main propre mardi à 14 h 12, signature à l'appui.» |
| 8 | C1 | open | Une table ronde jeudi | Association «Vivre le canal» | «Bonjour, notre association organise jeudi une table ronde sur ce que deviennent les commerces de quartier quand les loyers flambent et que des investisseurs rachètent les murs.» |
| 9 | C1 | open | Consultation sur les berges | Mairie d'arrondissement | «Madame, Monsieur, dans le cadre de la consultation sur la végétalisation des berges du canal, la mairie d'arrondissement recueille l'avis des habitants, y compris de ceux qui ne résident ici que depuis peu.» |

### Full texts

**1 · Votre train retour est supprimé** (B1, `once`: the end of a stay is not reprinted)
- Opening: «Bonjour, en raison d'une grève, votre train retour de dimanche est supprimé. Nous pouvons vous proposer un départ samedi soir ou lundi matin, sans frais, ou bien le remboursement de votre billet. Merci de nous indiquer votre choix avant vendredi midi ; si aucune de ces solutions ne vous convient, expliquez-nous ce qui vous poserait problème.»
- Brief: «Votre train retour est supprimé. Choisissez une solution, ou expliquez ce qui ne vous convient pas.»
- Objective: «Le service sait quelle solution vous choisissez, ou ce qu'il vous faut.» (de: «Der Kundendienst weiß, welche Lösung Sie wählen oder was Sie stattdessen brauchen.»)
- Twist: «Le lundi matin, le train part à 6 h 04.»
- Quick replies: «Je préférerais partir...», «Le samedi soir ne me convient pas, parce que...», «Est-ce que je pourrais plutôt...»
- Season: the protagonist «booked a return ticket for a week later». Whether they leave is the season's question, and the letter only asks for logistics.

**2 · Un sac aux objets trouvés** (B1)
- Opening: «Bonjour, un sac de sport a été déposé chez nous hier soir, avec dans la poche intérieure une carte à votre nom. Avant de vous le rendre, nous devons vérifier qu'il vous appartient : pourriez-vous nous décrire le sac et ce qu'il contient, et nous dire quand vous pourriez passer le chercher ?»
- Brief: «On a retrouvé un sac avec votre nom. Décrivez-le et proposez un moment pour passer.»
- Objective: «Le service peut vérifier que le sac est à vous et sait quand vous passez.» (de: «Das Fundbüro kann prüfen, dass die Tasche Ihnen gehört, und weiß, wann Sie vorbeikommen.»)
- Twist: «Le bureau ferme à 17 h, et il est fermé le samedi.»
- Quick replies: «C'est un sac... avec...», «À l'intérieur, il y a...», «Je pourrais passer...»
- Season note: the letter avoids a notebook and a scarf, which are story objects (Odile's notebook, Margaux's scarf letter).

**3 · Le conseil de quartier vous écrit** (B1, open)
- Opening: «Bonjour, le conseil de quartier prépare une réunion sur la vie autour du canal, et nous aimerions entendre aussi les personnes qui viennent d'arriver. Qu'est-ce qui vous a plu dans le quartier, et qu'est-ce qui vous a manqué ou étonné ? Quelques lignes suffisent.»
- Brief: «Le conseil de quartier veut votre avis. Racontez ce qui vous plaît ici, et ce qui vous manque.»
- Objective: «Le conseil sait ce qui vous plaît et ce qui vous manque dans le quartier.» (de: «Der Quartiersrat weiß, was Ihnen im Viertel gefällt und was Ihnen fehlt.»)
- Twist: «La réunion a lieu jeudi soir, dans la cour d'une école.» This is deliberately not a café back room, which would point at Le Mistral.
- Quick replies: «Ce qui me plaît ici, c'est...», «Ce qui me manque, c'est...», «Ce qui m'a étonné, c'est...»

**4 · Rester ou partir samedi** (B2, `once`)
- Opening: «Bonjour, j'espère que le studio vous convient, malgré ce radiateur capricieux. Votre réservation se termine samedi. J'ai une demande pour la semaine suivante, mais si vous envisagez de rester plus longtemps, je préférerais vous donner la priorité. Pourriez-vous me dire d'ici jeudi ce que vous comptez faire, quitte à me donner une réponse provisoire ?»
- Brief: «Votre hôte doit savoir si vous restez. Expliquez vos projets, même s'ils ne sont pas encore décidés.»
- Objective: «Hélène sait si vous partez samedi ou si vous voulez rester, et de quoi cela dépend.» (de: «Hélène weiß, ob Sie am Samstag abreisen oder bleiben möchten und wovon das abhängt.»)
- Twist: «Pour une semaine de plus, elle peut faire un prix, mais pas changer le radiateur.»
- Quick replies: «Merci de me donner la priorité...», «Tout dépend de...», «Pourriez-vous me garder le studio jusqu'à...»
- Season: this is the protagonist's own short-let studio with the cold radiator (bible, protagonist). **Owner call:** the letter touches the season's central «stay or go?». It asks only for a provisional answer and decides nothing, but you may prefer it to stay out of Season 1. If so, add `season_safe: False`.

**5 · Travaux de ravalement** (B2)
- Opening: «Madame, Monsieur, des travaux de ravalement de la façade commenceront lundi et dureront trois semaines. Un échafaudage sera installé devant les fenêtres côté rue, et les ouvriers devront accéder ponctuellement aux balcons. Nous vous remercions de nous indiquer vos disponibilités pour une visite, ainsi que toute contrainte particulière dont nous devrions tenir compte.»
- Brief: «Des travaux commencent dans l'immeuble. Donnez vos disponibilités et signalez ce qui vous gêne.»
- Objective: «Le syndic connaît vos disponibilités et ce qui vous gêne.» (de: «Die Hausverwaltung kennt Ihre Verfügbarkeit für einen Besuch und weiß, was Sie einschränkt.»)
- Twist: «Les travaux commencent à 7 h 30, même le samedi.»
- Quick replies: «Madame, Monsieur, je serai disponible...», «Je tiens toutefois à vous signaler que...», «Serait-il possible de...»
- Season note: the sender is a «syndic», not M. Marchand's gérance, which manages the Mistral building.

**6 · Des quais sans voitures ?** (B2, open)
- Opening: «Bonjour, notre prochain numéro porte sur une question qui divise le quartier : faut-il fermer les quais aux voitures tous les dimanches ? Les commerçants craignent de perdre des clients, les familles réclament de l'espace. Accepteriez-vous de nous écrire quelques lignes pour notre courrier des lecteurs, avec votre point de vue et ce qui le justifie ?»
- Brief: «Un journal de quartier vous demande votre avis sur les quais sans voitures. Donnez votre position et vos arguments.»
- Objective: «Le journal connaît votre position et au moins une raison.» (de: «Die Redaktion kennt Ihre Position und mindestens einen Grund dafür.»)
- Twist: «Le numéro sort samedi ; il leur faut le texte jeudi.»
- Quick replies: «À mon avis...», «Je comprends l'inquiétude des commerçants, mais...», «Ce qui me paraît décisif, c'est...»
- Season note: the letter avoids petitions, which are Romy's and Gus's territory.

**7 · Le transporteur conteste** (C1)
- Opening: «Madame, Monsieur, le transporteur nous indique que votre colis a été remis en main propre mardi à 14 h 12, signature à l'appui. Nous ne pouvons donc pas, en l'état, procéder à un remboursement. Si vous contestez cette livraison, il vous appartient de nous exposer précisément les faits ; nous ouvrirons alors une enquête auprès du transporteur, dont les conclusions nous parviennent généralement sous quinze jours.»
- Brief: «Le transporteur affirme vous avoir remis le colis. Contestez-le avec précision et dites ce que vous attendez.»
- Objective: «Le service dispose d'un récit précis des faits et sait ce que vous demandez.» (de: «Der Kundendienst hat eine genaue Darstellung des Geschehens und weiß, was Sie verlangen.»)
- Twist: «La signature sur le bon de livraison ne ressemble pas du tout à la vôtre.»
- Quick replies: «Je conteste formellement cette livraison :», «Ce jour-là, à cette heure-là...», «Je vous saurais gré de...»

**8 · Une table ronde jeudi** (C1, open)
- Opening: «Bonjour, notre association organise jeudi une table ronde sur ce que deviennent les commerces de quartier quand les loyers flambent et que des investisseurs rachètent les murs. Le regard de quelqu'un qui découvre le quartier nous serait précieux : accepteriez-vous d'intervenir cinq minutes, ou, à défaut, de nous envoyer quelques lignes que nous lirions en ouverture ?»
- Brief: «Une association vous invite à parler des commerces de quartier. Dites si vous intervenez, et donnez votre regard.»
- Objective: «L'association sait si vous intervenez et connaît votre regard en quelques lignes.» (de: «Der Verein weiß, ob Sie sprechen, und kennt Ihre Sicht in ein paar Zeilen.»)
- Twist: «Une librairie du quai a fermé la semaine dernière.»
- Quick replies: «Je vous remercie de votre invitation ;», «Ce qui frappe, quand on arrive, c'est...», «Il me semble que...»
- **Owner call:** the theme echoes arc C, the future of Le Mistral, and Solvel Immobilier. It names no one and decides nothing, but it may read as the story when it is not. If you prefer it off the season, add `season_safe: False`.

**9 · Consultation sur les berges** (C1, open)
- Opening: «Madame, Monsieur, dans le cadre de la consultation sur la végétalisation des berges du canal, la mairie d'arrondissement recueille l'avis des habitants, y compris de ceux qui ne résident ici que depuis peu. Le projet prévoit de supprimer une partie des places de stationnement au profit de plantations et de bancs. Quels effets en attendez-vous sur la vie du quartier, et quelles réserves éventuelles souhaiteriez-vous formuler ?»
- Brief: «La mairie consulte les habitants sur les berges du canal. Donnez un avis nuancé, avec vos réserves.»
- Objective: «La mairie connaît votre avis sur les effets du projet et vos éventuelles réserves.» (de: «Das Bezirksamt kennt Ihre Einschätzung der Folgen des Projekts und Ihre Vorbehalte.»)
- Twist: «La consultation ferme dimanche à minuit.»
- Quick replies: «Le projet me paraît...», «J'émettrais toutefois une réserve :», «Encore faudrait-il que...»

---

## 2. Follow-ups: 7, letter 2 of an affair

Each follow-up belongs to an existing season-safe A-level letter. It is written at that letter's level. It thanks the learner for their answer without guessing its content, and it asks the next concrete thing. The Courrier also prints the existing chain note («Lettre 2 sur 2 · suite de « … »»). An affair on a canned letter is capped at 1 + the number of follow-ups. With one each, an affair is two letters, never the four-day reprint the walk recorded («Pas la bonne taille», days 9–12).

| Letter 1 | Follow-up opening | Follow-up brief |
|---|---|---|
| Le radiateur est froid (A2) | «Bonjour, merci pour votre message sur le radiateur. Le technicien peut venir mardi à dix heures. Vous êtes là, ou je laisse la clé à la gardienne ?» | «Le technicien peut venir mardi. Dites si vous êtes là, ou qui peut ouvrir.» |
| Un mot de la voisine (A2) | «Bonsoir, merci pour votre petit mot d'hier. C'est plus calme maintenant. Samedi, je fais un gâteau : vous voulez passer prendre un café ?» | «Madame Vidal vous remercie et vous invite. Répondez à son invitation.» |
| Le colis perdu (A2) | «Bonjour, merci pour votre réponse. Nous avons maintenant votre adresse. Le paquet arrive demain matin. Comment est-ce qu'on entre dans votre immeuble ?» | «Le paquet arrive demain. Dites comment on entre chez vous.» |
| Pas de train (A1) | «Bonjour, j'ai bien reçu votre réponse. Il y a un train demain matin, à huit heures. Vous voulez une place près de la fenêtre ?» | «Il y a un train demain matin. Dites quelle place vous voulez.» |
| Trois jours sans internet (A2) | «Bonjour, merci pour votre message. Un technicien vient chez vous jeudi entre 14 h et 18 h. Pour les trois jours sans internet, nous vous offrons un mois. C'est bon pour vous ?» | «Un technicien vient jeudi. Dites si l'heure va, et si vous acceptez le mois offert.» |
| Pas la bonne taille (A1) | «Bonjour, merci pour votre réponse. Nous avons la bonne taille. Vous préférez l'échange par la poste ou à la boutique ?» | «La boutique a votre taille. Choisissez : par la poste ou à la boutique.» |
| Un papier pour la mairie (A2) | «Bonjour, merci pour votre message. Avec votre adresse, le dossier est presque complet. Il faut encore un papier avec votre adresse, par exemple une facture. Vous pouvez l'envoyer par e-mail ?» | «Il manque un dernier papier. Dites quel papier vous pouvez envoyer, et quand.» |

The first drafts of two follow-ups failed the A1/A2 level guard. «Le livreur passe demain entre 9 h et 13 h. Il y a un code pour la porte ?» was flagged for «livreur», «code» and «h». «Il y a un train demain à 8 h 12, voie 4» was flagged for «h». Both were rewritten as shown above.

---

## 3. Story frames: 3 levels × «vous»/«tu» = 6 lines

These are printed when a cast member's story-born letter cannot be written by the model. The richest frame at or below the learner's band is used. All frames are open: the learner says what they make of a scene they played. `{name}` is the writer.

| Level | «vous» | «tu» |
|---|---|---|
| A2 (today, unchanged) | «Bonjour, c'est {name}. Je pense encore à notre dernière rencontre. Et vous, qu'en pensez-vous ?» | «Salut, c'est {name}. Je pense encore à notre dernière rencontre. Et toi, tu en penses quoi ?» |
| **B1** | «Bonjour, c'est {name}. Je repense à ce qui s'est passé l'autre jour, et j'aimerais savoir ce que vous en avez pensé. Qu'est-ce que vous comptez faire, maintenant ?» | «Salut, c'est {name}. Je repense à ce qui s'est passé l'autre jour. Toi, tu en as pensé quoi ? Et tu comptes faire quoi, maintenant ?» |
| **B2** | «Bonjour, c'est {name}. Je n'arrête pas de repenser à notre dernière conversation ; j'ai l'impression qu'on ne s'est pas tout dit. Avec un peu de recul, comment voyez-vous les choses ?» | «Salut, c'est {name}. Je n'arrête pas de repenser à la dernière fois ; j'ai l'impression qu'on ne s'est pas tout dit. Avec le recul, tu vois ça comment ?» |
| **C1** | «Bonjour, c'est {name}. Certains moments ne prennent leur sens qu'après coup, et notre dernière rencontre en fait partie. Qu'en retenez-vous, avec le recul, et qu'avez-vous envie d'en faire ?» | «Salut, c'est {name}. Il y a des moments qui ne prennent leur sens qu'après coup, et la dernière fois en fait partie. Toi, qu'est-ce que tu en retiens, et qu'est-ce que tu as envie d'en faire ?» |

The frames never agree an adjective with the writer either, so they fit any cast member.

---

## 4. Count

**22 new texts:**
- 9 letters: 3 at B1, 3 at B2 and 3 at C1;
- 7 follow-ups, at A1/A2;
- 6 story-frame lines: B1, B2 and C1, each in «vous» and «tu».

Each new letter also adds:
- its brief, twist, three quick replies and three ambient cues;
- an objective in French and German, with the English source;
- two internal English success objectives.

## 5. Validation (patch applied, then reverted)

- **Level guard.** `letter_level_verdict` at each text's own band accepts every new letter, follow-up and frame line. The only rejection in the whole catalogue is the existing «Au parc ce midi», whose place and contact names are not passed as names in that ad-hoc check.
- **Tests.** The WP-125B, WP-84, missions, correspondence, WP-99, review, WP-125A and letter-day suites give 199 passed.
- **Life walk with the patch applied.** I applied the patch together with the walk-recording and walk-check wiring patch from the package report. The three lives below passed, including `check_letter_repeats` and `check_letter_levels`.

## 6. Life walk, provider-off (30 days)

Each cell reads Wave 1 *after* → WP-125B code → WP-125B code with this proposal applied.

| Life | New letters | Repeats of a completed request within 7 days | Letters beyond reach | Letter minutes a day |
|---|---|---|---|---|
| a1-de-fresh average | 19 → 14 → 15 | 8 → 0 → 0 | 0 → 0 → 0 | 2.8 → 2.0 → 2.2 |
| b1-en strong | 18 → 13 → 15 | 7 → 0 → 0 | 7 → 0 → 0 | 2.1 → 1.5 → 1.8 |
| c1-de strong | 21 → **1** → 13 | 12 → 0 → 0 | 20 → 0 → 0 | 1.6 → 0.1 → 1.1 |

With the proposal applied, the walk shows the new material at work:

- **C1 strong:** the C1 story frames, then «Le conseil de quartier vous écrit», «Une table ronde jeudi», «Des quais sans voitures ?» and «Le transporteur conteste».
- **B1 strong:** «Un sac aux objets trouvés» and «Travaux de ravalement».
- **A1 average:** two affairs that each go on to a named follow-up («Pas de train» on day 10, «Un papier pour la mairie» on day 17).

«Un mot de la voisine» comes back on day 30 for the A1 learner, exactly 28 days after day 2. That is the reprint window, not a repeat within 7 days.
