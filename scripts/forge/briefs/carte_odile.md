# La carte bleue d'Odile: her bank card beside the lease letter on the zinc

`forge.py queue --season --from api` on 21 Nov put the learners on g4 and g5 and printed `next:
none`, so the run takes the next thing the learners' own pages left, from `queue --orders`: «La
carte bleue d'Odile» at `le_mistral` (one life). The order says: «A small blue card rests beside
the lease letter on the café counter.» It waits on that mark: a learner sees it only once a page
of their own left it there.

## What the canon gives

- **Odile Ferrand** appears in Polaroids and flashbacks only, and never speaks. Her things stay
  where the story puts them, handled with care.
- **The lease letter** (`06-lautre-cote.md`, `09-entre-les-episodes.md` day 35,
  `10-lieux-et-images.md`): Margaux's recorded letter, «fin du bail le 31 mars», with the
  green-and-white *recommandé* slip. Marchand writes in recorded letters; his B1 line «Je vous
  rappelle que le bail expire le 31 mars» (`00-season-bible.md`).
- **The café counter** is Le Mistral's zinc.

## The forge's own choices, not canon

- **«Carte bleue».** In French that is a bank card, so it is one: plain blue, a gold chip, the
  number as dots with no digits, «ODILE FERRAND» in raised capitals. No bank's name or logo.
- **The letter.** Opened and laid flat with its two creases: «GÉRANCE MARCHAND» at the head,
  «Objet : fin du bail», «Madame, Je vous rappelle que le bail expire le 31 mars.», signed «M.».
  Its envelope sticks out from under it with the green-and-white «RECOMMANDÉ AR» slip.
- **Where on the zinc.** Between where the key lies (and your usual cup) and Odile's stool at the
  far end, the sheet's head away from you so it reads from where you stand; the card beside it, on
  your side.

## The kit

- `recommande` and `carte`, new in `room.ts` and in `scripts/forge/room.py`'s list.
- `mistral.ts` exports `ZINC` (its front, its ends, its back and its top's height) and builds the
  zinc from it, with the same numbers. The test reads the zinc from there.

## Rounds

1. The card read as a small blue card with its chip, and the letter as a letter. But the envelope
   hid under the sheet, so the green slip did not show.
2. The envelope turned out from under the sheet's head: the green-and-white slip shows.
3. The letter's subject and body a size larger: close up, «fin du bail» and «le 31 mars» read.

## Seen

On the standalone page (`?detail=carte_odile&debug`) at 900×600 and 390×844: from the zinc, the
letter and the card read on the counter; close up and from above, the letterhead, the subject,
the date, the slip and the name on the card read. From the door they are small, as papers on a
counter are. No errors.

## Still plain

- **Not tappable.** A detail is laid, not tapped, in the kit as it is.
- **The letter does not change** with the story: it says 31 March whatever Marchand decides later.
