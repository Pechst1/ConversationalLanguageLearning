# La banderole de Lila: rolled up at the zinc's far end, by the booth

`forge.py queue --season --from api` on 16 Nov put the learners on g4 and g5 and said `next:
none`: every place the season's pages are set in is built, or waits for a kit (the gare de l'Est,
the brocante, the mairie). So the run took a detail. `queue --orders` named the first thing the
learners' own pages left: «la banderole de Lila» at `le_mistral` (one life), «A long painted paper
banner, rolled and tied with string, leaning behind the zinc next to the booth.» Its file is
`web-frontend/lib/quartier/world/details/banderole_lila.json`, the first detail that waits on a
mark the story left rather than a season flag.

## What the canon gives

- **The places file** (`docs/story/season-1/10-lieux-et-images.md`), Le Mistral at the T4 party:
  «Lila's hand-painted banner «LE MISTRAL · 25 ANS · ON RESTE» across the mirror.»
- **T4 P1** (`04-la-photographie.md`): the banner across the mirror; R1, after the party, it has
  half come unstuck.
- **T8 F1**: Gus paints his own for the Gare de l'Est «using Lila's T4 banner as a template».

The order puts the banner rolled up before it goes up (or after it came down), which the canon
allows: nothing in Le Mistral's «Never» forbids it.

## The forge's own choices, not canon

- **Where.** The order says «behind the zinc next to the booth». The zinc's far end, by the booth,
  is the spot that is both: the roll stands on the floor between the zinc's north end and the
  north wall (x -35.15, z -17.92) and leans on the end of the zinc, its top at the zinc's height.
  From the room and the booth you see it; from the duckboard it would be hidden.
- **The roll.** Paper, 1.3 m long, 6.5 cm across, two ties of twine with their knots. The paint
  shows at the ends and along the edge of the last turn (red, blue, yellow), not the words: it is
  rolled.

## The kit

- `roll` (`room.ts`, `scripts/forge/room.py`): a paper banner rolled and tied, standing on its end
  and leaning about 19° toward local +z (`size` [length, radius]).

## Rounds

1. The roll reads as a paper roll with its ties, at the zinc's end beside the booth. It was thin
   from the booth's table.
2. 6.5 cm across instead of 5.5. At 390×844 from by the booth it reads at a glance, with the
   paint at its ends.

## Looked at

The standalone page with `?detail=banderole_lila&debug`, the stage set to roam: from the door,
from by the booth, close up, and at 390×844. No errors. From the door, the people of T1 stand
between you and it.

## Still plain

- **Nobody sees it yet** unless their own story left it: the quarter lays it from the server's
  world-state (`setBy`), once a page of theirs left «la banderole de Lila» at Le Mistral.
- **No words on it.** It is rolled; the party's banner across the mirror is T4's own staging.
- **Lila's flat** has its own order of the same name (a cloth banner drying over two chairs): a
  later run's detail.
- **No tap.** A detail is laid, not tapped, in the kit as it is.
