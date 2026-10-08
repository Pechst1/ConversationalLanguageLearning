# Tentpole 7 · «Le dernier soir»

*Days 51–52 · Thursday 31 December and Friday 1 January.*

The Réveillon at Le Mistral, which may be the café's last. The group tries the plan your choices made possible:
- the **lease**: Margaux must accept a new lease from Marchand, the man who called her negligent;
- the **co-op**: Gus must join, or the vote falls thirteen short;
- the **last service**: Gus has bought a chain to lock himself to the zinc.

At midnight, on the pavement, Lila. At eight the next morning, Margaux says the sentence she has never said, and you decide what happens to the flat.

**How to read this script.** The conventions are the same as in the earlier tentpoles: **A2** is the default line and **B1** is given only where it differs; *(silence)* marks a panel without dialogue; character lines are captions; **your line** is a balloon in its panel; **Note** lines are for the owner only.

---

## State in

- **`s1.plan`** (from T6): `lease` · `coop` · `last_service`.
- **From gap 6.**
  - Christmas at Le Mistral: Marchand's two croissants, and Lila's present.
  - The plan has been prepared but not attempted.
  - Lila's crate has left for Berlin by freight. She has a suitcase and a date: 8 January, 9:55.
- **Flags read:** `s1.lila_path`, `lila.heard_the_true_thing`, `s1.gus_photo`, `gus.costume_cracked`, `s1.promised_to`, `s1.went_with_lila_to_marin`, `s1.evidence_shared`, `romy.footage`, `s1.estate_liable`.

**Note (intent).** This is the season's warmest episode, and its most dangerous. It gives room for:
- **a confession:** Gus's, in the co-op variant;
- **a reconciliation:** Margaux and Marchand, or Gus and Marin;
- **a kiss or a pact:** Lila, at midnight.

Then Margaux turns the whole season with one word, «fatiguée». She has been the season's quiet centre, and now she asks for nothing. That is what makes the choice about the flat a real choice. It is no longer about being «for» or «against» the café.

---

## Day A · 31 December

**P1.** *Visual:* Le Mistral dressed for the Réveillon: one long table, paper stars, and Gus's candelabra. By the menu board, Romy and Marin argue with chalk in hand. Gus, in a dinner jacket, lays out place cards. Lila, on a chair, hangs the last star.
- CAPTION · A2 «31 décembre. Le Mistral fait son réveillon. Peut-être le dernier.» · B1 «Le 31 décembre. Le Mistral fête le réveillon, et tout le monde fait semblant que ce n'est pas le dernier.»
- ROMY · A2 «Chez nous, le souper, c'est le soir !»
- MARIN · A2 «Et le dîner, alors ?»
- ROMY · «Le midi !»
- MARIN · «Et le déjeuner ?»
- ROMY · «Le matin, voyons donc !»
- GUS · A2 «Je propose qu'on mange. Simplement.»

**P2.** *(silence)* *Visual:* The end of the zinc. Margaux puts a café crème in front of the empty stool, Odile's stool, then turns back to her glasses. Lila, on her chair with a star in her hand, sees it. So do you.

### P3 and the turn: variant by `s1.plan`

---

#### Variant: the lease (`s1.plan = lease`)

**P3.** *Visual:* The door. M. Marchand in his best coat, with Camille carrying his overnight bag, since the stairs are too much for him. The room goes quiet. Margaux does not look up.
- MARCHAND · A2 «Bonsoir. On m'a invité. Enfin… Gus m'a invité. En septembre, il ne m'aimait pas.» · B1 «Bonsoir. On m'a invité. Gus, plus exactement. Ce qui, vu d'où l'on part, est déjà un miracle.»
- GUS · A2 «Je ne vous aime toujours pas. Mais c'est le réveillon.»

