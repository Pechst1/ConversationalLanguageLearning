---
name: quartier-forge
description: Build the next corner of Paris for Le Quartier, from open map data or, for a room of the season, from the canon. Take the next place the season's story is set in (forge.py queue --season) and the next thing the learners' stories left in the quarter (forge.py queue --orders), or, when the story has nothing waiting, a place the Papier names; survey it, draft the site (a street with its trade, or a venue where the news happens), or write the room from the canon; render and critique it (three rounds at most), publish a street on the map (a room stays locked) and open a PR. Never merges. Use for the nightly "Quartier forge" scheduled task, or when asked to "forge <place>", "build <place> in the Quartier", "build the next room" or "grow the world".
---

# Quartier forge

Le Quartier's Paris is not built all at once. The quai de Valmy and Le Mistral are drawn by
hand; every other place is forged when the story or the news names it. The story comes first:
the forge builds the next place the season's pages are set in, just ahead of the learner, so that
a day set there plays there. A place the news names is on the map the moment its article is
(`forge.py news` writes the news layer, pinned under scaffolding); the forge builds it when the
season has nothing waiting. One run builds one place:

```
queue → world entry → brief → survey → draft → check → plan → render → look → notes
      → revise (back to draft, three rounds at most) → publish → tests → PR
```

The code is `scripts/forge/` (Python: `forge.py`, `overture.py`, `draft.py` for a street,
`venue.py` for a venue, `room.py` for a room) and `web-frontend/lib/quartier/` (the kit that
builds a site in 3D, `visit.ts` that plays a street, `market-talk.ts` for what the stallholders
say; `hippodrome.ts`, `course.ts` and `course-talk.ts` for race day; `room.ts` and `interior.ts`
for a room). `scripts/forge/briefs/marche_aligre.json` and `.md` are the worked example of a
street, `hippodrome_longchamp.json` and `.md` of a venue, `escalier_mistral.json` and `.md` of a
room: read the pair that fits before writing a brief. A room of the season is written from the
canon, not surveyed: see **Rooms of the season** below for how its run differs.

## Two rules every place keeps (owner, 13 Nov 2026)

Every place a run builds keeps both; `forge.py check` and `forge.py publish` refuse one that does
not, and the PR's tests (`web-frontend/lib/quartier/world-rules.test.js`,
`tests/test_quartier_forge_queue.py`) fail on it. Never work round them by editing those tests or
the lists in them.

1. **On foot.** A place the story uses is walked into from the walkable quarter, never only
   handed over by the story: a flat through its building's street door and up its stairwell, a
   shop or a café through its door. In `world.json` the place has an `entrance`: `from` (the place
   whose ground the door is on, usually `quai_de_valmy`), `door` (the door in the façade, x and z
   in the quarter's coordinates: find the façade's own door in `lib/quartier/quai.ts`, a `door`
   bay, and use it rather than cutting a new one), `outside` (where you stand on the pavement,
   walkable in `from`), `inside` (just inside the door, walkable in the place), `look_in`,
   `look_out`, and in three languages `enter`, `leave` and `arrive` (the caption you walk in to).
   From `inside`, the place's own ground must lead to its start, to every mark the story stands
   people at and to everything you can tap. The walking grid is one sheet, so a climb past a
   storey and a door the story keeps shut are `passages` in the room's brief (`a`, `b`,
   `look_a`, `look_b`, `to_a`, `to_b` in three languages, `door`: the leaf it swings, `until:
   "story"` and `shut` for a door that opens on foot only once the learner's story has played
   there, so nobody walks into a scene before the story gets there). A flat upstairs is built
   with its stairwell in the same room file: the vestibule behind the street door, the
   corridor, the flight to the first floor (Le Mistral's stairwell's plan, as in
   `chez_marin_lila.json`), and a passage up to the landing before its door.
   The places built before the rule that have no door yet are listed in `WAITS_FOR_A_WAY`
   (`forge.py` and `world-rules.test.js`): the list only shrinks. A run that gives one of them
   its door removes it from both lists.
2. **On the map.** A place gets a pin of its own only when it lies `MAP_PIN_MIN_METRES` (300 m)
   or more from every other pin (`lib/quartier/world.ts`, `forge.py`: on a phone two pins nearer
   than that overlap where a thumb lands). A place nearer to a pin is inside it: `in` names that
   pin, it has no pin, and you reach it through the pin (and on foot, through its door). A
   street or a venue far enough from every pin is a pin. Say in the PR which way the place fell
   and how far it is from the nearest pin (`forge.py check` prints it when it fails).

