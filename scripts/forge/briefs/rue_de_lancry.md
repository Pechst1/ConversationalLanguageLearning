# La rue de Lancry: the green door and the third-floor window, at dusk

The next place the season's pages are set in that the world had not built (`forge.py queue
--season --from api` on 13 Nov: learners on g3 and g4). The queue first named the gare de l'Est
(T8 B, the platform of 8 January): no kit can build it yet (`gare_de_lest.md`: a train shed
under glass, a platform and its track, a long white train), so the run took the next one,
`rue_de_lancry`, first needed at t8.b. It stays `locked` in `world.json` (`rue_de_lancry`,
`stages: ["rue_de_lancry"]`, in the quai): the story opens it, and `stages.json` now lets a
generated page be set there.

## What the canon gives

- **The places file** (`docs/story/season-1/10-lieux-et-images.md`, Rue de Lancry, season-2
  seed): «A narrow street running off the quai de Valmy, with tall pale façades and wrought-iron
  balconies. There is one third-floor window with an easel visible inside, and sometimes the
  tiny silhouette of an old man at it.» Rule: «background only, never larger than a thumbnail
  in the frame […] Never face-on, never named, never lit brighter than the street.»
- **T1 A P1**: «Far background, rue de Lancry: a third-floor window, an old man at an easel.»
- **T8, À suivre… (1)**: «Rue de Lancry at dusk. One lit window on a third floor, curtains
  half-open, an easel visible inside. Toi in the street below, from behind, the painting under
  one arm.» Margaux: «Rue de Lancry… C'est à deux cents mètres.»
- **E2, Day A, garder** (`12-la-semaine-dapres.md`): «Rue de Lancry, late afternoon. […] An old
  building, a heavy green door, an intercom with twelve names. None of them begins with L.» Mme
  Diallo comes out of the green door; the hook: «on the third floor, a hand closes a window.
  Behind the glass, for a moment, the shape of an easel.»

## Why a room in the quai, not a street from the map

The hand-drawn quarter already has the rue de Lancry (`quai.ts`): the street running west off
the quai by Le Mistral's corner, its faubourg houses, and on its south side the building with
the green door and the third-floor window lit low (`forceLit: ['0:3:2']`), where the engine
stands «L.» at his easel. A street surveyed from Overture (tried first: the survey and the draft
worked) would have been a second rue de Lancry, with a different green door, and the quai's
would still show «L.» from the café. So the room stands in the quarter's own build
(`quarter: true`, like the roof): its ground is the quai's street (the road at 0, the pavements
at the kerb) between x -86 and -46, walked and not drawn again (`drawn: false`), and the quai's
houses are its walls.

The forge's own choices, not canon:
- **The intercom's twelve names.** The canon wants twelve names, none beginning with L, and the
  learner reads them; the room's rule («only names the canon gives, the rest blank») cannot
  show «none begins with L» with blank cards. They are twelve of the commonest French surnames,
  none a name of the cast: Martin, Roux, Bernard, Simon, Girard, Petit, Durand, Michel, Moreau,
  Garcia, Fournier, Mercier.
- **Where you arrive**: in the street, a few steps from the quai, the green door and the
  intercom ahead on the left and the third-floor window above them (framed for a phone).

## The kit

- `intercom`: a plate beside a door, the speaker's grille, then two name cards and their
  buttons to a row (`text`, from the top floor down).
- `gaze`: nothing drawn; a point to tap where the quarter already draws something (the window).
- A room floor with `drawn: false`: walked, not drawn (the quarter lays it).
- The engine stands «L.» at his window in a room in the quarter too (it did only on the quai).
- `forge-view` reads an outdoor thing's text from a step away too, and looks up at a `gaze`
  from across the street.

## How it plays

You arrive in the street at dusk, the green door ahead. Marks: `fenetre` (in the street
below the window), `porte` and `interphone` (before the door), `coin` (toward the quai). Things
you tap: the intercom and the window. The end card remembers each.

## Rounds

1. The arrival stood too close under the door, looking up at the first floor: the window was out
   of frame. The review tool had no view of the intercom or the window (outdoor things).
2. The start moved across the street; `forge-view` gained the two views. The intercom's names
   read; the window is lit low, as the canon has it.
3. On a phone (390×844) the door and the window would not fit across the screen together, and
   the intercom fell under the joystick: the start moved east up the street, so the façade runs
   away from you with the door, the intercom and the window all in view, clear of the caption
   and the joystick.

## Played

`?place=rue_de_lancry&debug` on the standalone page at 390×844: the caption «Rue de Lancry, à
deux cents mètres du Mistral. Une porte verte, et au troisième, une fenêtre allumée.», the
intercom and the window each tapped and read, the end card with both, no errors.

## Still plain

- The green door does not open: Mme Diallo comes out of it in E2, and a room cannot play a door
  of the quai's own houses yet.
- The street is walked only round the green door (x -86 to -46); the rest is the quai seen.
- The gare de l'Est waits for its kit.
