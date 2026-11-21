# La banderole de Lila, qui sèche: a cloth banner pegged over two chairs in Marin and Lila's flat

`forge.py queue --season --from api` on 17 Nov put the learners on g4 and g5 and printed `next:
none`: every place the season's pages are set in is built or waits for a kit. So the run takes the
next thing the learners' own pages left, from `queue --orders`: «la banderole de Lila» at
`marin_lila_flat` (one life). The order says: «A long cloth banner reading «Les 25 ans du
Mistral», freshly cut shorter, drying across two chairs in the cramped living room.» The same
name at Le Mistral is the rolled paper banner (`banderole_lila`, built 16 Nov). This one waits on
the mark at the flat, so a learner sees it only once a page of their own left it there.

## What the canon gives

- **T4, the party** (`10-lieux-et-images.md`, `04-la-photographie.md` P1): Lila paints the
  banner for Le Mistral's 25 years. The canon's own words on it are «LE MISTRAL · 25 ANS · ON
  RESTE». The page that left this one wrote «Les 25 ans du Mistral», and the detail is that page's.
- **T5, B without the key, P2** (`05-berlin.md`): the flat «full of Lila».

## The forge's own choices, not canon

- **Where.** The séjour's south-east corner, between the wrapped canvas and the window wall. Two
  chairs are pulled out side by side, their backs to the room, 1.3 m apart. That corner is the
  only free floor in the room: the canvas, the easel, the table and its chairs, the armchair and
  the kitchen take the rest.
- **How it hangs.** The banner's top hem is folded over the two top rails and pegged with two
  wooden clothes pegs to each chair. Its painted face hangs toward the room, 56 cm deep, with the
  chair legs showing under it.
- **Freshly cut shorter.** The end by the canvas is cut straight, without a hem, its threads
  loose. The offcut lies crumpled on the floor in front, with a stroke of red paint across it and
  the scissors open beside it. The far end keeps its hem.
- **The words.** «LES 25 ANS DU MISTRAL» in red capitals with a cobalt shadow, each letter a
  little off its line, the paint run under a few. They reach close to the cut, so it was cut to
  the words.

## The kit

`drape` is new in `room.ts` and in `scripts/forge/room.py`'s list. It is a cloth banner pegged
over two chair backs: `at` is the middle of the span on the floor, `size` is [length, drop] and
`text` is the words. The painted face is a card (the cloth itself, with its folds, its hem and its
cut drawn on). The hem over the rails, the flap behind, the pegs, the threads, the offcut and the
scissors are geometry. It blocks the walk under the chairs only, so the offcut stays walkable.
The chairs are the kit's own `chair`s, listed in the detail.

## Rounds

1. The banner was built in strips that sagged between the chairs. The strips stepped like
   cardboard, and the printed words sat on a lighter card than the cloth round them. The offcut
   was a plank.
2. The painted face is the whole front panel now, hung straight and held by the pegs, so cloth and
   words are one surface. The folds are soft bands in the art, the hem is stitched, the cut frays.
   The offcut is three thin folds of cloth.
3. The details test found the walk block reaching into the canvas's own block. The block now
   covers only the chairs under the cloth. The chairs moved 2 cm out to sit under the pegs.

## Seen

On the standalone page (`?place=chez_marin_lila&detail=banderole_lila_seche&debug`) at 900×600
and at 390×844: from the séjour's threshold the words read across the room, beside the window.
From the table you read it whole, and close up you see the cut and the scissors. No errors.

## Still plain

- **Not tappable.** A detail is laid, not tapped, in the kit as it is.
- **It does not sag.** A pegged hem hangs straight here; a real cloth would droop between the
  chairs.
- **Only once the story left it.** A learner whose pages did not leave the banner in the flat
  never sees it.
