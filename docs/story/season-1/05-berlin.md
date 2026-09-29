# Tentpole 5 · «Berlin»

*Lila has a one-year residency in Berlin: a studio, a grant and a date, 9 January. She wants it. She tells you, or you find out first, and which one depends on what you did with the photograph in T4. On the romance path, what she tells you and what you say back are also about the two of you. On the friendship path they are about courage.*

**How to read this script.** It uses the same conventions as T4. **A2** is the default line and **B1** is given only where it differs. *(silence)* panels have no dialogue. Character lines are captions. **Your line** is a balloon in its panel. **Note** lines are for the owner only.

---

## State in

- **After T4.** The quartier knows about the fire (`fire_photo = wall`), or pretends not to (`margaux`). The flat's debt is real. Marin is still pushing «Le Mistral à nous», and his plan of the back room has a square labelled **ATELIER DE LILA**: her afternoon painting classes for children are the co-op's daytime income.
- **The generated days since T2 have seeded:**
  - the **disastrous improvised dinner** in Odile's kitchen (an omelette, the smoke alarm, Lila laughing so hard she has to sit on the floor);
  - **getting caught** on the building's roof by M. Marchand;
  - **an argument and a hesitant apology.**

  Each of these left a line the learner chose to say. Together those lines set `s1.lila_path`.
- **The residency.** It is fictional: Künstlerhaus am Kanal, Berlin. Lila must confirm by 15 December. Her train from Gare de l'Est leaves on 8 January.
- **Variant selection:**
  - **A · «Elle te le dit»** if `s1.fire_photo = wall`.
  - **B · «Tu le découvres»** if `s1.fire_photo = margaux`. It takes place in Odile's flat if `s1.lila_has_key`, and otherwise in Marin and Lila's flat (see B, end note).

### What the conversation means in each version

| | Romance path | Friendship path |
|---|---|---|
| **A · she tells you** | You are the first person she tells because you are the one person whose «reste» she is afraid of hearing. Telling you is the confession she won't make. | You are her accomplice, and she needs one to face Marin. The scene is about courage. |
| **B · you discover** | You learn she is leaving before you have learned what you are to each other. The hurt is out of proportion, and both of you notice. The quarrel is the confession. | A quarrel between two accomplices who both kept a secret. It ends in a truce and a private joke. |

> **Note (intent).** Lila never asks permission, and the learner can never stop her. What the learner's words change is *how* she goes, what she carries, and what they are to each other afterwards. The two halves of the owner's line are the whole scene: «je te veux ici» and «je veux ça pour toi». The best reply says both badly.

---

## Variant A · «Elle te le dit»

**P1.** *Visual:* Le Mistral, Monday, closing time. Chairs going up on tables. Gus, already in his coat, stands in the middle of the room with a list; Marin stacks chairs and listens patiently.
- GUS · A2 «La boulangère m'a rendu la monnaie… sans parler. Sans parler, Marin !» · B1 «La boulangère m'a rendu la monnaie en silence. En silence, Marin ! Depuis samedi, je suis un paria.»
- MARIN · «C'est peut-être un signe.»
- GUS · «Un signe de quoi ?»
- MARIN · «Je sais pas encore.»

**P2.** *Visual:* Margaux puts her ring of keys on the zinc in front of you and Lila, then shrugs on her coat. Gus and Marin are already at the door.
- MARGAUX · A2 «Vous fermez.» *(not a question)*

**P3.** *Visual:* You reach for your coat on the hook. Lila, behind you, has not taken hers.
- LILA · A2 «Reste. Deux minutes.»

**P4.** *(silence)* *Visual:* Lila behind the zinc, badly working the machine Margaux never lets anyone touch; steam everywhere. She puts a cup in front of you: your usual, exactly right (from `user.usual_order`). She has been paying attention for weeks.

**P5.** *Visual:* She slides a printed letter across the zinc. Its letterhead is legible: **Künstlerhaus am Kanal · Berlin**. You are reading, from behind; she watches you read.
- LETTER (diegetic) · A2 «Madame Bonnet, nous sommes heureux de vous proposer une résidence d'un an à Berlin, à partir du 9 janvier. Merci de confirmer avant le 15 décembre.» · B1 «Madame Bonnet, nous avons le plaisir de vous proposer une résidence d'un an, atelier et bourse compris, à partir du 9 janvier. Nous vous remercions de confirmer avant le 15 décembre.»

