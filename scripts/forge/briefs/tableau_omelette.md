# Le tableau de l'omelette de Lila: against the bottles behind the zinc

On 27 Nov `forge.py queue --season --from api` put the learners on g4 and g6 and printed `next:
none`. `queue --orders` printed a new order, so the run lays it: `next detail: «le tableau de
l'omelette de Lila» in quai_de_valmy (mark: le_mistral)`, one life, its look «A small painting of
the omelette with its smoke, propped against the bottles behind the zinc, Odile's name on the
back.»

## What the canon gives

- **The omelette.** A generated day after T2, «Le dîner raté» (`gaps.json`, `t5.json`): the
  learner and Lila improvise dinner in Odile's kitchen, the omelette burns, the smoke alarm
  screams, Margaux runs up with the café's extinguisher and goes back down without a word. The
  private joke: «ne refais jamais l'omelette».
- **The painting.** Gap 6's small moment `cadeau_de_lila`: on the friendship path Lila's present
  to the learner is «a painting of the omelette, smoke and all».
- **Behind the zinc** (`mistral.ts`, `10-lieux-et-images.md`): the long mirror, two shelves of
  bottles on it, «L.»'s small oil above it. «L.»'s painting is never discussed and nobody reads
  its back (`gaps.json`, `painter_named`, `painting_back`).

## The forge's own choices, not canon

- **Where.** «Against the bottles behind the zinc»: on the lower shelf, about a metre and a half
  along from the zinc's north end, clear of the coffee machine, leaned back so its top rests on
  the bottles. Bottles rise behind and beside it; the upper shelf is clear over it.
- **The painting.** 40 by 32 cm, a canvas on its stretcher with no frame (Lila's, not a gilt-framed
  oil like «L.»'s). Quick thick strokes in her classroom colours: a warm yellow kitchen wall,
  blue tiles over the cooker, the dark cooker top and the ring's flame, the black pan from a
  little above with the omelette yellow at its edge and black where it caught, and a column of
  grey smoke climbing out of it to the top of the canvas.
- **The back.** Odile's name is on the back, as the order says, and the back faces the bottles:
  it is not drawn. Nothing is written on its face either, no signature: a mark in a corner could
  be taken for «L.»'s.

## The kit

- `oilsketch`, new in `room.ts` and `scripts/forge/room.py`'s list: the canvas leaned back
  0.14 rad on a 1.8 cm stretcher, its art `omeletteArt()` (seeded, so the same each time).
- `SHELVES` is exported from `mistral.ts`: the bottles' axis, the shelves' depth and heights, a
  bottle's radius and the coffee machine's place along the zinc. The geometry is unchanged, only
  named.

## Rounds

1. 30 by 24 cm: it sat on the shelf among the bottles and read close up, but from the zinc it was
   a yellow smudge, the smoke a thin grey thread and the tiles a neat grid.
2. 40 by 32 cm, the smoke a full cloud, the tiles brushed over. But the light curved strokes in
   the smoke read like letters.
3. The strokes in the smoke long and soft along the curl, a shade off the grey: a column of smoke
   rising from the burnt omelette, readable from the zinc and on a phone.

## Seen

On the standalone page (`?detail=tableau_omelette&debug`) at 900×600 from the zinc, close up and
from the side (it leans on the bottles, its foot on the shelf), and at 390×844. No errors.

## Still plain

- **Not tappable.** A detail is laid, not tapped, in the kit as it is.
- **The back** with Odile's name is not drawn: it faces the bottles.