## Setup

```
python3 -m venv ~/.venvs/forge && ~/.venvs/forge/bin/pip install -r scripts/forge/requirements.txt
export PY=~/.venvs/forge/bin/python
```

In a cloud session, prefix network commands with `REQUESTS_CA_BUNDLE=/root/.ccr/ca-bundle.crt`.
The survey reads Overture's public bucket (`overturemaps-us-west-2.s3.us-west-2.amazonaws.com`).
The renders need `web-frontend/node_modules` and a Chromium (`/opt/pw-browsers/chromium` in
the cloud; never run `playwright install`).

## The register: which built place plays which place of the story

The story names its places by the season's ids (`SEASON_ONE_LOCATIONS` in
`app/services/season/world.py`: `stairwell`, `toit`, `marchand_office`…); a page's panels carry
them as `location_id`. The world's places say which of them they are the stage for, in
`world.json`: `stages` (a page set there plays here) and `sees` (seen from here without going
in: Odile's kitchen through the stairwell's open door). It is the only link between the two:
the 3D hands a page over to the room that `stages` its place (`stageOf` in `lib/quartier/world.ts`),
and the season queue below counts a place as built when a room, a site or the hand-drawn quarter
stages it. A world entry without `stages` is a place no page ever reaches: `check` refuses a
room without one, and two built places never stage the same id.

The server keeps a copy of the register, `app/data/season/s1/stages.json` (its image has no
`web-frontend`): the night writes a generated page only at a place the world has built, so a new
place the forge builds is a place the story can go the night its PR is merged. After any change
to `world.json`'s `stages` or to what is built (a `room` or `site` set), run
`$PY scripts/forge/forge.py stages` and commit the file with the run (`publish` writes it
itself); `check` and `tests/test_quartier_forge_queue.py` refuse a stale copy.

## The run

0. **What the story needs.** `$PY scripts/forge/forge.py queue --season --from api` reads
   the season's own pages in order (each tentpole's days, each gap's bridge page) and lists every
   place they are set in, with what the world has for it: `built`, `locked` (a world entry,
   nothing built) or `new`. `--from api` asks the server which segments the season's learners
   are on (`GET /api/v1/story-engine/season-frontier`; its first line says so): the place the
   nearest learner reaches first is listed first, then what lies behind them all. Should the
   server be unreadable, it says so and starts at the season's beginning; `--from g3` (or
   `g3,t1`) names the segments by hand. `--from api` also reads what the learners' pages named
   (step 0b): a place of the season a page named comes first, «named by N lives». A page goes
   only where the world is built, and names the rest first («Erst erwähnen, dann betreten»,
   Vincent, 8 Nov): so the place the story asked for is the one to build. Its last line names the next place to build. Build that one (a room of the season, below, or a street
   from the map data for a place outdoors) before anything the news asks for. A place no kit can
   build yet (a station platform, a park): write `scripts/forge/briefs/<location>.md` starting
   «Waits for a kit:» and one line on why and what kit it needs (the queue then shows it as
   `no kit` and names the next), commit it with the run, and take the next. When the line says `next: none`, go on with
   the details (below), then the news.
0b. **What the stories left.** The learners' own pages grow the quarter too: each page says
   what it leaves there (a thing at a place, a place it names), and
   `$PY scripts/forge/forge.py queue --orders` reads what the season's recent lives left
   (`GET /api/v1/story-engine/world-orders`, merged; what a learner named in their own words
   comes first, `said by N` on its line, then the most asked for; `--from <file>` reads a saved
   copy). A learner's own words are the strongest order there is (Vincent, 8 Nov): they asked
   for that place or thing themselves. Each line is a thing or a place with its status: a thing is `new`
   where its place is built (a detail of that place, below), `waits` while its place is not
   (the season queue builds the place first), `built` once a detail waits on it; a place is
   `season` when it is one of the season's (step 0 builds it in its time), `built` when the
   world has it, `new` when the world has never heard of it. A detail is small: besides the
   run's place, lay the `next detail:` it names (one a run), before the ladder's. A `new` place
   (`next place:`, with the id to give it) is the run's place instead of step 0's when no
   learner reaches step 0's within seven days (`in N days` on its line), when two lives or
   more named it, or when a learner named it in their own words (`said by`): see **A place the stories named** below. Otherwise list it in the PR.