**P6.** *Visual:* Close. Lila with both hands round her own cup, not drinking.
- LILA · A2 «Je vais dire oui. Tu es la première personne à le savoir. Même pas Marin.» · B1 «Je compte accepter. Tu es la première personne à qui je le dis. Même Marin ne le sait pas.»

> **Agreement note.** «La première personne» agrees with «personne», which is feminine whatever the learner's gender, so the line holds for every learner. Avoid the shorter «tu es la première / le premier».

### The turn

**P7.** *Visual:* Across the zinc, Lila facing you, and your empty balloon.
- LILA · A2 «Dis-moi un truc vrai. Pas un truc gentil.» · B1 «Dis-moi quelque chose de vrai. Pas quelque chose de gentil.»

**Your task.** Tell Lila what you actually feel about her going, for her and for yourself. She has asked you not to be polite.

### Exchange 1

**(a) Quick support.** *«C'est génial ! Tu dois partir !»*
- LILA · A2 «Tu dis ça vite.» *(beat)* «Trop vite. Encore une fois ?» · B1 «Tu dis ça bien vite. Essaie encore.»
- **Note.** This is not a punishment. It is a second chance to say the real thing, and the exchange repeats once. If the learner repeats the same line, she accepts it: A2 «D'accord. Merci.», with a small smile that doesn't reach her eyes. Friendship is unaffected. On the romance path it sets `lila.heard_the_true_thing = false`.

**(b) Honest want.** *«Je ne veux pas que tu partes.»*
- *Romance:* *(silence panel: she puts the cup down)* · LILA · A2 «Voilà. Ça, c'est vrai.» *(beat)* «Je pars quand même. Je crois.» · B1 «Voilà. Ça, c'est un truc vrai.» *(beat)* «Je vais partir quand même. Je crois.»
- *Friendship:* LILA · A2 «Moi non plus, je ne veux pas partir d'ici. C'est pour ça que je dois partir.» · B1 «Moi non plus, je n'ai pas envie de partir d'ici. C'est justement pour ça qu'il le faut.»

**(c) Clumsy but sincere.** *«Je veux toi… ici. Et je veux Berlin… pour toi. Les deux. C'est bête.»*
- LILA · A2 «Non. C'est pas bête. C'est ma phrase. Je la cherche depuis un mois.» · B1 «Ce n'est pas bête. C'est exactement ma phrase. Ça fait un mois que je la cherche.»
- **Note.** This is the best reply in the season's central relationship, and it is grammatically wrong («je veux toi»). The margin offers «je te veux ici» and «je veux que tu sois ici». The plot keeps what was meant. On the romance path this line alone can carry T7's kiss.

**(d) Deflection.** *«Et Marin ? Et le Mistral ?»*
- LILA · A2 «Voilà. Tout le monde pense à Marin. Moi, je t'ai demandé à toi.» · B1 «Et voilà. Tout le monde pense d'abord à Marin. C'est à toi que je pose la question.»
- **Note.** The exchange repeats once. The deflection is exactly the group habit Lila is trying to leave.

### Exchange 2: the portrait

**P8.** *Visual:* The back room of Le Mistral, rebuilt after the fire, with new plaster and a slightly different white. Under a sheet on an easel is Lila's group portrait, which Margaux lets her keep here. She pulls the sheet off. The booth: Marin mid-laugh, Gus mid-gesture, Romy with her microphone lowered, Margaux behind the zinc, and a new face at the zinc, Odile, painted from a Polaroid. In the bottom corner is a figure seen from behind, in a slightly-too-heavy coat.
- LILA · A2 «Là, dans le coin. C'est toi. De dos. Je n'ai pas encore trouvé ton visage.» · B1 «Là, dans le coin, c'est toi. De dos. Ton visage, je ne l'ai pas encore trouvé.»

> **Note.** This is the app's rule of never showing Toi's face, turned into a line of the story. It comes back in T8.

- *Romance:* LILA · A2 «Tu crois que je peux le trouver… de loin ?» · B1 «Tu crois qu'on peut trouver un visage de loin ?»
- *Friendship:* LILA · A2 «Je le finis à Berlin. Tu m'envoies des photos de toi. Des photos ridicules, s'il te plaît.» · B1 «Je le finirai à Berlin. Tu m'enverras des photos de toi, les plus ridicules possible.»

