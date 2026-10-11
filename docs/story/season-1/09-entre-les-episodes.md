# Entre les épisodes: the generated days

*For the story engine's director (WP-110..114). There are 43 generated days, in the seven gaps between tentpoles (calendar in the bible, §8). This file tells the director what each gap may do, what it must not do, and what a good day looks like.*

---

## The rule: episodes without meaningful change are refused

Every generated day must end with **something different from how it began**, and the difference must be something the learner can see. A day qualifies if at least one of these changes:

| Kind of change | Examples |
|---|---|
| **A relationship** | Something said that can't be unsaid. A gesture that becomes a habit. A first *tu*. A first time someone waits for you. |
| **Knowledge** | The learner, or a character, learns something true, or something false that they now believe. |
| **A situation** | An object moves, a plan advances or is blocked, a decision is taken, a letter arrives. |
| **Your life in Paris** | Your return ticket moves, your usual order is known, a first time happens (first bread, first *vous* that worked, first key cut). |

**Quiet changes count.** These are good days:
- **Bread with Lila (gap 1).** Your first awkward morning together at Mme Diallo's. Lila orders for you, «une tradition pas trop cuite». Then she makes you order the second one yourself, and she pays for yours without a word. *The change:* the baker knows your face, and Lila has started looking after you. Nothing else happens, and it is a real episode.
- **«La même chose ?» (gap 1).** Margaux asks your order for the third time, then doesn't ask any more. *The change:* you are a regular.
- **Marin's soup (gap 1).** Your radiator dies. Marin arrives with soup and a hot-water bottle and does not leave until you've eaten. *The change:* someone knows where you live.
- **The two croissants (gap 6).** On Christmas morning there are two croissants in a paper bag at Odile's door, from Marchand. *The change:* the Sunday ritual has found a new address.

**Refused.** The critic (WP-114) rejects these, and the director retries once:
- **«Une soirée comme une autre».** The group chats about the weather, the playlist or the metro, and nothing moves.
- **An errand that could happen on any day with any cast.** «Help Romy record fifteen minutes on Tuesday» is refused, unless it changes something between you.
- **A dramatic investigation that learns nothing.** A mystery beat that ends where it began is refused.
- **A day that advances a thread the tentpole owns.** See each gap's «must not» list.

## The shape of a generated day

- **Length.** One page of **4–6 panels**, **2–3 exchanges**, and at most one mechanic (Enquête, Convaincre, Choix, Déchiffrer).
- **Episode grammar.** Every day has a **goal** (someone wants something today), an **obstacle**, a **turn to you** (what you must want to say) and a **hook** («À suivre…»).
- **Silence.** At least one panel without dialogue.
- **Humour.** At least one laugh, most days. Gus and Marin first.
- **Two characters in frame** on most panels, doing something: carrying, cooking, measuring, painting, arguing.
- **Complication cards** create an obstacle *in the next day*, and it must be visible there.

### The director's checklist (each day must fill it before generating)

1. **Thread(s) touched,** from the gap's list below.
2. **The change,** written as «before → after» in one sentence.
3. **The turn,** and what the learner must want to say (never a grammar target).
4. **The small moment,** and whose it is.
5. **The hook.**
6. **Forbidden reveals respected:** the gap's «must not» list.

**Register rules** (bible §9) apply to every generated line:
- Lines addressed to Toi are agreement-free.
- Camille's lines about Camille are agreement-free, and pronouns come from `s1.camille_gender`.

---

## Gap 1 · Days 3–7 (13–17 November) · «La première semaine»

**Threads that may advance, and how far**
- **Settling.** The notary explains that nothing can be sold for weeks, and your ticket moves to **2 December** (`user.return_ticket`). Your usual order is established (`user.usual_order`).
- **The group, one by one.** One-on-one time with each of Lila, Marin, Gus and Margaux.
- **Romy is introduced** (she was not in T1). She is interviewing Margaux for her story on Solvel buying cafés, and she finds «l'héritage d'Odile» more interesting than the story.
- **Marchand is glimpsed** on the stairs with his keys: «La succession Ferrand. Bonjour.»
- **Solvel.** A formal letter reminds you of the offer, valid until 8 January.
- **The café's fire of 2023** may be *mentioned once*, as the official story: the back room and the wiring. Gus: «Marchand en profite.»

**Small moments available**
- Margaux's first «La même chose ?» (Margaux).
- Bread with Lila and Mme Diallo (Lila).
- Soup in your cold studio (Marin).
- Gus's first accidental *tu*, followed by a panicked return to *vous* (Gus).
- Romy switching off her recorder when you look uncomfortable (Romy).
- «La succession Ferrand» on the stairs (Marchand).

