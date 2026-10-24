---
name: quartier-forge
description: Build the next corner of Paris for Le Quartier from open map data. Pick a place the Papier names, survey it, draft the site (a street with its trade, or a venue where the news happens), render and critique it (three rounds at most), publish it on the map and open a PR. Never merges. Use for the nightly "Quartier forge" scheduled task, or when asked to "forge <place>", "build <place> in the Quartier" or "grow the world".
---

# Quartier forge

Le Quartier's Paris is not built all at once. The quai de Valmy and Le Mistral are drawn by
hand; every other place is forged when the news or the story names it. A place the news names
is on the map the moment its article is (`forge.py news` writes the news layer, pinned under
scaffolding); the forge then builds it. One run builds one place:

```
queue → world entry → brief → survey → draft → check → plan → render → look → notes
      → revise (back to draft, three rounds at most) → publish → tests → PR
```

The code is `scripts/forge/` (Python: `forge.py`, `overture.py`, `draft.py` for a street,
`venue.py` for a venue) and `web-frontend/lib/quartier/` (the kit that builds a site in 3D,
`visit.ts` that plays a street, `market-talk.ts` for what the stallholders say; `hippodrome.ts`,
`course.ts` and `course-talk.ts` for race day). `scripts/forge/briefs/marche_aligre.json` and
`.md` are the worked example of a street, `hippodrome_longchamp.json` and `.md` of a venue:
read the pair that fits before writing a brief.

## Setup

```
python3 -m venv ~/.venvs/forge && ~/.venvs/forge/bin/pip install -r scripts/forge/requirements.txt
export PY=~/.venvs/forge/bin/python
```

In a cloud session, prefix network commands with `REQUESTS_CA_BUNDLE=/root/.ccr/ca-bundle.crt`.
The survey reads Overture's public bucket (`overturemaps-us-west-2.s3.us-west-2.amazonaws.com`).
The renders need `web-frontend/node_modules` and a Chromium (`/opt/pw-browsers/chromium` in
the cloud; never run `playwright install`).

## The run

1. **Pick.** `$PY scripts/forge/forge.py news` refreshes the map's news layer
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
   give masculine names short hair and no earrings unless the brief says otherwise). A venue's
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
   about 2.5 s here?
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
   every site to the forge's checks, `market-talk.test.js` to the canon), `npx tsc --noEmit -p .`,
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
