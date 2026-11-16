# Le bureau de l'ONG de Marin: the first floor on the quai, Friday afternoon

This is the next place the season's pages are set in that the world can build. `forge.py queue
--season --from api` on 15 Nov put the learners on t4 and t5. Everything ahead of them is built
or waits for a kit: the gare de l'Est (`gare_de_lest.md`) and, from this run, the brocante
(`brocante.md`: a vault under the quay and a door that waits for the story). Behind them, the
mairie waits too (`mairie.md`: a pin of its own, so a street, and the street kit has no town-hall
front). That leaves `ngo_office`, first needed at T3 B, for the learners still to come. The room is
built in the state of the first scene that plays there: T3 B, P1 to P6. The place stays `locked`
in `world.json` (`bureau_ong`, `stages: ["ngo_office"]`, in the quai, no pin of its own).

## What the canon gives

- **The places file** (`docs/story/season-1/10-lieux-et-images.md`): «Marin's NGO office
  (canon). The fern, the spreadsheet projected on the wall, the leek pointer.»
- **T3 B** (`03-deux-promesses.md`):
  - P1: «Marin's NGO office, Friday afternoon, with protest posters and dying plants. Marin revives
    a fern with a spray bottle. A spreadsheet is projected on the wall: «LE MISTRAL À NOUS». Lila
    sits on a desk with a coffee and her school bag.» Marin: «Attention à la fougère. Elle est
    fragile. Comme moi.»
  - P2: Marin presents with a leek from the market for a pointer: «Deux cents personnes. Mille
    euros chacune. Une banque.»
  - P3: «The café's floor plan on the wall. Long tables at the front marked «cantine le midi», the
    booth moved to the back, and the back room marked «ATELIER».»
  - P5: Marin sits opposite you, big hands round a mug, the plan behind him.
- **The bible**: Marin works at an environmental NGO.
- **The project's own world bible** (`app/prompts/serial/world_bible_paris_v2.json`) is not season
  canon, but the forge follows it: «Cluttered environmental NGO office with protest posters, maps of
  waterways, dying plants Marin keeps reviving, mismatched mugs.» Its palette is «sea green, paper,
  poster red».

## The forge's own choices, not canon

- **Where it is.** The first floor of the Haussmann house on the quai between z 52.8 and 72, the
  next house south of Gus's. This is the façade the quai already draws (`row`, seed 48). You come
  in by its own street door, bay 1, at z 67.21. The stairwell is Gus's plan turned over (the flight
  on the north side of the cage, the corridor on the south), so the office lies north of the cage
  over the house's shops: 9.7 m by 9 m, floor at 4.6 m, three French windows on the canal. The
  canon only says «Paris 10e». The map entry's lat/lon is approximate, because a room is never a
  pin: 88 m from the quai's pin.
- **No name.** The canon names no NGO, so the letterboxes are floor numbers only and no poster
  carries a name.
- **The posters** are slogans the forge wrote: «Sauvons le canal», «L'eau n'est pas à vendre»,
  «Moins de béton, plus d'arbres», «Zéro plastique dans la Seine».
- **The map of the waterways** is drawn plain: the Seine, the canal Saint-Martin up to the bassin
  de la Villette, the canals de l'Ourcq and Saint-Denis out of it, red pins along them.
- **The spreadsheet's rows** are the canon's numbers: 200 sociétaires, a 1 000 € share, 200 000 €,
  and the bank's loan as a question mark («À nous et à la banque», says Lila).
- **The hour.** The kit's day light (`matin`) stands in for Friday afternoon.

No open street photo shows an interior, so there is no survey: the canon is the reference.

## The kit

New in `room.ts` (and in `scripts/forge/room.py`'s lists):

- `poster`: a sheet taped to the wall, a slogan in big capitals a line each, sea green, poster red
  or paper by turn, a wave at its foot.
- `map`: the waterways, as above (`text`: the title, then the names).
- `projection`: a spreadsheet thrown on the wall, the title band, then a row a «label | value».
- `projector`: a small projector on a desk, its lens lit.
- `plant`: a pot plant that needs water, its outer leaves yellow and drooping.
- `fern`: a fern on a stand, its fronds arching out, the spray bottle beside it.
- `leek`: a leek lying on a desk.
- `mug`: a mug, each one a different colour.

## How it plays

- **On foot:** you come from the quai through the street door, cross the tiled vestibule and climb
  the flight to the first-floor landing. The office's door is there. It stays shut until the story
  has played there: «Tu frappes. Personne ne répond, pas encore.»
- **On arrival** (`?place=bureau_ong`): you stand inside the door, facing the spreadsheet on the
  far wall, the two desks pushed together between you and it, Marin's desk and the fern by the
  windows on your right, the posters, the plan and the map on your left.
- **Marks:** `porte`, `tableur`, `plan`, `bureau`, `fougere`, `fenetre`, and in the stairwell
  `streetDoor`, `hall`, `foot` and `premier`.
- **Things you tap:** the spreadsheet, the map, the plan, a poster, the leek and the fern. The end
  card remembers each.

## Rounds

1. The room read as an office, with the spreadsheet legible across it. But the map and the two
   four-line posters were blank: the room asked more of the sign atlas than it holds, and the last
   cards did not print. The fern's fronds were broad blobs.
2. The posters, the map and the spreadsheet print at lower densities, and the plan is smaller
   (0.75 m): every card prints. The fern's leaflets are narrower. The fern was still out of the
   arrival's view.
3. Marin's desk moved to the far window and the fern to the pier between the first two windows, so
   you come in seeing the spreadsheet, the desks and the fern, as P1 lists them.

## Played

On the standalone page at 390×844 (`?place=bureau_ong&debug`):

- The caption: «L'ONG de Marin, au premier. Des affiches, des plantes qui ont soif. Au mur, un
  tableau : « LE MISTRAL À NOUS ».»
- You come in facing the spreadsheet, legible on the phone.
- The spreadsheet, the map, the plan, a poster, the leek and the fern were each tapped and read.
- The end card showed all six, with no errors.

`world-rules.test.js` walks from the quai through the street door and up to the office's door.

## Still plain

- **Nobody is there.** Marin, Lila on her desk with her school bag and coffee: a room has no
  people yet.
- **The receipt.** P4's folded bank receipt («4 000 €») comes out of Marin's wallet later in the
  scene; it is the stage's, not the room's.
- **The light.** The projector throws no beam; the spreadsheet is lit like the wall round it.
- **The view.** The houses across the canal are the quai's generic façades.
