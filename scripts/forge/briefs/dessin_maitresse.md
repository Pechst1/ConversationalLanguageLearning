# Le dessin « Maîtresse à Berlin »: a pupil's drawing beside Odile's Polaroid

`forge.py queue --season --from api` on 23 Nov put the learners on g4 and g5 and printed `next:
none`, so the run takes the next thing the learners' own pages left, from `queue --orders`: «le
dessin « Maîtresse à Berlin »» at `le_mistral` (one life). The order says: «A child's crayon
drawing with a date, pinned on the wall beside Odile's portrait.» It waits on that mark: a
learner sees it only once a page of their own left it there.

## What the canon gives

- **The drawings** (`09-entre-les-episodes.md`, day 38 «Le dernier jour d'école»): Lila's pupils'
  drawings, «Maîtresse à Berlin». «The leaving is real, and it is on a child's drawing.»
- **The date.** Lila's card on Marin's fridge: «Je pars le 8 janvier, à Berlin.»
- **Odile** appears in Polaroids and flashbacks only: a small upright woman in her seventies,
  short white hair cut straight, a moss-green cardigan, usually laughing at something outside the
  frame (`10-lieux-et-images.md`). On the party's wall each Polaroid has a small handwritten card
  beneath it.

## The forge's own choices, not canon

- **«Odile's portrait».** Le Mistral had no portrait of Odile on its walls, and the order speaks of
  it as there, so it is laid with the drawing: a Polaroid of Odile at the zinc, laughing at
  something out of the frame, pinned through its top border. It hangs just above where her name
  card (`carte_nom_odile`) is pinned, as the cards hang under the Polaroids on the party's wall.
- **The drawing.** Landscape on white paper, in crayon gone over two or three times:
  - the teacher with black curls and a yellow dress (Lila's colours), waving;
  - a blue and red train going off to the right with its smoke, a sun and a heart;
  - «MAÎTRESSE À BERLIN» in wobbly capitals across the top, and «8 janvier» in red in the corner.
- **Where.** On the north wall above the booth's back, between the old «Bal» poster and the
  corner, beside the Polaroid. Nothing overlaps the poster or the name card.

## The kit

- `drawing` and `snapshot`, new in `room.ts` and in `scripts/forge/room.py`'s list. A helper,
  `pinUp`, now pins every pinned thing (`pinned`, `drawing`, `snapshot`) the same way.

## Rounds

1. The drawing read: the words, the teacher, the train, the date. But the pin went through the
   Polaroid's picture, and Odile was too small in it to read as a woman with white hair.
2. The pin through the white border; Odile larger, filling the frame. Her white hair, the green
   cardigan and the laugh read close up.
3. The date written larger and in red, as a child dates a drawing.

## Seen

On the standalone page (`?detail=dessin_maitresse&debug`) at 900×600 and 390×844: from the zinc
and the door they are a small photo and a white sheet by the corner; from the booth's table and
close up, the drawing's words, the teacher, the train and the date read, and so does Odile
laughing. No errors.

## Still plain

- **Not tappable.** A detail is laid, not tapped, in the kit as it is.
- **One Polaroid, not the wall.** The rows of Polaroids above the booth are their own order («le
  mur d'Odile»).
