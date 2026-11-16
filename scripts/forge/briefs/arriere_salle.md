# L'arrière-salle: Le Mistral's back room, after closing

The next place the season's pages are set in that the world had not built (`forge.py queue
--season --from api` on 10 Nov: learners on g3 and g4, `next: mistral_back_room`, first needed
at t5.b). It is the room behind Le Mistral's back door, where Lila keeps her portrait under a
sheet, built in its T5 state: the night of 14 December, after closing. The place stays `locked`
in `world.json` (`arriere_salle`, `stages: ["mistral_back_room"]`, in the quai, no pin of its
own): the story opens it, and `stages.json` now lets a generated page be set there.

## What the canon gives

- **The places file** (`docs/story/season-1/10-lieux-et-images.md`, Le Mistral): «The back
  room. It was rebuilt after the 2023 fire: new plaster that is a slightly different white, the
  café's electrical board, stacked crates, and an easel under a sheet (Lila's portrait, from
  gap 4).»
- **The bible** (`00-season-bible.md`): at 1:30, embers in the old shared duct «set fire to the
  café's back room, where the electrical board is».
- **T5 A · P7b** (`05-berlin.md`): «Lila […] walks round the end of the zinc, past you, to the
  door of the back room. She stops with her hand on the handle.» The caption: «Dans
  l'arrière-salle, sous un drap, Lila cache quelque chose depuis des mois.»
- **T5 B · P8**: «The back room of Le Mistral, rebuilt after the fire, with new plaster and a
  slightly different white. Under a sheet on an easel is Lila's group portrait, which Margaux
  lets her keep here.» **P9**: «She stands in the doorway of the back room, coat now on, looking
  at the plan pinned by the door, Marin's plan, with its square labelled «ATELIER DE LILA».»
- **T3** (`03-deux-promesses.md`, P3): Marin's plan has «long tables at the front marked
  «cantine le midi», the booth moved to the back, and the back room marked «ATELIER»»; the
  co-op is «Le Mistral à nous».

The forge's own choices, not canon: where the room is (behind the café's back door, which
`mistral.ts` draws at the far end of the zinc: the room is 6 m by 5.75 m west of the café's back
wall, the stairwell's corridor to the north of it), the stone floor, the ceiling at the café's
height, the old cream plaster on the café's side and the new white on the walls the fire took
(the north and west walls, with the board), a single globe, no window (the room is inside the
block), the crates' number and places, a kitchen chair by the easel, and the plan as Marin would
draw it: «LE MISTRAL À NOUS» at its head, the room with its long tables («CANTINE LE MIDI»), the
booth («BANQUETTE») and the zinc («ZINC»), and the back room's square, «ATELIER DE LILA», not yet
coloured in (that is the folder's copy, in Marin's hands, at the end of the night). The portrait is
not drawn: the sheet stays on, the uncovering is the stage's. No photos: no open photograph shows
this room, which the canon invents.

## The kit

New things in `room.ts` (and `room.py`): `easel` (a painter's easel leaning back, its canvas
under a white sheet in folds, the mast up out of it), `crates` (wooden crates stacked against a
wall, bottles' necks in the top row), `board` (the electrical board: a pale cabinet, the
breakers behind a smoked window, the meter, the trunking up to the ceiling) and `plan` (a plan
drawn by hand in felt-tip capitals, pinned at its corners). The new plaster is the kit's `patch`,
wall-sized.

## How it plays

You arrive just inside the door from the café, the easel in front of you: «L'arrière-salle du
Mistral, après la fermeture. Un chevalet, sous un drap.» Tap the easel («Un chevalet, sous un
drap blanc. On ne voit pas la toile.»), Marin's plan by the door («Ici, un carré : «ATELIER DE
LILA».»), the board («Le tableau électrique du café. Il est neuf, comme le plâtre.») and the new
plaster («Le plâtre est neuf ici, d'un blanc un peu différent.»). «Rentrer» and the end card
lists what you looked at. Nobody is there: Lila is the stage's.

## Round 1 (r1, 844×844, load 0.2 s, 8k triangles)

- **What reads.** The easel under its sheet from the door, the café's green door, Marin's plan
  with every label legible from a step away («ATELIER DE LILA» in its square).
- **The new plaster** did not read as a different white: it covered whole walls, so there was
  no edge to see. **The tomettes** were loud orange under the warm globe, a flat's floor, not a
  back room's. **The sheet** read as a striped curtain (its folds alternated two tones too far
  apart). The board and the crates were in no view.

## Round 2 (r2)

The floor is stone; the new plaster stops short of the south wall and of the door's corner, so
the seam shows behind the easel and beside the door; the folds are a breath apart in tone. The
board was still in no view (the marks' order put it out of every look).

## Round 3 (r3)

The marks now walk from the door to the easel, to the board, back to where you stand and to the
plan: the board reads (its breakers, its meter, the trunking up the new plaster), the crates by
the south wall, and the seam of the new white beside the door.

## Played (the standalone page, 390×844, `?place=arriere_salle&debug`)

The cover, the arrival and its caption, a tap on the easel, the plan, the board and the new
plaster, each line as written, «Rentrer», the end card with the four things. No errors; about 9k
triangles in the frame.

## Still plain

- **Nobody is there**: no Lila pulling the sheet off. The stage places people.
- **The portrait** is never drawn: the sheet stays on. Its uncovering, the booth, Odile at the
  zinc and the figure from behind are the page's panel (P8), not the room's.
- **The door to the café** stays shut: the café beyond it is the quai's own room, which a room of
  the season does not build. «Rentrer» takes you back to the quai.
- **No duct**: the old shared ventilation duct the fire came down by is not drawn.
