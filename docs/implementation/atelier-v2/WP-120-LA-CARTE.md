# WP-120 · La Carte: where it happened, and the vignette you bring back

*Defined 2026-10-02 from the owner's idea: every Papier (WP-119) names a place; the learner should be
able to see those places on an interactive map of France, open each one and remember what happened
there; and every Papier should end with a creative, freshly generated vignette (the owner's word was
«batch», read as the stamp a traveller brings back). Builds on WP-119 (places on dossiers, the stage,
the Relevé entry) and WP-116 §12.3 (generated SVG props in the house grammar).*

## 1. Goal

**La Carte** is the learner's memory of France as a map: every place a Papier took them to is a
pin, and a pin opens what happened there in French: the headline, the words they kept, the dispatch
or the question they wrote with Romy, the plate. Most pins will land in Paris, so the map is a map of
France with a Paris that opens up.

**The vignette** is what the learner brings back from each Papier: a small stamp in the house style
with a pictogram of the one thing the story was about (a vine, a ballot box, a galette), the place
and the week. It is the pin on the map and a seal in the Relevé's collection. It is generated once
per story, shared by every learner who reads that story, and made personal by what the learner did
with it, not by another model call.

**What it is not.** Not a trophy wall or a score. A pin is a memory, so it always opens the French
first. No XP, no "collect them all". Season 1's places (Le Mistral, the quai de Valmy, the Buttes-
Chaumont) can appear as a quiet second layer, «Mon quartier», so the learner's fictional and real
France share one map, but the season's pins carry no vignette and never spoil (they appear only for
places already visited).

## 2. What exists today

