# La tuque de Romy: a blue knitted tuque beside the closed blue folder on the back table

`forge.py queue --season --from api` on 20 Nov put the learners on g4 and g5 and printed `next:
none`, so the run takes the next thing the learners' own pages left, from `queue --orders`: «La
tuque de Romy» at `le_mistral` (one life). The order says: «A blue knitted tuque rests beside
the closed blue folder on the back table.» It waits on that mark: a learner sees it only once a
page of their own left it there.

## What the canon gives

- **Romy** (`00-season-bible.md`): the Québécoise journalist, your friend. In T6 B P3 she «comes
  in with her camera bag and a tuque» (`06-lautre-cote.md`). The canon gives no colour; the
  order gives blue.
- **The blue folder** (`09-entre-les-episodes.md`, day 30; `gaps.json`): «un dossier bleu», Marin's,
  with the plan inside. The order says «the closed blue folder», so it lies on the table with the
  tuque: it is part of what the page left.
- **Le Mistral** (`10-lieux-et-images.md`): the ox-blood booth at the back, and in front of it
  two marble tables. «The back table» is the left one, where Marin's bowl of soup already stands.

## The forge's own choices, not canon

- **Which table.** The left back table, on the half away from Marin's bowl: the folder in the
  middle, turned along the table's depth, and the tuque at the table's left end beside it.
- **The tuque.** Deep blue wool, put down crown up so it reads as a hat from across the room: a
  turned-up cuff ribbed in a darker blue, a cream band knitted round the crown, the crown soft and
  leaning to one side, a fat cream pompom. A Québécois tuque, not a beret.
- **The folder.** A school card folder in blue, closed, with its papers' edge showing at the open
  side and the two corner elastics. No label: the order does not say what is in it.

## The kit

- `tuque`, new in `room.ts` and in `scripts/forge/room.py`'s list (`at` its foot, `size` [the
  cuff's radius]).
- `folder` takes a `tone` now (the new `dossier` tone, also in `room.py`); a toned folder shows its
  papers and elastics, and a folder with no `text` has no label. The existing buff folders are
  unchanged.
- `mistral.ts` exports `BACK_TABLES` (the two tables' centres, size, height, and Marin's bowl), and
  draws the tables and the bowl from it: the same numbers, the same room.

## Rounds

1. The tuque read as a blue bell with a grey knob, and the folder as a grey slate.
2. The tuque is taller, with ribs on the cuff, a cream band and a cream pompom; the folder is a
   clearer blue with its elastics. It reads as a hat and a folder now, but the wool was nearly
   navy and the pompom faceted.
3. The wool a shade lighter, the ribs finer, the pompom rounder.

## Seen

On the standalone page (`?detail=tuque_romy&debug`) at 900×600 and 390×844: from the zinc the
tuque and the folder read on the back table, left of the bowl; close up you see the rib, the band,
the pompom and the folder's elastics. From the door they are small, as a hat on a table at the
back of a café is. No errors.

## Still plain

- **Not tappable.** A detail is laid, not tapped, in the kit as it is.
- **No camera bag.** The canon gives Romy a camera bag too; the order names only the tuque and the
  folder, so nothing else is laid.
