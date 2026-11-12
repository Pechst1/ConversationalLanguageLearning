# La gérance Marchand: the office on the second floor, the evening Camille opens the door

The next place the season's pages are set in that the world had not built (`forge.py queue
--season --from g3` on 12 Nov: `next: marchand_office`, first needed at t6.a). It is M.
Marchand's office, built in the state of its fullest scene: T6 A, «L'autre côté», the evening
Camille opens the door marked «Gérance Marchand». The place stays `locked` in `world.json`
(`gerance_marchand`, `stages: ["marchand_office"]`, in the quai, no pin of its own): the story
opens it, and `stages.json` now lets a generated page be set there.

## What the canon gives

- **The places file** (`docs/story/season-1/10-lieux-et-images.md`): «A small
  property-management office in an old building. Walls of key boards hold hundreds of labelled
  keys on hooks. There are grey filing cabinets, a desk lamp, and a framed photo of his late
  wife. In the middle of it all stands a camp bed made with hospital corners. On the desk is a
  small framed Polaroid of an old man and an old woman laughing on a bench by a lake.» Mood:
  «Order holding back loneliness. Keep it cold ink and grey, with one warm lamp.»
- **The bible**: Marchand owns the café's walls and floors 2 to 4, and runs his buildings from
  an office on the second floor.
- **T6 A** (`06-lautre-cote.md`): **P1** the second-floor landing, evening; Camille opens the
  door; «in the lamplight, we see an office: key boards, filing cabinets, and in the middle of
  it all a camp bed made with hospital corners.» **P2** he gets up from his desk and offers «the
  only chair»; Camille sits on the camp bed. **P3** the Polaroid in a small frame among the
  files, its caption in her hand: «Dimanche. M. rit. Enfin.» **P7** the door half-open behind,
  «the old man under the lamp». Day B, R1: Camille watches from the window.
- **T3, À suivre**: an envelope slides under the office door; a camp bed among filing
  cabinets, lit by one lamp.

The forge's own choices, not canon:
- **Where it is.** Over Le Mistral, its floor at 7.9 m (the flat on the third is at 11.2), the
  two French windows on the canal (`canals`, the quai's own plan).
- **The plan.** One room: the landing's door in the north wall, the key boards up the west
  wall, the desk with Marchand's back to the windows, the camp bed towards the south, three
  cabinets along the south wall with the folder «TOITURE · FAÇADE» (P5's roof and façade
  numbers) on top of one.
- **The photo of his late wife** is the second frame on the desk, a sepia oval with no face
  drawn; the Polaroid faces the visitor's chair, as P6 has it «between you».
- **The calendar** says DÉCEMBRE 2026, the coat by the door is navy; the radiator under the
  windows is furniture any office has.

No open street photo shows an interior, so there is no survey: the canon is the reference.

## The kit

New in `room.ts` (and in `scripts/forge/room.py`'s lists):
- `keyboard`: a plank of brass hooks in rows, a key and its paper tag on most, one in six
  empty; `at` the board's centre on the wall, `size` [w, h].
- `cabinet`: a grey metal filing cabinet, four drawers with their pulls and label holders.
- `desk`: an old office desk, its green blotter, a pedestal of drawers on the sitter's side, a
  modesty panel at the front, files stacked at its left end.
- `campbed`: the folding X frame, the grey blanket pulled tight and tucked square with a
  crease at each corner, the sheet turned down, the pillow.
- `frame`: a small frame on its strut; with `text` a Polaroid (a lake, a bench, two small
  figures, the caption in a hand), without, an old portrait gone sepia.
- The light `desk`: a desk lamp, its brass foot behind, the arm, the green shade over the desk
  and the bulb's glow in its mouth: the room's one warm light.
- The floor finish `parquet`: an old office's, waxed dark and gone cold.

## How it plays

You arrive at the landing's door, the room lit by its lamp (an office has no minuterie), the
desk on your left and the camp bed ahead. Marks: `porte`, `bureau`, `lit`, `cles`, `fenetre`.
Things you tap: the key boards, the Polaroid, the camp bed. The end card remembers each.

## Rounds

1. The boards' floor read warm and orange, against the canon's «cold ink and grey»; one wall
   of keys held only four boards.
2. The floor became the new `parquet`; six boards now cover the west wall.
3. The walk-up check found the window and the Polaroid out of reach: the camp bed moved south
   (a corridor between it and the desk), the Polaroid to the visitor's edge of the desk.

## Played

`?place=gerance_marchand&debug` on the standalone page: the caption «La gérance Marchand, au
deuxième. Une lampe, des clés, et un lit de camp.», the room lit, the key boards, the Polaroid
and the camp bed each tapped and read, the end card with all three, no errors.

## Still plain

- The Polaroid's caption is legible only close up (it is a Polaroid on a desk): the tap says it.
- Marchand is not in his office: a room has no people yet.
- The opposite quai through the windows is the quai's generic façades.
