# Le toit: the roof over Le Mistral, at night

The next place the season's pages are set in that the world had not built (`forge.py queue
--season --from api` on 9 Nov: learners on g3 and g4, `next: toit`, first needed at
g3.bridge). It is the roof of Le Mistral's building, reached through the fifth-floor skylight,
built in its gap 3 state: at night, the skylight open, the canal below. The place stays
`locked` in `world.json` (`toit_mistral`, `stages: ["toit"]`, in the quai, no pin of its own):
the story opens it, and `stages.json` now lets a generated page be set there.

## What the canon gives

- **The places file** (`docs/story/season-1/10-lieux-et-images.md`), «The roof *(gap 3)*»:
  «Zinc roofs, chimney pots, an open skylight, the canal below, and a torch beam finding two
  figures.»
- **Gap 3 · 3 «Sur le toit»** (`09-entre-les-episodes.md`, `gaps.json`): «Lila takes the learner
  up through the fifth-floor skylight to see the canal from the roof at night. M. Marchand's
  torch finds them: «La succession Ferrand n'a rien à faire sur mon toit.»»
- **Its pages** (`bridges.json`, g3.toit): p1 «The fifth-floor skylight, open. Lila already
  outside on the zinc roof, holding out her hand.»; p2 «The canal at night from the roof: the
  locks, the lit footbridges, a barge.» («Regarde. Le canal, d'en haut. Personne ne vient
  ici.»); p3 and p4 Marchand's torch, his dressing gown and hat.

The forge's own choices, not canon: the roof is the quai's own (Le Mistral's building as
`quai.ts` draws it: a Haussmann block of five storeys whose mansard rises to a flat zinc top,
the terrasson, at 23.49 m); the skylight stands over the stair cage, 2.3 m in from the quai's
edge, its lid laid back to the west; three chimney stacks besides the two the quai's building
already has; where the people stand (`marks`: Lila by the skylight, you at the edge, Marchand
coming from the back). No photos: no open photograph shows this roof, which the canon invents;
the canon and the quai are the reference.

## The kit

A room on a roof sees the quarter, so the roof is laid into the quai's own build
(`quarter: true`): the engine builds the quai (the canal, its footbridge, the barge, the trees
and lamps, the houses and their lit windows), keeps none of its walking ground, and walks only
the roof, round the building's chimney stacks (`BuildingInfo.stacks`, now recorded by
`building()`; nothing about the quai's look changes). Floors under the sky (`zone: "out"`) are
walked now (only `sealed` or `walk: false` floors are not), and a room with nothing sheltered is
nowhere dry. New: the `zinc` finish, and the things `skylight`, `chimney` and `edge`.

## How it plays

You arrive at the edge of the roof over the quai, 23 m up, looking out over the canal at the
footbridge: «Sur le toit, la nuit. En bas, le canal.» Tap the skylight (the stairwell's light
below it), the roof's edge (what you see below: the lit footbridge, a barge, the trees), and a
chimney. «Rentrer» and the end card lists what you looked at. Nobody is there: Lila and
Marchand are the stage's.

## Round 1 (r1, r1b, 844×844, load 0.6 to 0.8 s, 105k to 150k triangles)

- **What reads.** The canal from above with its footbridge and lamps, the barge, the plane
  trees, the quai de Jemmapes with its lit windows, the zinc and its seams, the chimneys and
  their pots, the skylight's lid laid back, the rue de Lancry from the corner.
- **The arrival** stood by the skylight 4 m from the edge: from 25 m up the mansard hides
  everything nearer than 55 m, so the canal did not show, only the far houses over a field of
  zinc. The skylight and the start moved to the edge: from there you look down over the
  mansard's dormers to the water.
- **The skylight's light** did not show: its quad faced down.

## Round 2 (r2, r2-phone at 390×844)

The light faced up but still did not show: the roof's zinc runs under the skylight and covered
it. The canal reads on a phone, upright, with the footbridge in the middle of the frame.

## Round 3 (r3-phone)

The opening is now the stairwell's light a hand's breadth down inside the curb, the ladder's
top coming up through it: it reads as a way down.

## Played (the standalone page, 390×844, `?place=toit_mistral&debug`)

The cover, the arrival and its caption, a tap on the skylight, the edge and a chimney, each
line as written, «Rentrer», the end card with the three things. No errors; about 116k
triangles in the frame.

## Still plain

- **Nobody is there**: no Lila holding out her hand, no torch beam, no Marchand. The stage
  places people; a torch is a light that moves with him.
- **The dormers** of the quai's mansard are the quai's own, dark zinc gables seen from above:
  from the edge they fill the lower part of the view. They stay as the quai draws them.
- **The neon** «MISTRAL» on the corner is drawn with Le Mistral's room, which a roof does not
  build: from the corner of the roof it is not there.
- **No lock**: the canal under the roof has its footbridge and barge, not the locks of p2's
  panel (the quai has none in reach).
- **You cannot go down** by the skylight: «Rentrer» takes you back to the quai.
