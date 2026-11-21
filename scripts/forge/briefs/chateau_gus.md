# Le « château » de Gus: the loft on the fifth floor, the night the painting faces the wall

This is the next place the season's pages are set in that the world had not built yet.
`forge.py queue --season --from api` on 14 Nov put the learners on t4 and t5. The gare de l'Est
still waits for its kit (`gare_de_lest.md`), and the rue de Lancry is built, so the next place
is `gus_loft`, first needed at t8.b. The room is built in the state of the first scene that
plays there: T8, «À suivre… (2)». The place stays `locked` in `world.json` (`chateau_gus`,
`stages: ["gus_loft"]`, in the quai, no pin of its own). The story opens it, and `stages.json`
now lets a generated page be set there.

## What the canon gives

- **The places file** (`docs/story/season-1/10-lieux-et-images.md`):
  - «Gus's loft (canon). In ending 2, the painting leans against the wall face-first, with the
    inscriptions facing the viewer.»
  - The painting «L.»: «A small oil in a gilt frame […] The back reads «Pour Odile, qui part.
    — L., 1970» in ink, and «Toujours rue de Lancry. — L., 2021» in pencil.» T8 A gives the
    pencil line as «in a shaky recent hand».
- **T8, À suivre… (2)** (`08-ce-quon-garde.md`): «Gus's «château», the loft, at night. The
  painting leans with its face to the wall, so the inscriptions face the reader. Gus is on the
  phone with his back to it.» Gus: «Maman ? … Tu connais un certain L. ? Rue de Lancry ?»
- **The epilogue** (`12-la-semaine-dapres.md`) comes back here three times:
  - Gus sits on the floor in front of the painting, phone in hand.
  - The Mistral's bench stands against the wall (laisser partir).
  - Gus turns the painting round (partager).
- **The bible**: Gus's «Au château» on Sundays; his fear is Créteil and his mother; «de
  Roncourt» was invented at fifteen.
- **T7**: «Gus's candelabra» on the Réveillon's table.
- **The project's own world bible** (`app/prompts/serial/world_bible_paris_v2.json`) is not
  season canon, but the forge follows it: «Aggressively styled bachelor loft Gus calls a
  château, glass table, dramatic lighting, overcurated objects, one detail revealing Créteil
  underneath.» The palette is «burgundy, ink, polished paper neutrals». Its plate
  (`gus_loft.webp`) has green walls, a red banner with arms, and a gilt mirror over a
  chimneypiece.

## The forge's own choices, not canon

- **Where it is.** The fifth floor of the Haussmann house on the quai between z 36 and 52.8,
  two houses south of Marin and Lila's. This is the façade the quai already draws (`row`, seed
  49). You come in by its own street door, bay 0, at z 51.38. The floor is at 17.1 m, the
  ceiling under the cornice, and the three French windows open on the fifth floor's balcony
  over the canal. The canon only says «Paris 10e». The map entry's lat/lon is approximate,
  because a room is never a pin.
- **The arms.** A crown over a chevron between three stars, red and gold. They are invented
  arms for an invented name, which is the joke.
- **The candelabrum** on the mantelpiece is the one from the Réveillon. Its three candles are
  lit, which is the «dramatic lighting».
- **The Créteil detail.** An envelope on the glass table, «Augustin» in a round hand, postmarked
  CRÉTEIL. It is the world bible's «one detail revealing Créteil underneath». No surname is
  given, because the canon gives none for his mother.
- **The letterbox** reads «5e · A. de Roncourt», the name he gives. The others are floor
  numbers only.
- **The stairwell** is Marin and Lila's plan (same cage, same celadon wainscot), moved to this
  house's door.

No open street photo shows an interior, so there is no survey: the canon is the reference.

## The kit

New in `room.ts` (and in `scripts/forge/room.py`'s lists):

- `canvas` with `text`: a small oil in its gilt frame, leaning face to the wall. You see the
  frame's back in wood with the gilt at its edge, then the stretcher and the linen. What is
  written there comes a line each: the first in ink, the rest in pencil, each letter a little
  off its line.
- `banner`: a banner on a gilt pole hung by its cord. The cloth is red and comes to a point,
  with a gold border, the arms and a tassel.
- `mantel`: a marble chimneypiece (green marble, tone `marble`). It has the jambs, the frieze,
  the shelf, the hearth slab and cold logs in a black firebox. Over it hangs a tall mirror in a
  gilt frame with its crest.
- `candelabra`: three candles, lit.
- `lowtable`: a glass top on a brass frame, with a decanter of something amber and two tumblers.
- `letter`: an envelope face up, with a name in a hand, a stamp and the postmark's ring with its
  town.
- `rug`: a red rug with a dark border, its stripes and a medallion.
- The tones `bottle` (the walls), `velvet` (the armchairs) and `marble`.

## How it plays

- **On foot:** you come from the quai through the street door, cross the tiled vestibule and
  climb to the first floor. A passage takes you on to the fifth-floor landing, then through
  Gus's door. The door stays shut until the story has played there: «Tu sonnes. Personne
  n'ouvre, pas encore.»
- **On arrival** (`?place=chateau_gus`): you stand inside the door, facing the painting between
  two windows, with the rug and the table in front of you and the mantelpiece on your left.
- **Marks:** `porte`, `tableau`, `cheminee`, `banniere`, `table`, `fenetre`, and in the stairwell
  `streetDoor`, `hall`, `foot`, `premier` and `palier5`.
- **Things you tap:** the back of the painting, the banner, the mantelpiece and the envelope.
  The end card remembers each.

## Rounds

1. The room was 9.7 m by 11.6 m with little in it. The boards read bright orange, and the
   painting was a speck in the far corner.
2. The room became 9.7 m by 9 m, with three windows. The floor is now the dark `parquet`, and a
   rug lies under the table. From the painting looking back, the room reads: the mirror over
   the mantelpiece, the candelabrum, the rug, the table and its decanter, the armchairs and the
   banner. The arrival still looked at an empty corner.
3. The painting moved to the pier between the two windows opposite the door. You now come in
   facing it, with the room between you and it, on a phone (390×844) too.

## Played

On the standalone page at 390×844 (`?place=chateau_gus&debug`):

- The caption: «Chez Gus, au cinquième. Il appelle ça son château. Contre le mur, un tableau
  retourné.»
- The mantelpiece, the banner, the back of the painting and the envelope were each tapped and
  read.
- The end card showed all four, with no errors.

`world-rules.test.js` walks from the quai through the street door and up to the loft.

## Still plain

- **Gus is not there.** He is on the phone with his back to the painting, and a room has no
  people yet.
- **Later states** are the stage's or a later run's: the Mistral's bench (E3, laisser partir) and
  the painting turned to face the room (E3, partager).
- **The climb.** The climb from the first to the fifth floor is a passage, not drawn.
- **The view.** The houses across the canal are the quai's generic façades.
- **The armchairs** are the kit's buttoned armchair in red, not a club armchair.
