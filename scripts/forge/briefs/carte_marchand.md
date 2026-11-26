# La réponse de M. Marchand: «J'y serai. M.» against the till

On 26 Nov `forge.py queue --season --from api` put the learners on g4 and g6 and printed `next:
none`, and `queue --orders` printed `next detail: none` (every order is laid). So the run takes
the plan's ladder: the next line that leaves a thing in Le Mistral and waits on a season flag.

## What the canon gives

- **The card.** Gap 3 (`09-entre-les-episodes.md`): «Marchand's reply, if invited: a card, «J'y
  serai. M.»». Day 22 «Les canapés»: «If Marchand was invited, his reply card: «J'y serai. M.»».
  A small moment: «Marchand's handwriting on the reply card».
- **The flag.** `s1.marchand_invited` (bool), set in T3 B (Convaincre Gus), read in T4 B and T6 A.
  In T4 P4 Marchand stands in the doorway, coat buttoned, a bottle in paper (variant).
- **The till** at the zinc's far end, the old photograph of the bar tucked behind it
  (`mistral.ts`); in T4 R3 «margaux», what Margaux keeps goes to the till.

## The forge's own choices, not canon

- **Where.** The canon does not say where the card ends up. It is propped against the till's
  front, where whoever rings up sees it: the café keeps it, as it keeps the old photograph behind
  the till. It faces the room, so a learner at the zinc reads it.
- **The card.** A white correspondence card, 14 by 9 cm, a thin grey rule round it, the words in a
  neat upright hand in blue-black ink, «M.» lower right with a short stroke under it.
- **When.** Only once the learner's story set `s1.marchand_invited` true: a learner who did not
  have him invited never sees it.

## The kit

- `replycard`, new in `room.ts` and `scripts/forge/room.py`'s list: a card stood on its edge,
  leaned back 0.22 rad against what is behind it, its art `replyCardArt()`.
- `TILL` is exported from `mistral.ts` (the till's place: unchanged, only named).

## Rounds

1. The card stood against the till's front and read close up, «J'y serai.» and the signature. But
   from the zinc the words were small for the card.
2. The words larger and bolder, the signature a little smaller under them: «J'y serai. M.» reads
   from a stool's distance.

## Seen

On the standalone page (`?detail=carte_marchand&debug`) at 900×600 and 390×844: from the room a
white card at the till; from the zinc and close up, «J'y serai.» and «M.». No errors.

## Still plain

- **Not tappable.** A detail is laid, not tapped, in the kit as it is.
- **The bottle in paper** he holds in T4 P4 is not laid: the card is the trace the gap gives.