- **Places on dossiers.** `EditorialDossier.places[]` with `id, name_fr, brief, known` (WP-119
  §3.1); the W40 and evergreen dossiers name real places (place d'Aligre, Longchamp, the hémicycle).
  There is **no geo field** anywhere: not on dossiers, not on `SEASON_ONE_LOCATIONS`
  (`season/world.py:23`), not in `world.json` `setting_locations`.
- **Sessions.** `revue_sessions` rows hold the plan (place id) and the state (with a dossier
  snapshot); closed sessions are the learner's Papier history (WP-119 phase 1).
- **Seals.** `app/services/seals.py` (`edition_numbers`, `seal_variant_for`), the tutoiement seal
  minted by `story_archive.mint_tutoiement_seal`, and the Relevé's `SealCollection.tsx` with its
  four-week grid (`seal-collection-model.ts`). A seal is a kind + a variant today; it has no picture
  of its own.
- **Generated SVG in the house grammar.** Specified in WP-116 §12.3 (tier 2: a model writes an SVG
  constrained to palette, no outlines, round construction, fixed viewBox; a validator; cached), **not
  built yet**. This package builds it, for the vignette's pictogram.
- **Map libraries: none.** No d3, leaflet, maplibre or topojson in `web-frontend/package.json`, and
  no design reason to add one: the map is a drawing in the av2 style, not a tile map.
- **Design system.** The Bauhaus mark, EB Garamond + Instrument Sans, the av2 colour roles
  ([[design-proposals-stay-in-av2]]). The map and the vignette use nothing else.

## 3. Geo: a place gets coordinates

### 3.1 The field
`Place.geo: {lat: float, lon: float, precision: "exact" | "city" | "region", label_fr: str}` on the
editorial dossier (optional, so the W40 and evergreen files gain it in a data migration). `label_fr`
is the place as the map prints it («Place d'Aligre, Paris 12e», «Hippodrome de Longchamp»).

### 3.2 Where coordinates come from, in order
1. **The gazetteer** `app/data/geo/gazetteer.json`: a hand-kept table of the places a French-news
   kiosk returns to (national institutions, Paris landmarks and markets, the 20 arrondissement
   centroids, the 13 regions and the 101 prefectures, the big stadiums and racecourses, the
   Christmas markets, the wine regions). Matched by folded name and aliases. Precision `exact` for a
   landmark, `city` for a prefecture, `region` for a wine region.
2. **The builder's proposal**, when the model names coordinates for a place it knows. Accepted only
   if it lands inside the France bounding boxes (metropolitan and each overseas department) and,
   when the gazetteer knows the same city, within 25 km of it. Precision `exact`.
3. **The city centroid** from the gazetteer when only a city is known. Precision `city`.
4. **No geo**: the place is `region`-less and the Papier shows no pin; the dossier is still valid.
   The intake logs `revue_place_without_geo` so the gazetteer grows.

### 3.3 The season's places
`SEASON_ONE_LOCATIONS` gain `geo` the same way, by hand: they are all in the 10e around the canal
Saint-Martin, plus the Buttes-Chaumont, the gare de l'Est and the brocante. They appear on the map
only once the learner has been there in the story (`story_archive` knows), under «Mon quartier».

### 3.4 The Geo check (one more check on meaning, WP-119 §4.2)
Inside France (metropolitan or an overseas department); not the exact centroid of Paris with
precision `exact` (the model's favourite lie); consistent with the brief's named city when there is
one. Fails → precision downgraded to `city`, then dropped.

## 4. The vignette

### 4.1 What it is made of
A **composed** stamp, not a single generated image:
- **Frame (authored, client-side SVG):** a circle in av2 ink with a thin inner ring; the week number
  on the ring in Instrument Sans; the place label beneath in Garamond. Three ring colours by what
  the learner made: ink for a headline, blue for a reader question, red for a short report. A small
  mark on the ring when the learner's contribution was kept in the dispatch. This is where the
  vignette becomes *theirs*, at zero cost.
- **Pictogram (generated once per dossier):** one object that stands for the story, chosen by the
  dossier builder (`dossier.vignette_object_fr`, e.g. «une grappe de raisin», «une urne», «une
  galette avec sa fève») and drawn by the model as SVG in the house grammar. Shared by every learner.
- **Fallback (authored):** seven topic pictograms (food, culture, city, sport, nature, work,
  politics) in the same grammar, used when generation fails validation twice.

### 4.2 The house grammar and its validator (`revue/pictogram.py`)
The model is asked for an SVG with: `viewBox="0 0 100 100"`, 3 to 12 `<path>`/`<circle>`/`<rect>`/
`<ellipse>` elements, fills from the seven av2 inks only, no `stroke` except ink at width 0 to 6, no
text, no gradients, no `<image>`, no `<script>`, no `<style>`, no `xlink`, no filters, no ids, total
≤ 2 KB, bounding box inside the circle of radius 40 around (50,50), and "round construction": every
path must be closed and use only `M L C Q Z` commands. The validator parses with `defusedxml`,
whitelists tags and attributes, snaps any off-palette colour to the nearest ink (one tolerance
pass, logged), and rejects on anything else. One regeneration with the error named, then the
fallback. Validated pictograms are stored in `revue_pictograms(dossier_id pk, object_fr, svg,
prompt_version, validated_at)` and served inline. Cost: one small text call per story, ever.

### 4.3 Minting
At `close` (WP-119 encounter), the service mints `revue_vignettes(id, user_id, session_id,
dossier_id, ring: headline|question|report, kept_contribution: bool, minted_at)` and the Relevé's
seal collection gets a new seal kind `vignette` whose picture is the composed stamp. The close screen
shows it being stamped (a 300 ms press, reduced-motion aware) before «Classer le Papier».

## 5. The map

### 5.1 The drawing
An SVG map of France in the av2 style, shipped as static assets, no runtime library:
- `public/assets/carte/france.svg`: the 96 metropolitan departments as simplified paths (built
  offline from a public-domain GeoJSON with a small script in `scripts/geo/build_carte.py`;
  Lambert-93 projection; ~120 KB), the sea in paper, land in a paper tint, borders in a hairline of
  ink. Corsica in place; the five overseas departments as small boxes along the bottom edge in the
  French cartographic convention.
- `public/assets/carte/paris.svg`: the 20 arrondissements and the Seine, same construction.
- `public/assets/carte/idf.svg`: Île-de-France departments for the middle zoom.
The projection constants for each drawing (`lon/lat → x/y` as a 6-number affine on top of the
Lambert-93 formula, computed by the build script) ship as `carte-projection.json`, so pins are placed
client-side from `geo` without a geo library.

### 5.2 Levels and pins
Three levels, one component `Carte`: France → Île-de-France → Paris. A tap on a cluster zooms one
level; «France» in the corner zooms out. Pins are the vignettes at 28 px, clustered when they overlap
(a cluster shows the count on a plain ink disc). Precision `city` pins sit on the city with a dotted
ring; `region` pins sit on the region's centroid with a wider dotted ring. The season layer «Mon
quartier» toggles from the Paris level only.

### 5.3 The card
A pin opens a bottom sheet (`Sheet` from the av2 ui): the vignette large, the week and place, the
headline in French, the kept words as tokens (tap → WordHelpSheet), the dispatch or the question
with the learner's contribution marked, the plate as a band, and two actions: «Relire» (read-only
replay of the session's thread, reusing `RvEncounter` in a read-only mode) and «Dans le Relevé».

### 5.4 Where it lives
- `/carte`, an own-shell av2 page, reached from: the close screen of a Papier («Voir sur la carte»),
  the Relevé's «Le Papier» section (a small France silhouette with the pin count), and Settings'
  Bibliothèque row. No tab: the map is an archive, not a daily surface.
- `GET /revue/carte`: the learner's pins (closed sessions with geo), the season layer for visited
  places, counts per level. Pure read, cached per learner for a minute.

## 6. Phases and acceptance

| Phase | What lands | Done when |
|---|---|---|
| **A · Geo** | `Place.geo`, the gazetteer (≥ 150 entries), the four-step resolution, the Geo check, geo on the W40 and evergreen files and on `SEASON_ONE_LOCATIONS`, `revue_place_without_geo` logging | every W40 and evergreen place resolves with precision `exact` or `city`; a builder centroid at Paris's centre is downgraded in test |
| **B · Vignette** | `pictogram.py` grammar + validator + storage, `vignette_object_fr` on the builder, seven authored fallbacks, minting at close, seal kind `vignette`, the composed stamp component `RvVignette`, the close animation | 12 evergreen pictograms generated and validated with the real model and reviewed by the owner (a contact sheet in `docs/design-reference/revue/vignettes/`); a hostile SVG (script, external image, off-palette) is rejected in test; a learner's ring colour follows their make option |
| **C · Carte** | the three SVG drawings and projection file (build script in repo), `Carte` with levels, clusters and pins, the card sheet, read-only replay, `GET /revue/carte`, `/carte` page, entries from close, Relevé and Settings | a learner with six closed Papiers (fixture) sees six pins, four of them clustered in Paris, opens one and reads the headline and kept words; phone width 390, light and dark, reduced motion |
| **D · Walk** | E-3 walk `carte-shows-where-i-was` on the fake provider; the owner's hands-on | the owner has opened their own map |

## 8. Phase D in detail: the entry points and the walk (one lead, about 1.5 hours)

- **Entry points** (frontend lead; lease `components/revue/RvClose.tsx`, `components/releve/Releve.tsx`,
  `pages/settings.tsx`, `components/carte/CarteBadge.tsx` new):
  - the close screen gets «Voir sur la carte» as the quiet secondary under «Classer le Papier»,
    linking to `/carte?focus=<session_id>` (the page opens the pin's card on load; add the `focus`
    parameter to `pages/carte.tsx`);
  - the Relevé's «Le Papier» section (phase 3 of WP-119 builds the section; until then, a row after
    Le Registre) shows a small France silhouette `CarteBadge` with the pin count from
    `GET /revue/carte` counts, linking to `/carte`;
  - Settings › Bibliothèque gets a «La Carte» row.
- **Invalidate** (backend; lease `app/services/revue/encounter.py` close): call
  `carte.invalidate(user_id)` after minting so the new pin shows at once.
- **Walk**: E-3 harness check `carte-shows-where-i-was` on the fake provider: close one Papier via
  the mock-free path on `backend-e2e`, open `/carte`, assert one pin at the dossier's coordinates
  and the card's headline; phone size, light and dark, reduced motion. Screenshots into the walk's
  evidence folder.
- **Owner's hands-on**: the package is done only when the owner has opened their own map (process
  rule in the running log).

## 7. Decisions for the owner
1. **Overseas departments** as boxes along the bottom (recommended), or metropolitan France only.
2. **«Mon quartier»** season layer in the first version (recommended: yes, it ties the two Frances).
3. **Open sessions on the map**: only closed Papiers pin (recommended), or an active one as a hollow pin.
4. **The name**: «La Carte» (recommended), «Mes lieux», or «L'atlas».

## 9. Status

| Phase | Commit | What landed |
|---|---|---|
| A | ab42eda | `Place.geo`, `geo.py` (four-step resolution, 240-entry gazetteer in `app/data/geo`), `check_geo`, geo on every evergreen/W40 place and on `SEASON_ONE_LOCATIONS`; 17 geo tests. 13 gazetteer entries marked `verify: true` |
| B | ab42eda + 148e2ee | `pictogram.py` grammar + validator, seven authored fallbacks, `revue_pictograms`/`revue_vignettes` (migration d4f6a8c0e2b4), `mint_for_close` wired into the encounter's close with `closing.vignette`, `GET /revue/vignettes`, `RvVignette` at close and in the Relevé's seal collection; twelve evergreen pictograms by the real model (11 first try, US$0.034), `docs/design-reference/revue/vignettes/`. Weak: bac, guitar, maillot jaune, fireworks |
| C | 8834764 | `scripts/geo/build_carte.py` (Lambert-93, Etalab Licence Ouverte sources), `france.svg` 115 KB / `idf.svg` 27 KB / `paris.svg` 11 KB + projection file, `GET /revue/carte` (closed sessions, «Mon quartier» from visited season places, 60 s cache), `components/carte` three levels + clusters + pin card, `/carte` with `?mock=1`; 15 + 15 tests. Entry points and `invalidate()` at close: phase D |
| D | (this commit) | «Voir sur la carte» on the close screen (`/carte?focus=`), `CarteBadge` in the Relevé's «Le Papier» section, the Settings row, `carte.invalidate()` at close; walk `carte-shows-where-i-was` passed against the real stack (8 checks, pin at the hémicycle within 0.1 svg unit). Owner's hands-on pending |