1. **Pick a news place** (only when step 0 has nothing to build). `$PY scripts/forge/forge.py news` refreshes the map's news layer
   (`world/news.json`, held to the articles by `news.test.js`); commit it with the run.
   `$PY scripts/forge/forge.py queue` lists the places Papier articles name with an exact
   position in Paris: `en_chantier` first, then `new`. Take the first one you can build. Put
   the player inside the news, not beside it: where the article is an event (a race, a match,
   a debate) build the venue where it happens if the kit has one (today `hippodrome`); a
   street the article is about is drafted with its trade. An interior with no venue kit yet (a
   chamber, a stadium), a place outside Paris or a vague location cannot be built: write
   `scripts/forge/briefs/<id>.md` with one line on why and what kit it needs, and take the
   next. If nothing is left, stop and say so in one line.
2. **World entry.** If the place is not in `web-frontend/lib/quartier/world/world.json`, add it:
   `id`, `name` and `why` in fr/en/de (`why` cites the Papier: «Le Papier : « <title> ».»),
   `lat`/`lon` from the article's `geo` (for a venue, where you stand: the grandstand, not the
   infield the article may point at), `status: "en_chantier"`, `kind: "news"`,
   `source: { kind: "papier", id, title_fr }`, `site: null`, and `ride`: how you get there
   from the quai (the metro from République or Jacques Bonsergent, in fr/en/de). Keep the
   file's format: one key a line, small flat objects on one line.
3. **Brief.** Write `scripts/forge/briefs/<id>.json` from the article and the survey:
   `radius` (walk about 60 m, build about 115 m: a corner of Paris, not a district; every
   errand within about 50 m of the start), `ambiance` (`matin` or `nuit`), `title` and
   `can_do` (what a learner practises there, fr/en/de), `arrondissement` for the street
   plaques, `level_streets`, `landmarks` (match an Overture name, give a kind the kit has:
   `halle`, `pavillon`), `market` rows if it is a market, `start` (a street, facing a
   landmark), `commerce`, and `people`: who stands where, with `goods`, `seed`, `name`,
   `goal` (an errand that leads you to them) and `look` (slots of `web-frontend/lib/avatar.ts`;
   give masculine names short hair and no earrings unless the brief says otherwise). They stand
   in the round as their card draws them (`lib/quartier/cast3d/avatar.ts`): every slot and
   colour of the `look` is what the learner sees. A venue's
   brief says `venue` instead of `market`: its `kind`, the way the course turns, and what the
   article says of the event (`race`: name, metres, hour, runners), with the people the venue's
   director stands (`guichetiere` at the window, `habitue` at the rail).
4. **Survey, draft, check, plan.**
   ```
   $PY scripts/forge/forge.py survey <id>   # var/forge/<id>/survey.json
   $PY scripts/forge/forge.py draft <id>    # web-frontend/lib/quartier/world/sites/<id>.json
   $PY scripts/forge/forge.py check <id>
   $PY scripts/forge/forge.py plan <id>     # var/forge/<id>/plan.svg: look at it before rendering
   ```
   Read the draft's warnings. A redraft of an unchanged brief must give the same file.