**Complications allowed**
- The radiator dies (canon).
- The notary needs a document from «là-bas».
- The price becomes gossip (if `s1.price_public`).
- Rain, every day.

**Must NOT happen yet**
- Anyone entering the flat.
- Any Polaroid or the notebook.
- Berlin.
- The Sundays.
- The co-op idea.
- Anything romantic beyond Lila being curious.

**Example premises**
1. **«Le billet».** You must call the airline to move your ticket, in French, with Lila as a coach who keeps making it worse on purpose. *The change:* the ticket moves, and so does something in you. *The turn:* explain to the agent why you are staying. The learner decides how honest to be.
2. **«Romy enquête».** Romy interviews Margaux at the zinc («J'ai rien entendu»), then turns to you: «C'est vous, l'héritage ?» *The change:* you learn that Solvel has bought three cafés in the quartier this year, and Romy has a source she likes.
3. **«La même chose ?»** Margaux asks your order for the third time. Gus insists your order says who you are. You choose, and say why you're still here. *The change:* your usual order exists. Gus announces that you are «un habitué», and it is not a joke.

---

## Gap 2 · Days 10–15 (20–25 November) · «L'appartement s'ouvre»

**Threads that may advance, and how far**
- **The Polaroid box.** Sorting it and reading captions makes funny days.
- **Lila painting upstairs at 7 a.m.** (if `s1.lila_has_key`).
- **Marin starts a spreadsheet** after Lila shows him the notebook page. He asks your permission to use «Odile's idea».
- **Gus starts his petition.**
- **The Gus photo** may change hands: `s1.gus_photo`.
- **Romy's Solvel story** advances.
- **Camille** emails an inventory deadline.
- **Romance/friendship gate 2**, the disastrous improvised dinner, belongs here.

**Small moments available**
- Lila's coffee cup in your sink (Lila).
- Marin finding his own Polaroid and crying at it (Marin).
- Gus calling you «mon cher» (Gus).
- Margaux looking at the ceiling when you mention upstairs, in a silent panel (Margaux).
- Mme Diallo recognising herself in a Polaroid you bring her (minor).

**Complications allowed**
- A water cut announced by the Gérance Marchand.
- Bastien Roux phoning you directly.
- Camille's deadline.
- The smoke alarm.

**Must NOT happen yet**
- The fire's origin.
- Anyone separating the stuck Polaroids.
- The notebook's last pages.
- Berlin named. Only hints: an envelope with a German stamp, closed quickly.
- The Sundays explained.
- Gus's truth.

**Example premises**
1. **«Le dîner raté»** (gate 2). You and Lila improvise dinner in Odile's kitchen. The omelette burns and the smoke alarm screams. Margaux comes up the stairs *running, with the café's fire extinguisher*, sees the omelette, and goes back down without a word. *The turn:* the line that saves the evening (bible §7). *The change:* a private joke is born, «ne refais jamais l'omelette». The reader has watched Margaux react too fast to smoke from this kitchen. Nobody on the page remarks on it.
2. **«Je peux ?»** Marin, holding the notebook page, asks whether he may use Odile's plan. He cannot ask without a grandmother's saying and three apologies. *The change:* the spreadsheet exists, with your blessing, or without it but with your knowledge.
3. **«Pour son anniversaire».** It is Gus's birthday (a good day for it). Lila wants to give him his Polaroid at fifteen, framed. You decide with her: give it, keep it, or hide it. *The change:* `s1.gus_photo`. If given, Gus laughs too loudly and takes it home. The costume holds, and the reader sees his hands.

---

## Gap 3 · Days 18–24 (28 November – 4 December) · «Avant la fête»

**Threads that may advance, and how far**
- **Party preparations,** including the wall.
- **The two promises weigh on you.** Gus and Marin each rehearse their announcement with you.
- **Marchand's reply,** if invited: a card, «J'y serai. M.»
- **Romy's editor** pushes the Solvel story.
- **Lila closes an email** too quickly.
- **Getting caught somewhere you shouldn't be**, on the roof, belongs here.

**Small moments available**
- Lila copying Odile's captions onto little cards at your table while you dictate (Lila).
- Gus rehearsing on index cards (Gus).
- Marin testing canapés on you (Marin).
- Margaux saying «pas de fête» twice a day while buying garlands (Margaux).
- Marchand's handwriting on the reply card (Marchand).

**Complications allowed**
- The stuck Polaroids (Lila: «Je les décolle samedi»).
- Gus and Marin almost discovering each other's ask.
- A letter from the insurer to Margaux, which she hides under the till.
- A rain forecast.

**Must NOT happen yet**
- Separating the stuck Polaroids.
- The fire's origin.
- Margaux's secret.
- Berlin revealed.
- Any announcement made before the party.

**Example premises**
1. **«Sur le toit».** Lila takes you up through the fifth-floor skylight to see the canal from the roof at night. M. Marchand's torch finds you: «La succession Ferrand n'a rien à faire sur mon toit.» You must talk your way down in your best *vous* while Lila giggles. *The change:* Marchand has met you both as a pair, and Lila now has a story she tells everyone.
2. **«Au milieu du mur».** Lila asks which Polaroid goes in the centre of the wall. You choose. The best choice is Odile at the zinc with her café crème, and that is the one Margaux will unpin in T4 P3. *The change:* the wall is ready, and so is its heart.
3. **«Deux répétitions».** Gus rehearses his petition speech, and an hour later Marin rehearses his pitch, both to you. *The change:* you realise both will speak at the party. *The turn:* you tell one of them what you'll say, or refuse to.

---

## Gap 4 · Days 27–32 (7–12 December) · «Le quartier sait» (or pretends not to)

**Threads that may advance, and how far**
- **The aftermath of the reveal,** by `s1.fire_photo`:
  - `wall`: the quartier is kind, and cruel, and curious.
  - `margaux`: thirty people act as though nothing happened, badly.
- **The estate's liability.** The notary explains «à concurrence de l'actif net» in two plain sentences: «La dette peut prendre l'appartement. Pas plus.»
- **Margaux's silence.**
- **Gus's hurt.**
- **Marin's folder,** in the bin and out of it.
- **Lila's deadline** (15 December), hinted at.
- **Romance/friendship gate 3,** the argument and the hesitant apology, belongs here.

**Small moments available**
- Mme Diallo's free croissant «pour Odile» (`wall`), or her careful not-looking (`margaux`) (minor).
- Gus back on *vous* with you for a day, then slipping (Gus).
- Margaux leaving the zinc's flap up (Margaux).
- Marin's soup left at your door without knocking (Marin).
- Romy saying the memory card is «fermée» (Romy).

**Complications allowed**
- The insurer's second letter to Margaux.
- Solvel raising the pressure («valable jusqu'au 8 janvier»).
- Camille meeting you at the notary's for Grand-père's claim: the first *real* disagreement.

**Must NOT happen yet**
- Berlin revealed.
- Marchand's account or the Sundays (T6).
- The notebook's last pages.
- Any decision about the flat.

**Example premises**
1. **«La dispute»** (gate 3). The argument with Lila is about secrets:
   - `margaux`: she resents «encore un secret».
   - `wall`: you blame her «remets-la au mur», because Margaux's insurer has called.

   The next morning comes the hesitant apology, from you or from her. *The turn:* the apology line, where what is expressed decides the gate. *The change:* you have fought, and you are still here.
2. **«Chez le notaire».** Maître Vasseur explains the debt. Camille is in the waiting room for Grand-père's claim against the estate. You disagree precisely, for the first time: «Je comprends. Je ne suis pas d'accord.» *The change:* you know what the flat is worth to the fire, and Camille knows you won't just sign.
3. **«Vous».** Gus uses *vous* with you. *The turn:* get him back to *tu* without mentioning the party. *The change:* he slips at the end, «Tu… vous… tu veux un café ?», or he doesn't, and the next day says it first.

---

## Gap 5 · Days 35–41 (15–21 December) · «Le départ commence»

**Threads that may advance, and how far**
- **Lila has confirmed Berlin.** Her last school day is 18 December.
- **Marin knows.**
- **Margaux's recorded letter:** «fin du bail le 31 mars».
- **Romy's editor** wants the Solvel story by Christmas.
- **The portrait's corner** gains your coat.
- **Camille:** a short email proposing «une rencontre avec mon grand-père».
- **Solvel's Bastien** measures the café's back room during service (canon s3).

**Small moments available**
- Lila's pupils' drawings, «Maîtresse à Berlin» (Lila).
- Marin baking far too much (Marin).
- Margaux putting the recorded letter under the till unopened (Margaux).
- Romy's tuque for you (Romy).
- The camp bed glimpsed again through the office door (Marchand).

**Complications allowed**
- The freight company wants the crate by the 22nd.
- Bastien in the café.
- The lease letter.
- The insurer.

**Must NOT happen yet**
- The Sundays or Marchand's account (T6).
- The notebook's last pages.
- Margaux's «fatiguée».
- The flat decision.
- Any suggestion that Lila might stay.

**Example premises**
1. **«Le dernier jour d'école».** You help Lila carry thirty paintings out of her classroom. A child asks you «Tu vas où, toi, quand elle part ?». *The turn:* answer a seven-year-old honestly. *The change:* the leaving is real, and it has a date on a child's drawing.
2. **«L'homme au beau manteau».** Bastien measures the back room during lunch service. Gus confronts him with escalating superlatives, and you have to stop Gus before he says something true. *The change:* Solvel's plan becomes concrete: a hotel lobby where the booth is.
3. **«Trop de far breton».** Marin has baked for a week and can't talk about Lila. *The turn:* get one sentence out of him. *The change:* he says «Elle a raison de partir», and then cries at a train advert.

---

## Gap 6 · Days 44–50 (24–30 December) · «Noël, et le plan»

**Threads that may advance, and how far**
- **The plan forms** by `s1.plan`:
  - `lease`: Marchand asks, through Camille, to see Margaux, and she refuses to discuss it.
  - `coop`: the member count climbs to about 150, then stalls. The bank wants a guarantee.
  - `last_service`: Margaux starts giving her glasses away.
- **Christmas Eve at Le Mistral.**
- **Romy's article** has landed (if public), and the quartier reacts.
- **Lila's crate has gone.** She has only a suitcase left.

**Small moments available**
- The two croissants at your door on Christmas morning (Marchand).
- Margaux's café crème for Odile's stool on Christmas Eve (Margaux).
- Lila's present to you (Lila):
  - romance: a small painting of the key ring with the cicada;
  - friendship: a painting of the omelette, smoke and all.
- Gus's present: an index card engraved «Règle n°1 : rester» (Gus).
- Marin's father phoning on Christmas Day, and Marin answering, for once (Marin).

**Complications allowed**
- By plan: the bank, Margaux's refusal, or the glasses.
- Camille takes Grand-père home for Christmas, so the camp bed is empty.

**Must NOT happen yet**
- Margaux's «fatiguée» (T7 Day B).
- Gus's confession about his mother (T7 Day A, co-op).
- The kiss.
- The flat decision.
- The letter.

**Example premises**
1. **«Deux croissants».** Christmas morning: a paper bag at Odile's door with two croissants in it. You go up to thank Marchand and find the office empty, the camp bed stripped. Camille took him home. You leave something in return, and choose what. *The change:* the Sunday ritual has passed to you, whatever happens in T8.
2. **«Le cadeau».** A present exchange with Lila on Christmas Eve, colored by the path. *The turn:* say what the present means. *The change:* an object passes between you, and it will be in T8's platform panel.
3. **Plan-specific.**
   - «Cent cinquante» (`coop`): canvass the quartier with Marin, and Mme Diallo signs.
   - «Margaux ne répond pas» (`lease`): carry Marchand's note down the stairs.
   - «Les verres» (`last_service`): Margaux gives each regular one glass, and you get Odile's.

---

## Gap 7 · Days 53–57 (2–6 January) · «La dernière semaine»

**Threads that may advance, and how far**
- **The decision is carried out:** papers, the notary, the co-op, or Solvel.
- **Lila packs.**
- **«Last times».**
- **Romy's piece.**
- **Camille:** one argument about the paperwork.

**Small moments available**
- The last bread with Lila at Mme Diallo's, which bookends gap 1. The baker asks «Et demain ?», and Lila says «Demain, je suis à Berlin» (Lila).
- Lila giving her plants to Marin (Lila, Marin).
- Margaux teaching you the coffee machine (Margaux).
- Gus measuring the booth, for reasons he won't give (Gus).
- Marchand visiting his new residence with Camille (Marchand).

**Complications allowed**
- Paperwork.
- A freight delay.
- Snow warnings for the 8th, which come to nothing.

**Must NOT happen yet**
- Finding the letter (T8).
- Reading the back of the painting.
- Reversing the flat decision.
- Lila staying.

**Example premises**
1. **«La dernière tradition».** The last bread with Lila. She asks you to keep going to Mme Diallo's, «pour moi». *The change:* the ritual is inherited.
2. **«La machine».** Margaux teaches you to make your own usual on the machine nobody touches. *The change:* you can serve yourself at Le Mistral. In `sell`, she teaches you anyway: «pour ailleurs».
3. **«Ce qu'on donne».** Lila gives away her things and gives you one:
   - romance: the ochre scarf;
   - friendship: her terrible cactus.

   *The change:* something of hers stays.

---

## The romance and friendship gates in generated days

Gates 2 and 3 (bible §7) live in gaps 2 and 4.

- **What counts.** The director must include the gate's moment, and the classifier reads only what the learner *expresses*.
- **When the learner doesn't take it.** Nothing is lost. The gate simply stays open, and a later small moment can still register it. Never generate a second «chance» the same day.
- **Never show the path.** No hearts, no meters, no «Lila s'en souviendra» on romance moments. That label is only for the tentpole *choices*.
