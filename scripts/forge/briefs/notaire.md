# Chez le notaire: Maître Vasseur's office over the boulevard

The third room the forge writes from the canon: the notary's office, where the estate is
explained («Plusieurs semaines»), where the debt is explained («Chez le notaire»), and where, at
ten o'clock on 23 December, Marchand does or does not sign (T6 B). One room, 6.4 m by 5 m, on the
second floor of a stone house on a boulevard (floor at 7.9 m, the quarter's storey heights), two
French windows over the boulevard on the north, the double door from the waiting room on the
south. The place stays `locked` in `world.json`; the story opens it.

## What the canon gives

- **The places file** (`docs/story/season-1/10-lieux-et-images.md`): «The notary's office (Maître
  Vasseur). A polished table, a fountain pen, tall windows on a boulevard, the quartier visible on
  the pavement below (T6 B, public variant).»
- **The bible** (`00-season-bible.md`): «Maître Vasseur, the notary. Brisk and kind.» The notary
  calls the flat «modeste» and advises accepting the estate *à concurrence de l'actif net*.
- **Between the episodes** (`09-entre-les-episodes.md`): «Plusieurs semaines» (nothing can be sold
  for weeks; the ticket moves); «Chez le notaire»: «La dette peut prendre l'appartement. Pas
  plus.», with Camille in the waiting room; «The notary's office calls: Thursday, ten o'clock.»
- **T6 B** (`06-lautre-cote.md`): «10:00, at the notary's. Maître Vasseur; Bastien Roux in his good
  coat with the pen held out; Camille; Marchand. Marchand puts the pen down on the table without
  uncapping it.» In the public variant, the pavement under the window fills: Mme Diallo in her
  apron, Marin with a thermos, Gus with his placard. In the kept variant, Camille looks out of the
  window at the pavement below, where you stand in the cold.
- Marchand on the stairs: «La succession Ferrand.» The folder's label is that, and nothing more.

The forge's own choices, not canon: the plan and the floor, the walnut table and its five leather
armchairs (Maître Vasseur's with its back to the windows; T6 seats four and you), the bookcase of
law in bound volumes (no titles on the spines), the wainscot and its cream, the ceiling globe, the
boulevard itself (which one is not said: a stone boulevard of the quarter, 32 m façade to façade,
plane trees on both kerbs, shops with no names on them). It is morning: the scenes there are at
ten o'clock. The leaves are November's, the season of the first visit.

The map has no boulevard yet, so the office waits inside the quai on the map, like the stairwell
and the studio (no pin of its own); its coordinates are on the boulevard, west of the quai.

## How it plays

You come in by the waiting room's door, the light on and the morning in the windows: «Chez Maître
Vasseur, sur le boulevard. Il est dix heures.» Tap the folder («Sur le dossier : «Succession
Ferrand». Rien ne se vend avant plusieurs semaines.»), the fountain pen, or the bookcase. «Rentrer»
and the end card says what you read and looked at. Nobody is in the room yet: Maître Vasseur and
the others are the stage's. Maître Vasseur's gender is not in the canon, so no line needs one.

## Round 1 (r1, 844×844, load 0.28 s, 14k to 39k triangles, 8 views)

- **What reads.** The long table and its sheen, the armchairs in oxblood leather, the folder with
  «Succession Ferrand» legible, the pen beside it, the French windows with their iron guards, the
  stone houses across the boulevard with their balconies on the second and fifth floors.
- **The pavement below did not show.** A wall of plane-tree crowns stood in front of both windows:
  the tree on our own kerb. The boulevard now has a stretch of our kerb with no tree (`clear`), and
  round 1's brief had the room too narrow to walk round the table (the window's mark and the
  bookcase out of reach: `room.test.js` said so); it is 80 cm wider and 40 cm deeper.

## Round 2 (r2)

The `clear` stretch did nothing at first: the kit compared each kerb's line with the façade's, so
it never knew which kerb was ours. Fixed, a look straight down from the window shows our pavement,
the roadway with its dashes, the far pavement with its trees, a lamp, a bench, and the shop fronts
with their awnings. From where you stand, the windows give the façades, the crowns and, under them,
the shops and the street.

## Round 3 (r3, 390×844, the phone's frame)

Upright, the arrival had a chair's back filling the lower half and the window at the edge. The
start now looks at the west window: the boulevard in the middle of the screen, the table on the
right, the folder a turn away.

## Played (the standalone page, 390×844, `?place=notaire&debug`)

The cover, the arrival and its caption, a tap on the folder, the pen and the bookcase (turning to
each), each line as written, «Rentrer», the end card with the three things. No errors; about 33k
triangles with the boulevard.

## Still plain

- **Nobody is there**: no Maître Vasseur, no Camille in the waiting room. The stage places people.
- **The quartier on the pavement** (T6 public) is the stage's too: the pavement is there for them.
- **The boulevard has no name and no traffic**: no cars, no bus, nobody walking yet.
- **At night** the boulevard's lamps would not light the street: the room's light map covers the
  room only. The scenes there are by day.
- **The floor** is the kit's warm boards, not a herringbone parquet.
- **Photos.** None: no open photograph shows this office, which the canon invents; the canon is
  the reference.