5. **Render and look.** From `web-frontend/`:
   `node scripts/quartier/forge-render.mjs lib/quartier/world/sites/<id>.json ../var/forge/<id>/renders/r<n> --size 844x844 --scale 1`.
   Open `sheet.png` and `render.json`. Ask, view by view: does the arrival read as the place
   the article describes? Does each landmark read from outside and from inside? Is anything
   empty, floating, cut or wrong for Paris? Is the edge of the walkable world closed? Is the
   frame affordable on a phone: about 450k triangles or fewer at street level, a load under
   about 2.5 s here? The renders stand the people up as the game does (the stallholders behind
   their stalls, a venue's people at the window and the rail, the passers-by), so the count is
   the whole frame's; past 30 m everyone the avatar kit draws changes into a body of under half
   the triangles. `peopleMs` is how long they take to stand up after the load (one by one, so
   the first frame does not wait for them; Aligre's fifty take about 2.6 s). To look at the
   brief's people up close:
   `node scripts/quartier/cast3d-sheet.mjs ../var/forge/<id>/renders/r<n>/people.png --avatars '[{"key":"primeur","seed":4101,"look":{"hat":"casquette"}}]'`
   (`--far` for their far bodies).
6. **Notes and revise.** Write what you saw in `scripts/forge/briefs/<id>.md`, a section per
   round: what was looked at, what is wrong, what you changed. Change the brief first; change
   the kit (`lib/quartier/*.ts`) only when the brief cannot say it, and keep the quai's look
   unchanged. Draft and render again. Three rounds at most.
7. **Something to do there.** A place opens only when a learner can do something in French
   there. Today that is a market (stallholders who sell through `market-talk.ts`) or a venue's
   event (race day, `course.ts`: a bet at the window, the race called, the result). What anyone
   says about the place comes from its Papier article and is keyed to it (`Know.place`,
   `MarketBark.place`, `course-talk.ts`); never reuse another place's facts, never name a real
   person, a horse or a sponsor. A place of another
   kind is drafted, rendered and critiqued, then stays `en_chantier`; its notes say what it
   lacks (a talk module for a bakery, a café, a ticket office).
8. **Publish** (only when step 7 is met): `$PY scripts/forge/forge.py publish <id>` checks the
   site, opens it on the map (`world.json`) and regenerates `world/sites/index.ts`.
9. **Tests and checks.** From `web-frontend/`: `npm test` (`lib/quartier/site.test.js` holds
   every site to the forge's checks, `market-talk.test.js` to the canon, `world-rules.test.js`
   every place to the two rules), `npx tsc --noEmit -p .`,
   `npm run lint`, `npm run build`. Play it once: `node scripts/quartier/build-standalone.mjs`,
   open `out-quartier/le-quartier.html?place=<id>&debug`, begin, follow the errands, buy
   something, leave, go home.
10. **PR.** Branch `claude/forge-<date>-<id>` from origin/main. Commit the brief, its notes, the
    site file, `world.json`, `sites/index.ts` and any kit change (never `var/`). A place that
    stays `en_chantier` commits its brief, its notes and its world entry, not the site file: the
    tests load every site file as an open place, and the brief drafts it again. Open a PR titled
    «Le Quartier forge: <place name>» with: the article, what was built (the draft's counts),
    each round in a line, what is still plain, open or `en_chantier` and why, and how to play it
    (`?place=<id>`). End with one short summary: the place, its status, the PR link.

## Rooms of the season

The story's own places (the stairwell, the flat above the café, the notary's office) are not on
any map: they are written from the canon and built with the pieces Le Mistral's room is built
from (`room.ts`: the wainscot wall, the façade's lining, the globes, the tables), so a room and the
café are the same print. The story sets the order (step 0): the next room is the next place
`queue --season` lists that is not built. Built so far: the stairwell and Odile's door, the
learner's studio, Maître Vasseur's office, Odile's flat, the roof over Le Mistral
(`toit_mistral`, gap 3), Le Mistral's back room (`arriere_salle`, T5 B: through the café's
back door, at -37.6 x, -18.1 z in the café's own plan), Marin and Lila's flat
(`chez_marin_lila`, T5: on the third floor of a building on the quai, its windows on the canal)
the gérance Marchand (`gerance_marchand`, T6 A: on the second floor over Le Mistral, floor
7.9, its windows on the canal), the rue de Lancry (`rue_de_lancry`, T8 and E2: the quai's own
street, `quarter: true`, round «L.»'s green door and his third-floor window) and Gus's «château»
(`chateau_gus`, T8 À suivre (2) and the epilogue: the fifth floor of the Haussmann house on the
quai at z 36 to 52.8, its door bay 0, the painting turned to the wall between two windows). A room under the sky is a room too: its floors are `zone: "out"` and
you walk them (only a `sealed` floor, or one with `walk: false`, is not walked), and nothing on
it is dry. A room on a roof of the quai says `quarter: true`: the engine builds the quai round it
as it is (the canal, the footbridge, the barge, the houses and their lit windows) and walks only
the room's own ground, round the chimney stacks the quai's building already has
(`BuildingInfo.stacks`). A street the quai already lays (the rue de Lancry, at x -53 to -178 and z
-6 to 6: the road at 0, its pavements at the kerb, 0.14) is a room in the quarter too: its floors
are that ground with `drawn: false` (walked, not drawn again), and the quai's own houses, doors and
lit windows are its walls; tap them through things (`intercom`, `gaze`). Build a place the quai
already has there, never a second copy of it from the map data. Le Mistral's roof is the flat top of its mansard (the terrasson, at
23.49 m, inside the building's walls; the mansard falls away at the street sides, so you see the
canal from its edge, not from the middle). A run builds one room instead of a street; it follows
the steps above with these differences.

1. **Canon.** Read the place in `docs/story/season-1/10-lieux-et-images.md` (its canonical
   descriptor, its states across the season, its «Never») and the scenes that happen there
   (`docs/story/season-1/` scene files). Build the state of the first scene that plays there.
   Quote the canon's lines at the top of the notes; say which choices are the forge's (an hour on
   a clock, a plan, a name on a letterbox: only names the canon gives, the rest blank).
2. **World entry.** `status: "locked"`, `kind: "season"`, `stages`: the season's ids it is the
   stage for (`["toit"]`; the id the queue named), `sees` if a page looks into another place from
   it, `source: { kind: "season", id: "s1" }`,
   `site: null`, `room: "<id>"`, and `in`: the place on the map it is inside (the stairwell, the
   studio are in `quai_de_valmy`; the notary's office, 86 m from the mairie's pin, is in
   `mairie_10e`: `in` is the nearest pin, within `MAP_PIN_MIN_METRES`). A room is never a pin of
   its own and is never published (`forge.py publish` refuses it): the story opens it. It has its
   `entrance` (**Two rules**, above): the door you walk in by, and the stairwell up to it.
3. **Brief.** `scripts/forge/briefs/<id>.json` with `kind: "room"`, `in`, `canon` (`doc`,
   `place`, `scenes`), `ambiance`, `title`, `can_do`, `arrive` (the caption you arrive to, in
   three languages; the kit's default speaks of the dark), `start` (`pos`, `look`), and the room in the
   quarter's coordinates (x east, z south, metres; the stairwell stands where the quai's façade
   has its street door):
   - `spaces`: rectangles with a `floor` height, a `ceiling`, a `finish` (`cabochons`, `boards`,
     `parquet` (an old office's, dark and cold), `tomettes`, `cobbles`, `stone`, `zinc`), a `zone` (`room` is lit by its lamps; `sealed` is seen and
     not entered yet; `out` is under the sky), `walk: false` for a floor seen, not walked, and
     `walls` (`finish`, `tone`, `dado`, or null where a space opens into the next). `open` cuts a
     side's opening (`{ "w": [{ "u": [1.5, 2.75] }] }`, u along the side from its start); a
     passage under a lintel (`"top"`) with `"framed": true` is a doorway with its jambs and
     architrave. Two rooms side by side need a `floors` strip in the doorway (the walls between
     them are not ground you walk).
   - `walls`: the walls no space draws (a stair cage's, a partition under a flight), each from `a`
     to `b` with the room on its right, `base` and `top` (a pair where they slope).
   - `flights` (`from`, `dir` along x or z, `width`, `y0`, `y1`, `risers`, `tread`, `rail`),
     `rails` along open edges, `ceilings`.
   - `doors` (on a wall by its key or a space's side, `<space>.<n|e|s|w>`, with `u`, `height`,
     `hinge`, `swing`, `tone`, `numeral`, `opens: "never" | "once"`, `mat`), `windows` (`u`, `y`,
     `shutters: "closed"` for the slatted street light, `"open"` for the persiennes folded back
     on the façade, `sun: true` for the morning sun laid on the floor in the floor's own finish,
     `balcony: 0.6` for a narrow balcony outside with the quai's ironwork), `holes` (a way through
     with no door, `framed` as above).
   - `lights` (`globe`, `sconce`, `hublot`, and `desk`: a desk lamp, `at` the green shade's mouth
     over the desk, `facing` the way it leans, its foot behind) on a `circuit`, its `switches` (push-buttons, 1.0 to
     1.7 m above the floor in front of them) and `timers` (seconds a press keeps it lit). A room
     with no switch (a flat, the studio) is lit from the start and stays lit.
   - `things` the kit draws (`letterboxes`, `coat`, `clock`, `calendar`, `table`, `chair`,
     `slippers`, `camera`, `cup`, `stove`, `patch`, `doorway`, `mat`, `radiator`, `bed`, `phone`
     with its screen's lines in `text`, `keys` with the cicada, `suitcase`, `kitchenette`,
     `longtable`, `armchair`, `pen`, `folder` with its label in `text`, `bookcase`, `polaroids`
     (the shoebox out from under the bed, the photos spilled in front of it over `size`),
     `armoire`, `drink` with the order in `text`: a cup on its saucer by what it holds, its
     handle on local +x; on a roof, `skylight` (a tabatière: its curb, the glazed lid laid back,
     the ladder's top and the stairwell's light, `size` [across, along]), `chimney` (a stack
     with its pots, `size` [long, high]) and `edge` (the zinc's rolled edge where the mansard
     falls away, `size` [length, 0]: tap it for what you see below); in a back room, `easel` (a
     painter's easel with its canvas under a white sheet, `size` the canvas), `crates` (wooden
     crates stacked against a wall, `size` [across, high]), `board` (the electrical board on the
     wall, its breakers behind a smoked window, the meter and the trunking up to the ceiling) and
     `plan` (a plan drawn by hand and pinned up: `text` its title, the back room's square, then
     the labels of the room); in a flat, `fridge` (its door's folder, `text[0]`, `''` for none,
     a card in a quick hand under a sardine, the rest of `text`, a line a paragraph, and a
     felt-tip drawing), `crate` (a painting's shipping crate on its edge, its stencil in `text`,
     the first line red), `canvas` (leaning face to the wall, half in bubble wrap) and an
     `easel` with `size` [0, 0] (nothing on it); in an office, `keyboard` (a plank of hooks and
     tagged keys on the wall, `at` its centre, `size` [w, h]), `cabinet` (a grey metal filing
     cabinet, four drawers, `size` [w, h]), `desk` (its blotter, files stacked at its left end,
     the drawers on the sitter's side, local -z), `campbed` (made with hospital corners, `size`
     [length, width] along local x, the pillow at -x) and `frame` (a small frame on its strut: a
     Polaroid with its caption in `text`, or without `text` an old portrait gone sepia); in a
     showman's flat, `banner` (a banner on a gilt pole, red to a point, a crown, a chevron and
     three stars: `at` the cloth's centre, `size` [w, h]), `mantel` (a marble chimneypiece, cold
     logs, a tall gilt mirror over it: `size` [width, the mirror's height], `tone` the marble),
     `candelabra` (three candles lit, `at` its foot on a shelf), `lowtable` (glass on brass, a
     decanter and two tumblers, `size` [w, d]), `letter` (an envelope face up: `text` the name in a
     hand and the postmark's town), `rug` (a red rug, its border and medallion, `size` [w, d]),
     and `canvas` with `text`: a small oil in its gilt frame leaning face to the wall, what is
     written on its back a line each (the first in ink, the rest in pencil, shaky); in a
     street, `intercom` (a plate on the wall by a door, `text` its names from the top floor down,
     two to a row, `at` its centre) and `gaze` (nothing drawn: a point to tap where the quarter
     already draws something, a window up the street)) with
     `zone`, `tone`, `text`, `size`. A thing with `look` (three languages) can be tapped and says
     it in a line; its `did` is what the end card remembers. `courts` are seen through a window:
     `storeys` one fewer than your floor puts their zinc at your eye, and `roofs: true` gives
     them the mansard, dormers and chimney pots. `boulevards` are a street under a window (`x0`,
     `x1`, `z` our façade's outer line, `side`, `width`, `storeys`, `seed`, `lit`, `clear`: a
     stretch of our kerb with no plane tree, so the windows over it see down to the pavement):
     the quai's own stone houses across it, trees, lamps, a bench. `canals` are the quai de
     Valmy and the canal under a window on its façade (x -27), laid from the quai's own plan
     (`z0`, `z1`, `storeys` across the water, `seed`, `lit`): its trees where the quai has them,
     the gap by the café's corner, the lamps, the water, the quai de Jemmapes. `guard: true` on
     a window gives a French window its iron garde-corps. A calendar's `text` after its two
     months is what is written on it («12/4 dentiste», «Tous les dimanches : M.»), in its days.
   - `marks`: where the stage stands people. The room director (`interior.ts`) reads `landing`
     (where the climb ends), `door` (where you stand before the door the story opens),
     `threshold` (where you look in from) and `inside` (what you look at); the cast's marks
     (`lilaStep`) wait for the stage. A mark you are walked to stands where a body fits (22 cm
     clear all round): short of that, the walk ends at the nearest place that does, half a metre
     off, and you see the door from the side.
   The walking grid has one height a cell: no floor you walk may lie over another you walk (a
   flight runs beside the corridor below it, never over it). `check` says so when it happens.
4. **Draft, check, plan.** `$PY scripts/forge/forge.py draft <id>` writes
   `web-frontend/lib/quartier/world/rooms/<id>.json` and `rooms/index.ts`; `check <id>` holds it
   to the walking grid, the circuits, the marks and the canon's door; `plan <id>` draws
   `var/forge/<id>/plan.svg`. No survey: the canon is the reference, and no open street photo
   shows an interior, so the notes say so in a line.
5. **Render and look.** The same `forge-render.mjs`, with the room file. The views: the arrival
   in the dark and lit, from each of the stage's marks to the next, what the things say (a
   phone's screen with the lens closed on it, as a hand brings it up), each
   flight from its top, each window, each door, the door the story opens standing open as the
   stage frames it, and a plan of each floor cut under its ceiling. Ask, view by view: does each
   line of the canon read (say which)? Is anything a «Never» of the canon (mess, decay, horror: a
   coat must read as a coat, not a figure in the dark)? Is the dark dark and still legible on a
   phone? Does the door's number read? Does anything float, gap or show the void?
6. **Play it.** The standalone page with `?place=<id>&debug` opens the room even while it is
   locked: press the button, climb, open the door once, see it shut and the light go out, come
   back to find it shut, leave. In a lit room: tap each thing with a `look`, read its line, leave,
   and read the end card. Then walk it in from the street: open the standalone page with no
   `place`, walk the quai to the door (its card shows when you stand at it), go in, climb, take
   the passages, and walk back out onto the quai. `lib/quartier/room.test.js` builds every room
   file and holds it to the same checks; `lib/quartier/world-rules.test.js` walks from the quai's
   start to the door and from inside it to every mark and every thing you can tap.
7. **PR.** Run `$PY scripts/forge/forge.py stages` once the room is built (`room` set and
   `stages` given in `world.json`). Commit the brief, its notes, the room file, `rooms/index.ts`,
   `world.json`, `app/data/season/s1/stages.json` and any kit change (never `var/`), titled
   «Le Quartier forge: <what was built>». The PR says where the door is (which street, which
   bay of which façade), how you climb to the place, and the map's verdict: «inside <pin>, N m
   away» or «a pin of its own, N m from the nearest». Its checks are the run's checks and
   `pytest tests/test_quartier_forge_queue.py` (the register, `stages.json`, the two rules).

## A place the stories named

A shop, a café, a flat, an office a learner's page named that the bible does not have
(«la librairie de la rue Bichat»): the stories asked for it, so the quarter grows it. Once it is
built, the night may set pages there, in every life of the season (`stages.json` carries it as
one of `places`; `app/services/season/world.py: story_places`).

1. **What it is.** Read its order: the name, the `look` of each life that named it, how many
   lives. It is a place of this quarter, in the canon's tone (`docs/story/season-1/10-lieux-et-images.md`):
   ordinary, lived in, never a brand or a real business. An indoor place is a room, written like a
   room of the season; a street or a square that exists in Paris is a site, surveyed like any
   street.
2. **World entry.** `id` as `queue --orders` gives it, `kind: "story"`, `status: "locked"`, `name`
   in three languages, `in` (the place it is reached from, usually `quai_de_valmy`), `why` («Les
   histoires l'ont nommée.»), `stages: [<its own id>]`, and `story`: `description` (one English
   sentence the night writer reads: what the place is and what is in it) and `named_by` (lives).
3. **Build it** as a room (**Rooms of the season**, steps 3 to 6, with the order's looks as its
   canon) or a site (the run's steps 2 to 9), then `$PY scripts/forge/forge.py stages`: the place
   is in `stages` and in `places`. `queue --orders` lists its order as `built`.
4. **PR** as usual, titled «Le Quartier forge: <name> (named by the stories)».

## Details: what the story leaves

A detail is a small thing in a built place that appears once the learner's story put it there.
One a run, in this order:

- **What the stories left** (step 0b): the `next detail:` of `queue --orders`, a thing the
  learners' own pages left at a built place (Gus's petition on Le Mistral's window). It waits on
  that mark: a learner sees it once a page of theirs left it.
- **The plan's ladder** (`docs/story/season-1/09-entre-les-episodes.md` and the episodes): the
  learner's usual cup on the zinc after «La même chose ?» (done), then the next line of the
  ladder that leaves a thing in Le Mistral (the party's garlands…). It waits on the season flag
  the moment sets. What T1 already stages (the key, Odile's café crème) is not a detail.

1. **Canon.** For a story order: the order's line (its name, its place, its `look`, how many
   lives left it) and the canon of the place it stands in (`docs/story/season-1/10-lieux-et-images.md`);
   it must be something the canon allows there (no brand, no real person, nothing a «Never»
   forbids). For the ladder: the line, the scene that sets it, and the season flag it waits on
   (`app/data/season/s1/season.json`); the values `bridges.json` gives that flag are what it
   must build for.
2. **Detail file.** `web-frontend/lib/quartier/world/details/<id>.json`: `kind: "detail"`, `in`
   (the built place it stands in: the order's stage from `queue --orders`, `quai_de_valmy` for
   Le Mistral's room, or a room of `world/rooms`), `title` in three languages, `moment`, then
   either `mark` (a story order: `name_fr` and `location_id` exactly as the order gives them)
   or `flag` (the ladder: `key`, and an `example` value shown when none is given); `things` (the
   room kit's things, in that place's coordinates: inside Le Mistral's room the zinc's top is
   at 1.26 m; inside a room, within its walls), `provenance` (`canon`, `scenes`: for an order,
   the order's line). A thing's `text` may say `{value}` when it waits on a flag: the flag's
   value is written in. Add it to `world/details/index.ts`. Nothing in `world.json` changes: a
   detail is not a place.
3. **Look.** The standalone page lays it on request where it stands: `?detail=<id>` (and
   `&place=<in>` for a room; `&value=<the flag's value>` for the ladder). Render it (for a flag,
   each value the season offers): from where you stand, close up, and the room; then at
   390×844. Does it sit on something (no saucer sunk in the zinc), read at a glance, change
   with the value? In the quarter a learner sees it once their own story set the flag or left
   the mark (the server's `/story-engine/world-state`; `setBy` in `details.ts`).
4. **Checks.** `lib/quartier/details.test.js` holds every detail to its file, its flag or its
   mark (the mark's place must play in `in`, per `stages.json`), its place and its room, and
   builds it for every value; `$PY scripts/forge/forge.py queue --orders` then lists the order
   as `built`. Then the run's usual checks and PR.

## Rules

- Open data only: Overture Maps, with its release and attribution kept in the site file. Never
  Google Street View, Google or Apple imagery, or any imagery whose terms forbid deriving a
  model from it.
- Photos guide the critique in step 5; they are never copied into the game. Two sources:
  Vincent's own under `scripts/forge/photos/<id>/`, and open street photos when the
  environment lets their hosts through. Try each once:
  Panoramax (`https://api.panoramax.xyz/api/search?bbox=<w>,<s>,<e>,<n>&limit=20`, STAC items
  with `assets.sd.href`) and Wikimedia Commons
  (`https://commons.wikimedia.org/w/api.php?action=query&list=geosearch&gscoord=<lat>|<lon>&gsradius=80&gsnamespace=6&format=json`,
  then `prop=imageinfo&iiprop=url|extmetadata` for author and licence). Keep a handful within
  about 60 m of the start, look at them beside `sheet.png`, and write each one's author and
  licence in the notes. Refused (a 403 from the proxy) means the hosts are not allowed yet:
  say so in one line of the notes and go on with the map data.
- No real business on a fascia (the check allows only the generic trades of `draft.py`), no
  real person, no brand.
- The canon holds for every line a forged place adds: strangers and stallholders say vous,
  nothing agrees an adjective with Toi, Odile never speaks, «L.» is never named.
- One place a run. Never push to main, never merge, never deploy. The owner merges.
