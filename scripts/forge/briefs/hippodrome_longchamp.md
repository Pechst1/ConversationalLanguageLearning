# L'hippodrome de ParisLongchamp: race day

The Papier's article «Seize chevaux pour le Prix de l'Arc de Triomphe» (2026-W40, sport) names
the racecourse. Vincent asked on 2026-10-24 that a news place put you inside the event, not
beside it ("for a football match into the stadium"), so this is the first venue: the forge
places a set from the survey, and race day plays on it (`course.ts`).

## Round 1 (r1, 844×844, load 0.3 s, 45k to 68k triangles)

- **The anchor.** The article's point (48.8573, 2.2338) is on the infield: the survey around it
  found the golf course inside the track and no grandstand within 200 m. A wider read of the
  buildings found the stands 450 m north. The world entry is anchored where you stand, at the
  grandstand (48.8612, 2.2315), and the survey ran again there (Overture 2026-10-21.0, r 200 m).
- **The measures.** `venue.py` takes the track from the land use («Hippodrome de Longchamp»,
  class `track`) and the stand as the large building nearest its edge: 176 × 36 m, its front
  18 m from the rail. A larger building behind it (316 m long) is the older stand complex; it
  is not drawn. Longchamp runs right-handed, so the infield is on the horses' right and they
  come up the straight from the south-south-west, past the stand.
- **What was built.** The stand (twelve tiers, about 2,000 seated people in the inks, the glazed
  boxes, a roof on thin posts, «HIPPODROME DE LONGCHAMP» along its edge); the esplanade and the
  lawn (walk 1,459 m²: the whole errand within 25 m of the start); the white rails of the
  straight, the winning post with its red disc and the line across the turf; the betting window
  («PARIS · GUICHET»); the board across the track; the trees of the Bois beyond the infield; the
  windmill far off. Fifteen crowd spots, the clerk at the window, the regular at the rail.
- **What I looked at.** From the window: the clerk in her kiosk, the full stand behind it, reads
  well. From the rail: the forged-place haze (135 m) hid the infield and the far trees, and the
  horses would have come out of it only 135 m away. Opened it to 260 m for a venue (`engine.ts`).
  The regular filled the screen when you arrived at the rail: the goal now stops 7 m short of him.
- **The race.** Played through in the standalone page: a bet on the 9 at 40/1 («Deux euros
  gagnant sur le 9»), the money, the ticket; the regular's facts (2,400 m, more than 60 km/h);
  the stalls, the off, the far side called while the field is out of sight, the field up the
  straight in the paper inks, the finish drawn by the odds (the 16 won; the 9 came 12th), the
  board turned to, the end card. 49k triangles in play, no errors.
- **Names.** No person and no horse is named; the sponsor's name is left off the race. The
  defending winner is «le gagnant de l'an dernier», and his trainer's word on him
  («son accélération») is told as the trainer's, without his name.
- **Photos.** Not tried this round (the run went to the venue kit); the next round should look
  at Panoramax and Commons around the stand.
- **Played again.** A place bet on the favourite («Cinq euros placé sur le 3»): it came 4th twice,
  and the winners differed (the 11, then the 8). The saddle cloths of the horses running left
  read «ƐI» for 13: the number is now turned back on itself (`horse-art.ts`).
- **Sound.** The course has its din now (`audio.ts`, from `course.ts`): the crowd's murmur, a
  little louder once they are off, a roar that swells up the straight to the post and dies over
  nine seconds; the hooves on the turf from 200 m out, loudest as the field passes the rail,
  fading as it pulls up. Listened to in the headless browser by its numbers: the roar reaches
  0.99 at the post, the hooves 0.84 at the rail, seven footfalls a stride. The race is called
  aloud over the loudspeakers in the device's French voice, each call as it is captioned (from
  the stalls to «Arrivée : …»), unless the learner turned the voices off.

## Round 2: the bet as a choice

- **The odds.** A board over the window lists the sixteen runners, their silks and their odds
  («40/1»), so a learner picks a horse by reading French figures instead of guessing a number.
- **The arrival.** You used to arrive looking up the straight, with the window and the stand
  behind you. You now arrive 12 m from the window, facing it: the odds over it, the stand and its
  crowd behind. The straight is the second errand.
- **The caller** is calm on the far side, faster and higher up the straight. After the race, what
  you know has the words it used: la corde, la ligne droite, côte à côte.
- **She remembers.** The end card promised that the clerk would remember a missing bonjour; she
  now does on the next visit («La dernière fois, pas de bonjour… On recommence ?»), until you say
  it. Checked over two visits in the standalone page. Making it up is one bonjour each: hers no
  longer comes twice, and the end card no longer promises she will remember it.
- **He knows you again.** The regular at the rail no longer asks a returning player if it is
  their first Arc. He greets them by how their last ticket went («Vous venez vous refaire ?»
  after a loss, «Vous aviez eu de la chance» after a win, the last winner if they only watched),
  then lets it go.

## Still plain

- The stand is tiers and a box, not the curve of the real one; the paddock, the parade ring and
  the old stands behind are not drawn.
- One race, one pose per horse (the card bobs and rocks); the caller is the device's voice,
  calm where a real one would shout.
- The window takes one ticket a race; a second race of the day would make a place to come back
  to.