**P4.** *Visual:* Marchand at the zinc, across from Margaux, with a folded document between them: a nine-year lease, unsigned. Camille and you stand a step behind them.
- MARCHAND · A2 «Neuf ans. Le même loyer. Je vends mes étages à Solvel. Pas les murs du café. Avec votre loyer, je paie ma résidence. Ce n'est pas un cadeau. C'est un calcul.» · B1 «Un bail de neuf ans, au même loyer. Je vends mes étages à Solvel, mais je garde les murs du café. Votre loyer paiera ma résidence. Ce n'est pas de la charité, c'est un calcul.»
- MARGAUX *(to the glass)* · A2 «Non.»

**The turn.** Margaux has refused. Camille looks at you: A2 «Parlez-lui. Nous, elle ne nous écoute pas.»

**Solve · Convaincre (Margaux).** Persuade Margaux to accept the lease. She has three objections. Any sincere reason that touches her lands.

| Margaux's objection | A2 | B1 |
|---|---|---|
| 1 | «Il m'a traitée de négligente pendant trois ans.» | «Trois ans qu'il me traite de négligente, et je devrais signer ?» |
| 2 | «Je n'ai besoin de personne.» | «Je n'ai jamais eu besoin de personne. Ce n'est pas ce soir que je vais commencer.» |
| 3 | «Neuf ans de plus. Seule. Tu te rends compte ?» | «Neuf ans de plus, seule derrière ce zinc. Tu te rends compte de ce que tu me demandes ?» |

