# La poêle brûlée d'Odile: her frying pan soaking in the sink, a tea towel over the tap

`forge.py queue --season --from api` on 18 Nov put the learners on g4 and g5 and printed `next:
none`, so the run takes the next thing the learners' own pages left, from `queue --orders`: «la
poêle brûlée d'Odile» at `odile_flat` (one life). The order says: «Odile's old frying pan,
blackened inside, left to soak in the sink under the window with a tea towel hung over the
tap.» It waits on that mark: a learner sees it only once a page of their own left it there.

## What the canon gives

- **Odile's flat** (`10-lieux-et-images.md`): two rooms on the first floor above the café, the
  kitchen with its gas stove, the whiter patch over it, the window on the canal. «A room that
  waited, not a room that rotted»: no mess, no decay.
- Nothing in the canon about a frying pan. The page that left it is the learner's own.

## The forge's own choices, not canon

- **The sink.** Odile's kitchen had a stove, a table and a calendar, but no sink. A sink that
  appeared only when a page left a pan in it would be odd, so the room gains its sink for good,
  in the flat and in the stairwell's view into the same kitchen (the two files hold the same
  things in the same places, and a new test now says so). It is an old one: a white glazed
  stoneware basin on a pale green painted cupboard, a wooden draining board, the plug on its
  chain, a brass tap out of the wall with its cross handle.
- **«Under the window».** The kitchen's only window is a French window down to the floor, with
  its guard, so nothing stands under it. The sink stands against the same east wall, just south of
  it, in its light: between the calendar and the corner, beside the stove.
- **The pan.** Black steel, its inside burnt black with a crust round the inside wall where it
  caught. It lies on the basin's floor full of water gone dark over the burnt bottom, a little foam
  of washing-up liquid on one side, the wooden handle up on the front rim.
- **The tea towel.** Linen with two red stripes near the hem, folded in three and hung over the
  tap's arm, one half longer than the other.

## The kit

New in `room.ts` and in `scripts/forge/room.py`'s list:

- `sink`: the old sink above (`size` [width]). The basin's inside is at local x -w/2 + 0.3,
  z 0.26, floor 0.86 m, 0.46 by 0.36. The tap's arm runs from the wall to z 0.2 at 1.18 m.
- `soak`: a frying pan soaking in a basin (`at` the basin's floor at its centre, `size` the
  basin's inside).
- `towel`: a tea towel over a bar (`at` the top of the fold, the bar along local z, `size`
  [width, drop]).

## Rounds

1. The sink sat well beside the window and the towel read from the door. But the grey water
   filled the whole basin over the pan, so its black inside did not show, and the foam on it read
   as crumbs.
2. The basin is dry now. The pan holds the water itself, dark over its burnt bottom, inside a ring
   of black crust, with the foam gathered on one side. On the phone it reads as a burnt pan left to
   soak.
3. The water a shade darker.

## Seen

On the standalone page (`?place=odile_flat&detail=poele_odile&debug`) at 900×600 and 390×844:
from the door on arrival the sink stands right of the window with the towel on its tap. From the
table and close up you see the pan, its crust, the dark water and the foam. No errors.

## Still plain

- **Not tappable.** A detail is laid, not tapped, in the kit as it is.
- **The water is still.** It does not move or catch the canal's light.
- **The stairwell's kitchen** gains the sink, but never the pan: a detail is laid in the room it
  names, and the stairwell only looks in through the door.
