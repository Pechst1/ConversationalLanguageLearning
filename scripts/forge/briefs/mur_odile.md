# Le mur d'Odile: her Polaroids above the booth, the burnt one alone in the gap

`forge.py queue --season --from api` on 25 Nov put the learners on g4 and t6 and printed `next:
none`, so the run takes the next thing the learners' own pages left, from `queue --orders`: «le
mur d'Odile» at `le_mistral` (one life). The order says: «Rows of Odile's Polaroids pinned on the
wall above the booth, with one photo at the very centre.» It waits on that mark: a learner sees
it only once a page of their own left it there.

## What the canon gives

- **The wall** (`04-la-photographie.md`, setting and P2): «sixty of them pinned above the booth.
  Lila copied the handwriting on the back of each one onto a small card.» Rows of Polaroids, each
  with Lila's small card under it. `mistral.ts` already says it: «in T4 this wall becomes the
  Polaroids».
- **The photo at the centre** (R3, the «wall» choice): «The burnt Polaroid is pinned alone in the
  middle of a gap, where Lila has moved the others aside to give it room.»
- **The burnt Polaroid** (P6): «A small kitchen at night. A pan on a gas ring, black smoke under
  the ceiling, orange light. Through the window, seen from above and from behind, so the letters
  read reversed, is the café's red neon sign: LARTSIM. On the white border, in a shaky hand: «14
  mars. 23 h. J'ai oublié. Encore.»»

## The forge's own choices, not canon

- **Which photo is at the centre.** The order's «one photo at the very centre» is read as R3's
  «wall» ending (`s1.fire_photo = wall`). A detail waits on its mark alone, so a learner whose
  page left the wall sees the burnt one there; the «margaux» ending (the photo in the till) is not
  told apart.
- **The two old posters stay.** A detail cannot take the room's posters down, so the wall fills
  the space between them: 15 across, 5 down, 63 photos round the gap, 64 with the burnt one.
- **The gap.** Three photos wide, from the row over the burnt one down to the bottom row. The
  booth's sconce hangs in its lower part, so no photo hides behind the lamp, and the burnt one
  sits just above the lamp's glow.
- **The pictures.** Small and drawn as geometry, not as cards (sixty textures would blow the sign
  atlas): a ground in one of six colours and in it a face and shoulders, two people side by side,
  a street under a pale sky, or a dog asleep. Each is pinned a little crooked; Lila's cards hang
  straight under them, one or two lines in her ochre hand. Only the burnt one is a drawn card.

## The kit

- `polaroidwall`, new in `room.ts` and `scripts/forge/room.py`'s list; `polaroidWall()` gives
  its layout (the tests use it). The burnt Polaroid's art is `burntArt()`: the orange kitchen, the
  smoke, the pan, «MISTRAL» mirrored in red in the window, the browned frame, the caption.

## Rounds

1. The rows read as a wall of photos with cards under them. But the sconce hung right in front of
   the burnt photo, and the little figures read as bottles.
2. The wall moved up a row and the gap runs down to the bottom row, so the lamp hangs in it;
   15 across instead of 13, for the canon's sixty. The figures became faces and shoulders, pairs,
   streets and a dog.
3. The burnt frame's edge lightened from near black to a browned ochre.

## Seen

On the standalone page (`?detail=mur_odile&debug`) at 900×600 and 390×844: from the door, a
block of small white frames between the two posters with a gap in the middle; from the booth,
the rows, the cards, and the orange photo alone in the gap over the lamp. No errors.

## Still plain

- **Not tappable.** A detail is laid, not tapped: the captions on Lila's cards are lines, not
  words, and the burnt one's caption reads only very close.
- **Both endings show the burnt one.** See above.