- **Landing arguments** (examples): «Odile voulait ça : "oui, si Margaux reste".» · «Il l'aimait aussi.» · «Accepter, ce n'est pas demander.» · «Tu n'es pas seule. On est là.»
- **Clumsy but sincere** (for example *«Tu… protèges Odile. Trois ans. Maintenant… quelqu'un protège toi ? Laisse-le.»*) → *(silence panel: Margaux puts the glass down, and her hands are empty again, as in T4)* · MARGAUX · A2 «"Quelqu'un protège toi."» *(beat)* «C'est très mal dit.» *(she takes Marchand's pen)*
- **When it lands:** Margaux signs. Marchand signs. Neither looks at the other, then they do. → `s1.margaux_persuaded = true`
- **If it doesn't land, or [ Laisser Margaux décider ]:** MARGAUX · A2 «Je réfléchis. Demain.» → `false`. The lease stays unsigned. T7 Day B decides.

---

#### Variant: the co-op (`s1.plan = coop`)

**P3.** *Visual:* Marin stands on a chair with a tally sheet, and the room crowds around him. In the booth's corner seat, Gus sits with his arms crossed, in a dinner jacket.
- MARIN · A2 «Cent quatre-vingt-sept ! Il manque treize personnes. Si on passe minuit à deux cents… c'est un signe.» · B1 «Cent quatre-vingt-sept sociétaires ! Il en manque treize. Si on franchit minuit à deux cents, ce sera un signe.»
- ROMY · A2 «Cent quatre-vingt-sept… C'est pas le chiffre de la pétition de Gus ?»

> **Note.** The missing members are exactly Gus's petition signatories (T3: 187). If Gus signs, his people follow. Marin knows it, and cannot ask.

**P4.** *(silence)* *Visual:* Gus alone in the corner seat. His hand is flat on the old leather of the booth, the fabric Marin's plan will replace.

**The turn.** Marin looks at you from his chair, then at Gus. He cannot ask, again.

**Solve · Convaincre (Gus).** Persuade Gus to join the co-op. He has three objections.

| Gus's objection | A2 | B1 |
|---|---|---|
| 1 | «Ils vont bouger la banquette.» | «Ils vont déplacer la banquette. Au fond. Comme un meuble.» |
| 2 | «Ce ne sera plus le Mistral. Ce sera une cantine.» | «Ce ne sera plus le Mistral. Ce sera une cantine avec des sociétaires.» |
| 3 | «Il y a des choses que tu ne sais pas.» | «Il y a des choses que tu ne sais pas, sur cette banquette.» |

- **After objection 3, Gus's confession.** It always comes here, whatever the learner said:
  - GUS · A2 «Ma mère servait les cafés ici. Moi, je faisais mes devoirs là. C'était sa table de pause.» *(beat)* «Il n'y a pas de château. Il y a cette banquette.» · B1 «Ma mère a servi les cafés ici pendant neuf ans. Moi, je faisais mes devoirs à cette table : c'était sa table de pause.» *(beat)* «Il n'y a jamais eu de château. Il y a cette banquette.»
  - *(silence panel: the room has heard. Marin sits down on his chair very slowly.)*
- **If `s1.gus_photo` is with Lila:** Lila gets up, puts the Polaroid on the table («Augustin, 15 ans. Il dit qu'il sera comte.») and sits down again without a word.
- **Landing arguments** (examples): «La banquette, ce n'est pas le tissu. C'est toi.» · «Ta mère serait fière.» · «Si tu dis non, Solvel gagne. Et la banquette part à la déchetterie.» · «Garde la table de pause. On la met au fond, pour toi.»
- **Clumsy but sincere** (for example *«Gus… Ta place… c'est pas le cuir. C'est… tu restes. Avec nous. Signe ?»*) → GUS · A2 «C'est un argument épouvantable.» *(he takes the pen)* «Je signe.»
- **When it lands:**
  - GUS *(standing, to the room, the costume back on for one last performance)* · A2 «Mesdames, messieurs ! Augustin… de Créteil… signe !» · B1 «Mesdames, messieurs ! Augustin de… Créteil… a l'honneur de signer !»
  - Then a flurry of signatures. → `s1.gus_persuaded = true`
- **If it doesn't land, or [ Laisser Gus tranquille ]:** GUS · A2 «Pas ce soir.» → `false`. The tally stops at 187. T7 Day B decides.

> **Note.** This is where the canon tentpole «Gus's aristocracy exposed» pays off, and it is not a humiliation. He tells it himself, to save the room.

---

#### Variant: the last service (`s1.plan = last_service`)

**P3.** *Visual:* Gus arrives last with a bicycle chain and a padlock, and lays them on the zinc like a sword.
- GUS · A2 «Le 8 janvier, je m'attache au zinc. Solvel va devoir me porter dehors.» · B1 «Le 8 janvier, je m'enchaîne au zinc. Solvel devra me sortir en me portant.»
- MARGAUX · «Pas à mon zinc.»

**P4.** *(silence)* *Visual:* Margaux, not Gus, is the one who looks tired. Only the reader and you see it.

**The turn.** Gus turns to you: A2 «Toi, tu viens avec moi ? On a deux chaînes.»

**Solve · Convaincre (Gus).** Persuade Gus to let Margaux decide.

| Gus's objection | A2 |
|---|---|
| 1 | «Si on ne fait rien, on perd tout.» |
| 2 | «Margaux ne dit jamais ce qu'elle veut.» |
| 3 | «Et moi, je vais où, le soir ?» |

- **Landing arguments** (examples): «C'est à Margaux de choisir.» · «On ne perd pas les gens. On perd un bar.» · «Demande-lui. Pour une fois.»
- **Clumsy but sincere** (for example *«Gus, le soir… tu viens chez moi ? Chez nous ? On trouve un autre zinc.»*) → GUS · A2 «Un autre zinc.» *(he puts the chain in his pocket)* «Il faut qu'il soit en zinc. C'est tout ce que je demande.»
- → `s1.gus_persuaded = true`, or `false`. If false, Gus keeps the chain. It comes back in T8 ending 3 as a comic beat: he uses it to carry the bench.

---

### Midnight *(romance/friendship gate 5)*

**P5.** *Visual:* The whole café counting down around the long table. Marin holds his watch up, Romy films, and Gus stands on a chair. Near the door, Lila slips out onto the pavement before zero. Your panel shows the door swinging behind her.
- ALL · «Dix ! Neuf ! Huit !…»

**P6.** *Visual:* The pavement under the red neon, with the canal black beyond. Lila in her coat, the ochre scarf. You beside her, from behind. Through the glass, the room shouts «Bonne année !» and nobody out here does.
- LILA · A2 «Bonne année, l'héritage.»

**Your task.** Say what you want to say to Lila at midnight, a week before her train.

**Romance path.** An expression of feeling is needed, and it can be clumsy. The kiss is possible if `lila.heard_the_true_thing` or if this line confesses.
- *A confession* (for example *«Je ne veux pas une bonne année. Je veux… toi. Une semaine. C'est bête.»*) → *(silence panel: Lila looks at you for a long moment)* · LILA · A2 «Ce n'est pas bête.»
- **P7 (romance).** *(silence)* *Visual:* Seen from inside, through the café's glass, from behind the paper stars: two silhouettes under the neon, closing the distance. Lila moves last. The panel holds. → `s1.kiss = true`
- **P8 (romance).** LILA *(her forehead against yours)* · A2 «Une semaine. C'est déjà beaucoup.»
- *If the learner lets the moment pass,* LILA · A2 «Bonne année quand même.» *(she takes your arm)*. Nothing is lost. `s1.kiss = false`, and the platform in T8 carries the rest.

**Friendship path.** A pact.
- LILA · A2 «On se promet trois choses. Un : plus de secrets. Deux : tu ne refais jamais l'omelette. Trois : tu m'appelles en premier. Quand tu trouves quelque chose.»
- *The learner adds a fourth* (anything): LILA · A2 «Quatre. D'accord. Signé.» *(she spits on her palm; Marseille; you shake)*
- *Clumsy but sincere* (for example *«Quatre : tu reviens. Pas pour moi. Pour… le Mistral. Pour toi.»*) → LILA · A2 «Quatre. Je reviens. Pour moi.» *(beat)* «Et un peu pour toi.»

### Mid-point hook

**P9.** *Visual:* Back inside, after one in the morning. The long table is wrecked. Gus and Marin are asleep in the booth. Margaux, alone at the zinc, catches your eye as you come in and speaks very low.
- MARGAUX · A2 «Demain matin. Huit heures. Viens sans les autres.» · B1 «Demain, huit heures. Viens. Sans les autres.»
- CAPTION · A2 «Margaux veut te parler. Margaux ne parle jamais. À suivre…» · B1 «Margaux veut te parler. En vingt-cinq ans, personne ne l'a entendue demander ça. À suivre…»

---

## Day B · 1 January

**P0 · Précédemment.** A strip: the café crème on Odile's stool; midnight under the neon; «Viens sans les autres.»

**P1.** *Visual:* 8 a.m., New Year's Day. The shutter is half up. Inside, Gus and Marin are still asleep in the booth: Gus under his dinner jacket, Marin hugging the co-op folder (or the lease, or the chain). Margaux behind the zinc makes your usual order and slides it across.
- MARGAUX · A2 «Ta même chose.»

**P2.** *(silence)* *Visual:* Margaux pours herself a coffee, which she never does, and drinks it standing, looking out at the empty quai.

**P3.** *Visual:* Margaux and you across the zinc. The sleeping pair are in the background.
- MARGAUX · A2 «Je suis fatiguée.» *(beat)* «Vingt-cinq ans. Je veux voir la mer avant d'être vieille. Enfin… plus vieille.» · B1 «Je suis fatiguée.» *(beat)* «Vingt-cinq ans derrière ce zinc. J'aimerais voir la mer avant d'être vieille. Enfin… plus vieille.»

**P4.** *Visual:* The same framing. What she says next depends on the plan:
- **The lease, signed:** MARGAUX · A2 «J'ai signé. Neuf ans. Pour vous, pour elle. C'est long, neuf ans.»
- **The lease, unsigned:** MARGAUX · A2 «Si je signe, je reste neuf ans. Si je ne signe pas, je suis libre. Et vous, vous perdez le Mistral.»
- **The co-op, with Gus:** MARGAUX · A2 «Avec la coop, je ne suis plus seule. Mais ce n'est plus mon bar. C'est notre bar. Je ne sais pas faire "notre".»
- **The co-op, without Gus, or the last service:** MARGAUX · A2 «Marchand vend. Solvel me paie pour partir plus tôt. Je peux fermer le 7. Si tu vends, tu paies le feu, et tout finit… proprement.»
- **In every version:** MARGAUX · A2 «Ton appartement, c'est la dernière pièce. Je ne te demande rien. Tu choisis.» · B1 «Ton appartement, c'est la dernière pièce du puzzle. Je ne te demande rien. C'est toi qui choisis.»

### The turn

**P5.** *Visual:* Your balloon, across the zinc from a woman who has just asked for nothing.

**Your task.** Tell Margaux what you want, for her, for the café and for the flat. She has given you permission to want something.

- **(a)** *«Reste. On a besoin de toi.»* → MARGAUX · A2 «Je sais. C'est ça, le problème.»
- **(b)** *«Va voir la mer.»* → *(the barely-visible smile)* · MARGAUX · A2 «Tu parles comme Lila.»
- **(c) Clumsy but sincere.** *«Je veux… le Mistral. Et toi, libre. Et Odile… contente. C'est trop ?»* → MARGAUX · A2 «C'est trop. C'est bien.» *(beat)* «Choisis quand même.»
- **(d)** *«Et toi, qu'est-ce que tu veux ?»* → *(silence panel)* · MARGAUX · A2 «Personne ne m'a demandé ça depuis vingt-cinq ans.» *(beat)* «La mer.»

### Solve · Le choix *(the flat)*

The cards are drawn from the state (bible §6). Unavailable ones are not shown.

| Card | Shown when | Subtitle | Sets |
|---|---|---|---|
| **[ Garder l'appartement ]** | `marchand_only` and `margaux_persuaded`, or `kept` | lease: «Tu habites au-dessus du Mistral. Marchand quitte son immeuble pour que rien ne change.» · kept: «Tu habites au-dessus d'un café qui ferme.» | `keep` |
| **[ Le vendre à la coop ]** | truth public and `gus_persuaded` | «L'appartement devient l'atelier de tous. Là-haut, ce n'est plus chez toi.» | `coop` |
| **[ Le vendre à Solvel ]** | always | «Tu paies le feu. Margaux est libre. Le Mistral ferme le 7 janvier.» | `sell` |

> **Note.** If the lease is signed and the learner still chooses «sell», the café stays open on the lease under Solvel's upper floors. This folds into ending 3's emotional shape, with Margaux choosing to close anyway, because she is tired and now can. The writers accept this fold. The owner may prefer to hide «sell» once the lease is signed (open question).

---

## Resolution

**R1.** *(silence)* *Visual:* 9 a.m. The canal on New Year's Day, the city empty. You walk alone along the quai de Valmy. One pigeon, one jogger, and the locks.

**R2.** *Visual:* Back in the booth, the sleepers wake. Marin sits up, sees the folder in his arms and remembers.
- MARIN · A2 «On a… On a gagné ? On a perdu ?»
- GUS *(without opening his eyes)* · A2 «Mon cher, on a surtout trop bu.»

---

## À suivre…

**Last panel.** *Visual:* Odile's flat. On the kitchen wall, her calendar is still stopped on **April 2023**. Beside it, you pin a new calendar, **January 2027**, and circle one date in pen: **8**. The two calendars hang side by side.
- CAPTION · A2 «Dans sept jours : le train de Lila. La fin de l'offre. Et tout le reste. À suivre…» · B1 «Dans sept jours : le train de Lila, la fin de l'offre de Solvel, et tout ce qu'on n'a pas encore dit. À suivre…»

> **Note.** The learner turns the time capsule's clock forward. It is the season's quietest meaningful change.

---

## State out

- `s1.margaux_persuaded` / `s1.gus_persuaded`
- `gus.aristocracy_exposed = true` (co-op variant; canon flag)
- `s1.kiss`
- `s1.lila_path` (final)
- `s1.flat_decision`
- `margaux.wants_out = named` (fixed)

## For gap 7 (the last week)

- The decision is made. The week is about «last times», not about reversing it.
- Nobody finds the letter before T8.
