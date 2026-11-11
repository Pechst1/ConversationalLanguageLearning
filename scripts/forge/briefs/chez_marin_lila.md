# Chez Marin et Lila: the flat on the third floor, the night the crate stands in the hallway

The next place the season's pages are set in that the world had not built (`forge.py queue
--season --from api` on 11 Nov: learners on g3 and g4, `next: marin_lila_flat`, first needed at
t5.b). It is Marin and Lila's flat, built in the state of its fullest scene: T5, «Tu le
découvres» without the key, the night of Sunday 13 December. Marin is in Finistère, you come by
to give back the casserole dish, and the crate for Berlin is standing in the hallway. The place
stays `locked` in `world.json` (`chez_marin_lila`, `stages: ["marin_lila_flat"]`, in the quai,
no pin of its own): the story opens it, and `stages.json` now lets a generated page be set there.

## What the canon gives

- **The places file** (`docs/story/season-1/10-lieux-et-images.md`, Other places): «Marin and
  Lila's flat (canon). The co-op folder on the fridge, held by a sardine-shaped magnet.»
- **The bible** (`00-season-bible.md`, Lila): «Marin's flatmate and oldest friend.»
- **T5 A · R1 and R2** (`05-berlin.md`): the canal at one in the morning, «at the foot of her
  building»; «From the street, you watch the third-floor window light up.» «The door opens.
  Marin in his socks, delighted to see both of you, holding up the co-op folder like a trophy.»
- **T5, B without the key · P2**: «Marin and Lila's flat, empty of people: Marin is in Finistère
  for the weekend. The space is full of Lila: an easel, a canvas half-wrapped in bubble wrap,
  and a wooden crate standing in the hallway. On the fridge, Toi's drawing from the dinner,
  still there.» **P3**: «Close on the crate, standing in the hallway. The stencil is legible:
  FRAGILE · BERLIN · KÜNSTLERHAUS AM KANAL.» **P4**: «On the fridge, under a magnet shaped like
  a sardine, a card in Lila's quick handwriting, addressed to Toi, with its last line
  unfinished.» The card's A2 text is quoted in the scene, and the room writes it as it is.
- **The end note**: «The crate stands in the hallway, and the card is on the fridge under a
  magnet shaped like a sardine. […] your drawing still on their fridge from the dinner.»
- **Gap 2 / T5 A** (the disastrous dinner): an omelette, the smoke alarm, Lila laughing on the
  floor.

The forge's own choices, not canon:
- **Where the flat is.** A building on the quai de Valmy, its third floor at 11.2 m, the
  séjour's two French windows on the canal (`canals`, the quai's own plan), a little down the
  quai from Le Mistral (the map entry's lat/lon is approximate: the room is never a pin).
- **The plan.** A hallway with the landing's door and the crate, and through a framed opening
  the séjour with the kitchen along the north wall.
- **The fridge.** Canon puts two things under the sardine: the folder (the places file) and the
  card (T5 B). The sardine holds the card, as the scene needs; the folder «LE MISTRAL À NOUS» is
  held by a plain red magnet beside it.
- **Toi's drawing.** The canon does not say what it shows. It is a pan, an omelette, three curls
  of smoke and the alarm shouting «BIIIP»: the dinner, and nobody's face.
- **The canvas** leans face to the wall, so the portrait (Toi from behind, «never a face») is
  never shown: its stretcher's back, and bubble wrap taped round its lower half. The easel
  stands empty, a little paint dried on its ledge.
- **The clock** says 1:40. The table, two chairs, a celadon armchair and a coat by the door are
  furniture any flat has.

No open street photo shows an interior, so there is no survey: the canon is the reference.

## The kit

Three new things in `room.ts` (and in `scripts/forge/room.py`'s list):
- `fridge`: a tall fridge, freezer drawer below, the handle up its side. On its door, under
  magnets: a folder (`text[0]`, its label, `''` for none), a card in a quick hand held by a
  sardine (the rest of `text`, one line a paragraph, wrapped to the card; an unfinished line
  stays unfinished), and a felt-tip drawing.
- `crate`: a painting's shipping crate on its edge against a wall: plywood, battens, screws,
  skids, its stencil on the face (`text`, the first line in red).
- `canvas`: a canvas leaning on the wall, face to it, the stretcher's back and its brace, bubble
  wrap round its lower half with the tape across it and its loose end, the roll of tape on the
  floor.
- `easel` with `size` `[0, 0]`: the easel with nothing on it.

And one fix to the review tool: `forge-view`'s close view of a thing with text started inside a
deep thing's block (a fridge is 62 cm deep, the view began 45 cm out); it now starts where the
block ends.

And one fix to the standalone page: since the one language resolver (#657) the quarter reads
the learner's language through the app's API client, which reads `process.env`; a page on its
own has no `process`, so `build-standalone.mjs` gives it an empty one and the client falls back
to its defaults.

## How it plays

You arrive in the hallway, the landing's door behind you and the crate in front of you, lit
(a flat has no switch). Marks: `porte`, `caisse` (in front of the crate), `frigo`, `toile`,
`fenetre`. Things you tap: the crate, the fridge (the card, and your drawing beside it), the
empty easel, the wrapped canvas. The end card remembers each.

## Rounds

1. The fridge was the walls' cream and read as part of the wall; the bubble wrap's bubbles were
   balls with ink outlines and read as a pegboard; the fridge's close view looked from inside
   the fridge (the review tool, above).
2. The fridge went whiter and a little cool; the bubbles smaller; an armchair and a coat made
   the flat lived in. The close view now shows the fridge, the kitchen beside it, the folder,
   the card and the drawing.
3. The bubbles became a printed sheet on a fat block of wrap, with its tape and loose end, which
   reads as a wrapped canvas from across the room. The easel moved off the south-east corner so
   you can walk up to it.

## Played

`?place=chez_marin_lila&debug` on the standalone page: the caption «Chez Marin et Lila, au
troisième. Marin est dans le Finistère. Dans l'entrée, une caisse.», the room lit, the crate,
the fridge, the easel and the canvas each tapped and read, the end card with all four, no
errors.

## Still plain

- The card is legible only close up (it is a postcard on a fridge): the tap says what it is.
- The bubble wrap's bubbles are printed, not modelled: from across the room it reads as wrap,
  close up as a print.
- The opposite quai through the windows is the quai's generic façades, not surveyed for this
  stretch.
