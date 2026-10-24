# Le marché d'Aligre: the forge's notes

Forged for the Papier's evergreen «Le marché du dimanche à Aligre» (`evergreen-marche-du-dimanche`).
Data: Overture Maps, release 2026-10-21.0, 175 m around 48.849, 2.378. Renders in
`var/forge/marche_aligre/renders/<round>/` (not committed); `sheet.png` is what was looked at.

Each round: render (`web-frontend/scripts/quartier/forge-render.mjs`), look at the sheet, write
down what is wrong, change the brief or the kit, draft again. At most three rounds, then publish
or leave it `en_chantier` with the reason here.

## Round 1 (r1, 390×844, load 3.5 s, 349k triangles at the arrival)

Looked at: the arrival, the hall outside and in, the pavilion, the market street, a stall, the
brocante, the edge of the walkable world, a look from above.

- The rue d'Aligre reads at once: stalls under striped canvases, Haussmann fronts with their
  balconies, the street running to the hall. Good.
- The left side of the street looked missing. False alarm: the portrait frame crops it. Rendered
  again square (r1b, 844×844) to judge the layout, and kept the square frame from then on.
- The hall from the square: the name board «MARCHÉ BEAUVAU» reads, but the front is a flat
  timber frame and two low fences. No glazing, no lantern, nothing that says covered market.
- Inside the hall: an empty floor under a dark ceiling. No counters at all. The worst view.
- The pavilion (La Petite Mairie): a plank box with a door and a bench. Plain but right.
- A stall up close: crates with their heaps and a slate «Kakis 1 € pièce». Reads well.
- The brocante: things on a cloth, a vase, a slate «Tout à 2 €». Reads well.
- From above: washed out in the haze, the layout cannot be judged. Added an oblique view.

Changed: the hall gets glazing between the posts, a timber roof with its trusses, a lantern
along the ridge, and counters inside in islands with aisles between.

## Round 2 (r2, 844×844, load 4.2 s, 488k triangles at the arrival)

- The hall from the square now reads as Beauvau: glazing, roof, lantern, name board.
- Inside, the counters stop short: the middle of the hall is still an empty strip. The island
  rows broke off too early (the aisle test was 2.4 m where the middle aisle is 1.9 m).
- The frame got heavy: 729k triangles from above, 4.2 s to load. Too much for a phone.

Changed: the island rows run to an aisle along each end wall (break at 1.9 m), about 120 counters
in all. Buildings beyond the walkable radius + 10 m are drawn as flat fronts (windows, shops,
balcony slabs, a cornice) instead of full façades; trees out there lose their grates and twigs;
what is heaped in the crates is drawn only within 64 m.

## Round 3 (r3, 844×844, load 1.7 s, 412k triangles at the arrival)

- Inside the hall: aisles of counters under the timber roof and the lantern. Good.
- The street with the crowd in it reads like a market morning; the brocante square under its
  trees; the hoarding at the edge carries its «chantier» sign.
- About 15% fewer triangles at street level, 35% fewer from above, loads in under 2 s.
- Still plain: the pavilion; the crowd is thin at 24 people. The visit adds a stallholder behind
  one street stall in four and here and there under the hall, which fills it.

Published after this round.

## Play-through (after publishing)

Played from the quai: the map, «Y aller», the three stallholders, «Rentrer», home, and back
again. Found and fixed:

- A food stall only counted its front row of crates as what it sells, and with three cheeses the
  front row showed one. The fromagère, asked the price of «le chèvre», gave the comté's. Stalls
  now count both rows (the back row goes on where the front row stops), and a thing of the
  trade that is not on the stall today gets «Du chèvre ? Pas aujourd'hui, je n'en ai plus.»
- Money held out before the total was not taken (the lamp at the brocante stayed unpaid). The
  stallholder now reckons it up first, then gives the change.
- A goodbye left the sheet open; it now closes after the stallholder's answer.
- The errand card sat on the thumb stick; it is centred in the room right of the stick.
- The primeur rolled a ponytail and earrings under his cap; the brief now gives him short hair
  and no earrings, and the brocanteur no earrings.

## Round 4: smaller (r4, 844×844, load 1.8 s, 303k triangles at the arrival)

Vincent played it: beautiful, but too big to cross. You arrived 105 m from the hall and the
first errand was 91 m away, at a stroll of 1.45 m/s.

- The walk radius went from 110 m to 62 m and the build radius from 175 m to 115 m. You now
  arrive 57 m out; the primeur is 43 m away, the brocanteur 33 m, the fromagère 19 m.
- 30 stalls instead of 56, 209 buildings instead of 488, 8,400 m² to walk instead of 16,200.
  The site file is 84 kB instead of 219 kB.
- Looked at: the arrival still opens on the stalls under their canvases; the hall reads from
  outside and inside; the hoarding still closes the street where the walk ends.
- The kit walks faster too: the thumb at the rim, the keys and every walk you ask for go at
  3.1 m/s (`lib/quartier/pace.ts`); half a thumb is still a stroll.