**Your task.** Answer her about the face, in any way at all. Replies might be *«Reviens le finir.»*, *«Non. Il faut être ici.»* or a joke (*«Fais-moi beau / belle.»*).
- To «Reviens le finir» · LILA · A2 «C'est une invitation ou un ordre ?» *(a real smile)*
- To «Il faut être ici» · LILA · A2 «Peut-être. Ou peut-être que je te vois mieux de loin.»
- To a joke · LILA · A2 «Impossible. Je peins la vérité, moi.»
- **Agreement.** «Fais-moi beau / belle» is the learner's own choice. Lila's replies are agreement-free.

### Solve · Le choix

**P9.** *Visual:* Lila throws the sheet back over the portrait. She stands in the doorway of the back room, coat now on, looking at the plan pinned by the door, Marin's plan, with its square labelled «ATELIER DE LILA».
- LILA · A2 «Il faut le dire à Marin. Ce soir. Tu viens avec moi ?» · B1 «Il faut que je le dise à Marin. Ce soir. Tu viens avec moi ?»

- **[ Oui, je viens ]**, subtitle «Marin saura que tu savais.» → `s1.went_with_lila_to_marin = true`
- **[ Non. C'est à toi. ]**, subtitle «Lila y va seule.» → `false`

> **Note.** Going is support, but it entangles you in Marin's disappointment, and his plan is the one your flat could save. Staying away respects her, but she walks alone. On the romance path, staying away also reads as «this is not mine to hold yet». On the friendship path, going with her is the accomplice's instinct.

### Resolution A

**R1.** *Visual:* The canal at one in the morning. Two figures walk under the plane trees, the locks black and still.
- *Romance:* *(silence)* Your shoulders nearly touch. She has paint on her thumb from the portrait; so do you, on the back of your hand. At the foot of her building she wipes the ochre off your hand with her thumb, and the thumb stays a second too long.
- LILA *(romance)* · A2 «Pas maintenant.» *(beat)* «Mais pas jamais.»
- *Friendship:* Lila rehearses what she will say to Marin and makes you play Marin. She does his voice when you won't. LILA · A2 «"C'est un signe, ça !"» *(she laughs)* «Il va pleurer. Il va pleurer et me faire une crêpe.»

**R2.** Variant by the choice:
- *You went:* the door opens. Marin in his socks, delighted to see both of you, holding up the co-op folder like a trophy. MARIN · A2 «Vous tombez bien ! Regardez ce que j'ai fait pour toi, Lila !»
- *You didn't:* *(silence)* From the street, you watch the third-floor window light up. Two silhouettes. One of them sits down very slowly.

### À suivre… (A)

**Last panel.** *Visual:* Close on the folder in Marin's hands, open to the plan of the back room. The square «ATELIER DE LILA» has been coloured in, carefully, with a child's felt-tip.
- CAPTION · A2 «Marin a fait une place pour Lila. Dans trois semaines, cette place va être vide. À suivre…» · B1 «Marin a gardé une place pour Lila. Dans trois semaines, elle sera vide. À suivre…»

---

## Variant B · «Tu le découvres»

*(Odile's flat, `s1.lila_has_key = true`. See the end note for the version without the key.)*

**P1.** *Visual:* The stairwell at night. Your hand with the key; the timed light ticking. Under Odile's door there is a line of light that should not be there.
- CAPTION · A2 «Deux heures du matin. Tu ne dors pas. En haut, il y a de la lumière.» · B1 «Deux heures du matin. Impossible de dormir. Là-haut, quelqu'un a laissé la lumière.»

**P2.** *(silence)* *Visual:* Odile's room, empty of people. Her things have been pushed carefully to one side: her chair, her Polaroid box, her calendar still on May 2022. The space is full of Lila: an easel, a canvas half-wrapped in bubble wrap, and a wooden crate. On the drainer, two washed mugs, one of them the one you always use. She has been coming here for weeks.

**P3.** *(silence)* *Visual:* Close on the crate. The stencil is legible: **FRAGILE · BERLIN · KÜNSTLERHAUS AM KANAL**.

**P4.** *Visual:* On the easel's ledge, a card in Lila's quick handwriting, addressed to you, with its last line unfinished.

### Solve · Déchiffrer

The card fills the screen.

> **A2**
> *À toi —*
> *Viens voir la toile. Demain, je la mets dans la caisse.*
> *Pardon pour l'autre soir. «Encore un secret», j'ai dit. Moi aussi, j'ai un secret.*
> *Je pars le 8 janvier, à Berlin. Je veux te le dire avant tout le monde, et je*

> **B1**
> *À toi —*
> *Passe voir la toile avant qu'ils l'emballent.*
> *Pardon pour l'autre soir, pour mon «encore un secret». J'étais mal placée pour le dire : moi aussi, j'en garde un.*
> *Je pars le 8 janvier, à Berlin. Je voulais te le dire avant tous les autres, et je*

**Prompt:** «Ce message, c'est quoi ?» («What is this message?»)
- **A1/A2.** One tap: **[ Une invitation ]**, **[ Des excuses ]** or **[ Un adieu ]**.
- **B1.** «Tout ce qui est vrai», any combination.
- **There is no wrong answer.** Each reading is true: «Viens voir la toile», «Pardon», «Je pars». What the learner taps sets how Lila finds you when she walks in: hurt if they tapped *adieu*, softened if *invitation*, wary if *excuses*. It also comes back in her line in Exchange 1 (c).

> **Note.** This is the owner's own example of Déchiffrer («an invitation, an apology or a goodbye?»), and the honest answer is «the three». The learner is doing exactly what a reader does with a message from someone they care about.

**P5.** *(silence)* *Visual:* The doorway. Lila with two paper cups from the all-night place on the corner, one of them your usual. She sees you, sees the card in your hand, and stops.

**P6.** *Visual:* Two-shot across the crate.
- LILA · A2 «Tu as lu.» *(not a question)*
- *If the learner read «adieu»:* LILA · A2 «Vas-y. Dis-le. Tu es en colère ?» · B1 «Vas-y. Dispute-toi avec moi. Tu en as le droit.»
- *If «invitation»:* LILA · A2 «Bon. Au moins, l'invitation, elle marche.»
- *If «excuses»:* LILA · A2 «Oui. C'était des excuses. Et le reste aussi.»

> **Agreement.** «Tu es en colère ?» is agreement-free. Avoid «Tu es fâché(e) ?» here.

### The turn

**P7.** Your balloon, empty, facing her across the crate.

**Your task.** Say what finding it this way does to you, and what you want now: from her, from yourself, from the two of you.

### Exchange 1

**(a) The hurt question.** *«Tu allais me le dire quand ?»*
- LILA · A2 «Après. Toujours après.» *(beat)* «Comme toi, avec la photo.» · B1 «Après. C'est toujours après, ici.» *(beat)* «Comme toi avec la photo.»
- *(silence panel: she regrets it)*
- LILA · A2 «Pardon. C'était pas juste.» · B1 «Pardon. C'était bas, ça.»

**(b) Cold.** *«OK. Bon voyage.»*
- *(silence panel: she puts both cups down on the crate)*
- LILA · A2 «Non. Pas comme ça. Dispute-toi avec moi, au moins.» · B1 «Non. Pas comme ça. Engueule-moi, si tu veux, mais pas ça.»
- **Note.** A second chance is offered, and the exchange repeats. Coldness is not a dead end. The owner's rule is that misunderstandings create chances to connect.

**(c) Clumsy but sincere.** *«Je lis ta carte. C'est… adieu ? Ou pardon ? Je comprends pas bien. Je veux pas adieu.»*
- LILA · A2 «C'est les trois. Invitation, pardon, adieu. Tu as bien lu. C'est moi qui écris mal.» · B1 «C'est les trois à la fois. Tu as très bien lu. C'est moi qui ne sais pas écrire ce genre de chose.»
- **Note.** The learner's fear of not understanding becomes her admission. This is the reversal we want the learner to feel: the comprehension doubt was the right reading.

**(d) Warm but honest.** *«Je suis content pour toi. / Je suis contente pour toi. Mais tu pouvais me le dire.»*
- LILA · A2 «Je sais. J'ai écrit cette carte six fois. Je n'ai jamais fini la phrase.» · B1 «Je sais. J'ai commencé cette carte six fois. Je n'ai jamais réussi à finir la phrase.»

### Exchange 2: the portrait, and the group

**P8.** *Visual:* She unwraps the canvas for you, bubble wrap crackling. It is the same portrait as in A, with you in the corner from behind.
- LILA · A2 «C'est toi. De dos. Je n'ai pas encore trouvé ton visage.»
- *Romance* · B1 «Je n'arrive pas à trouver ton visage. Peut-être que je ne veux pas le finir.»
- *Friendship* · A2 «Ton visage, je le fais à Berlin. De mémoire. Ça va être une catastrophe.»

**P9.** *Visual:* Lila sits on the crate. You are on Odile's chair. The Polaroid box is between you.
- LILA · A2 «Ici, on s'aime beaucoup. Et on se retient beaucoup. Margaux avec Odile. Moi avec Marin. Et toi…» *(she stops)* · B1 «Ici, on s'aime en se retenant. Margaux a retenu Odile avec un mensonge. Moi, je me retiens avec Marin. Et toi…» *(she stops)*
- *Romance:* she doesn't finish the sentence. *(silence panel)*
- *Friendship:* LILA · A2 «…toi, tu retiens tout le monde avec cet appartement.» · B1 «…toi, tu retiens tout le monde avec cet appartement. Sans le vouloir.»

**Your task.** Answer her theory, which is also Lila's side in the fight over the café's future. Replies might be *«Non. On s'aide.»*, *«Peut-être. Tu as raison.»*, or on the romance path the unfinished sentence finished by you (*«Et moi, je te retiens ?»*).
- To «On s'aide» · LILA · A2 «Oui. Les deux. C'est ça, le problème.»
- To «Tu as raison» · LILA · A2 «Je déteste avoir raison la nuit.»
- To «Et moi, je te retiens ?» · *(romance; silence panel)* · LILA · A2 «Un peu. Pas assez pour rester. Trop pour partir tranquille.» · B1 «Un peu. Pas assez pour que je reste. Trop pour que je parte tranquille.»

### Solve · Le choix

The same choice as in A: «Il faut le dire à Marin. Demain matin. Tu viens avec moi ?» → **[ Oui, je viens ]** or **[ Non. C'est à toi. ]**

### Resolution B

**R1.** *(silence)* *Visual:* The two of you wrapping the portrait together: tape screeching, bubble wrap, her holding, you taping. An ordinary task at two in the morning.

**R2.**
- *Romance:* she wipes ochre off your hand with her thumb, and the thumb stays. LILA · A2 «Pas maintenant.» *(beat)* «Mais pas jamais.»
- *Friendship:* at the door, coat on. LILA · A2 «Promets-moi un truc. Après mon départ, tu ne refais jamais l'omelette. Jamais.» · B1 «Promets-moi une chose. Quand je serai partie, tu ne referas jamais l'omelette.» She points at the smoke alarm, still hanging from its wire since the disastrous dinner.

### À suivre… (B)

**Last panel.** *Visual:* Lila's phone, face up this time, on the crate. A message from Marin.
- SMS (diegetic) · «Tu rentres ? J'ai une surprise pour toi. Pour le Mistral !»
- CAPTION · A2 «Marin a une surprise pour Lila. Lila a une caisse pour Berlin. À suivre…» · B1 «Marin prépare une surprise pour Lila. Lila, elle, a fait sa caisse pour Berlin. À suivre…»

> **End note: B without the key.** The scene moves to Marin and Lila's flat. Marin is in Finistère for the weekend (his father thread). You come by to return the casserole dish from the disastrous dinner. The crate stands in the hallway, and the card is on the fridge under a magnet shaped like a sardine. Lila comes back from the épicerie with two cups. Everything else holds. The only lost detail is the washed mug in Odile's kitchen, which is replaced by your drawing still on their fridge from the dinner.

---

## State out

- `lila.berlin_revealed = true`
- `s1.berlin_told_how = told | discovered`
- `s1.went_with_lila_to_marin = true | false`
- `s1.lila_path`: updated only by what was *expressed* here. For example, (b) or (c) said with romantic intent confirms romance, and a joke-first scene keeps friendship. It is never shown.
- `lila.heard_the_true_thing` (romance only): read by T7

## For the director (generated days after T5)

- Lila is leaving. She does not become sad or distant. She becomes *practical* about everyone else's life, which is how she meddles (canon).
- Marin now knows, in both versions. He says nothing about it for two episodes and bakes too much. The folder stays on the fridge.
- **Never** write a scene where the learner can ask Lila to stay as a mechanic. They can say it, and she can hear it, but it is not a choice card.
