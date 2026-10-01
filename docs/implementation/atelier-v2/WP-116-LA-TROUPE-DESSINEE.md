# WP-116 · La troupe dessinée: the drawn cast replaces the painted one

*Defined 2026-10-01. The owner chose variant C («rond») on the Claude Design canvas
claude.ai/artifact/6Lr278xt6RDmRhYHDwt8WS and asked for every old character image to be
replaced, with the old set kept so it can be swapped back.*

## 1. Goal

Every person the learner sees in the app becomes a **drawn, animatable SVG character** (a "rig").
The **painted location plates stay** as backgrounds. A panel becomes *plate + who + mood + what they hold*,
drawn in the client at no image cost, and the characters can blink, speak with moving mouths and react.

The painted set (portraits, model sheets, panel art with people) is **kept intact and one switch away**
until the owner has played the drawn set and says yes. Removal is the last phase and needs that yes.

**Non-goals.**
- No change to any plot point, line or character in `docs/story/season-1/`.
- No new fonts or UI colours. Character skin and hair tones live inside the rigs only.
- Toi is never shown face-on.
- No paid image calls. Drawn mode switches panel-art generation off.

## 2. What exists today (inventory of 2026-10-01, HEAD a41d9b1)

### Painted character files (tracked)
- `web-frontend/public/assets/serial/characters/`: 31 files, 1.3 MB.
  - 6 cast members × `portrait-{neutral,happy,cross,moved}.webp` + `model-sheet.webp`.
  - `user/model-sheet.webp`.
- `web-frontend/public/assets/serial/scenes/{arrange_meeting,explain_delay,order_at_cafe}/panel-1..4.webp`: 12 files, 3.6 MB of authored panels with people.
- `docs/design-reference/cast/<id>/{reference,happy,cross,moved}.webp`: 24 files, 2.6 MB. These are the references the panel-art pipeline uploads.
- Untracked runtime art: `var/graphic-novel-images/scenes/**` (183 MB).
  - The `.webp` files are generated panels.
  - The `.svg` files are the legacy `_fallback_svg` stick figures.

### Plates (stay)
- `web-frontend/public/assets/serial/locations/*.webp`: 12 files.
- `app/services/season/world.py:23-55` (`SEASON_ONE_LOCATIONS`, `plate_for`).

### The seams
- **Faces.** Almost every face goes through:
  - `portraitSrc()` (`web-frontend/lib/onboarding-portraits.ts:29`);
  - `faceSrcFor()` (`lib/cast-faces.ts:108`);
  - rendered by `CastPortrait` (`components/atelier-v2/ui/CastPortrait.tsx:45`) or `Feedback.Portrait` (`components/atelier-v2/ui/Feedback.tsx:234`).
- **Faces that bypass the seam:**
  - `components/feuilleton/archive/Trombinoscope.tsx:154`;
  - `pages/audio-session.tsx:670`;
  - `pages/vocabulary/review.tsx:358`;
  - backend `model_sheet_url`/`portrait_url` from `app/services/serial.py:2236`;
  - push icons from `app/services/serial_notifications.py:306`.
- **Panels.** The seam is:
  - `components/atelier-v2/journey/story-episode-model.ts:281-315` (`imageUrl`, `artStatus`, `SHOWN_ART`, and `panelReaderVariant`, which needs art for a bubble);
  - `components/feuilleton/reader/FeuilletonReader.tsx:783,875-905` (`PlateArt`).
- **The gap.** A drawn panel loses its plate URL:
  - `panel_art._write_back` overwrites `image_url` (`app/services/panel_art.py:612`);
  - `journey_content.authored_panels` swaps in the scene file (`:1218`);
  - `public_scene` emits no `location_id` (`app/api/v1/endpoints/story_engine.py:~120`).
- **Flags.**
  - Backend: `ATELIER_PANEL_ART_ENABLED` (default off), `GRAPHIC_NOVEL_IMAGE_GENERATION_ENABLED`.
  - Frontend: only `web-frontend/launch-flags.json` (build-time) and localStorage preferences (`lib/app-preferences.ts`).
  - There is no runtime config endpoint. Server toggles reach the client as payload fields.

## 3. Safekeeping first (phase 0, before any code changes the look)

1. **Tag the painted state:** `git tag art-painted-2026-10-01 <commit>` on the commit before phase 1 lands. Local tag only, no push without the owner.
2. **Write a manifest** of the painted set: `docs/art/painted-set-2026-10-01.json`.
   - It lists every file in §2 (path, bytes, sha256).
   - It also lists every code path that reads them.
3. **Add a script, `scripts/art/art_set.py`, with three commands:**
   - `verify`: every painted file in the manifest is present and unchanged.
   - `restore`: brings any missing painted file back from the tag with `git show art-painted-2026-10-01:<path>`. It never runs `checkout`, `stash` or `reset`, because the checkout is shared.
   - `report`: lists which surfaces render painted and which render drawn under the current switch, read from the registry in §4.3.
4. **No painted file is moved or deleted in phases 1–5.** Both sets ship side by side.

## 4. The switch

### 4.1 One value, two places
- **Frontend.** `artSet: 'painted' | 'drawn'` in `web-frontend/launch-flags.json` sets the build default. A localStorage override, `atelier.artSet`, lets the owner flip it on a device without a rebuild.
  - Both are read in **one module**, `lib/art-set.ts`, through `useArtSet()` and `artSet()`.
  - No component reads the flag directly.
- **Settings.** A row in Settings › Affichage: «Personnages : dessinés / peints». It is visible while both sets ship and goes away with phase 7.
- **Backend.** `ATELIER_ART_SET` in `app/config.py`, values `painted` (default until the owner's yes) or `drawn`. When it is `drawn`:
  - `panel_art.enabled()` returns False, so there are no paid panel calls and every panel keeps its plate;
  - payloads still carry the painted URLs for the painted switch, plus the new fields from §6, so the client can render either set from the same payload;
  - push icons use the drawn PNG snapshots from §5.4.

### 4.2 Switching back
- **On a device:** Settings, or delete the localStorage key. This takes effect at once, because both sets are in the bundle.
- **For everyone:** set `artSet: 'painted'` in `launch-flags.json` and `ATELIER_ART_SET=painted`, then redeploy.
- **After phase 7 (removal):** run `scripts/art/art_set.py restore`, flip the two values, and redeploy.

### 4.3 Registry of surfaces
`lib/art-surfaces.ts` lists every surface that shows a person: its id, its component, and whether it renders through the seam. A unit test fails if a component imports `portraitSrc`, `faceSrcFor` or a `/assets/serial/characters/` path outside `lib/art-set.ts` or the two seam components. This is the guard against stragglers.

## 5. Phase 1: the rig library

Port the canvas rigs (`.dc.html`, kept in the session scratchpad and to be copied into `docs/design-reference/drawn-cast/`) into React.

### 5.1 Layout
- `web-frontend/components/cast/` contains:
  - `CastRig.tsx`, the public component;
  - `rig-face.ts`, the shared eyes, lids, brows and six mouth shapes;
  - `rigs/<id>.tsx`, the geometry for each character, kept as pure data and paths;
  - `cast-registry.ts`.

### 5.2 Characters and ids

| Rig | Cast id | Notes |
|---|---|---|
| Margaux | `margaux_barman` | |
| Marin | `marin_leveque` | |
| Lila | `lila_bonnet` | |
| Gus | `augustin_de_roncourt` | |
| Romy | `romy_tremblay` | |
| Marchand | `landlord_marchand` | |
| Camille | `camille_marchand` (new) | Two variants, chosen by the learner's Camille flag (§9) |
| Odile | `odile_ferrand` (new) | |
| Toi | `user` | Seen from behind only |

- `NO_PORTRAIT_TOKENS` in `lib/cast-faces.ts:38` loses camille and odile, because they now have faces.
- Minor characters keep the initial disc.

### 5.3 The `CastRig` component
- Props: `id`, `mood`, `mouth`, `blink`, `crop` (`full | bust | head`), `size`, `hold`, `variant`, `gaze`, `still`.
- **Moods:** `PortraitMood` maps onto rig moods, and `surprise` is added:

  | PortraitMood | Rig mood |
  |---|---|
  | `neutral` | `neutre` |
  | `happy` | `ravie` |
  | `cross` | `fachee` |
  | `moved` | `emue` |

- **Motion:** idle loops and blinks are CSS animations or Web Animations API calls scoped to the rig. **Never SMIL.** The canvas sketches use SMIL `<animateTransform>`, and nothing (not a media query, not the `still` prop) can stop it, so it breaks Reduce Motion and WCAG 2.2.2. The port converts every loop, including Romy's camera light.
- **Stillness:** under `prefers-reduced-motion`, and whenever `still` is set, every loop pauses and moods change instantly. The rig is still while the learner reads or types, and only one character moves at a time on ensemble screens.
- **Accessibility:** `role="img"` with `aria-label` set to the character's name and mood in the UI language.
- **Size:** the target is under 6 KB gzipped per rig, with the shared face module counted once.

### 5.4 PNG snapshots
`scripts/art/render_rigs.mjs` uses Playwright, which is already a dev dependency, to write `public/assets/serial/drawn/<id>/portrait-<mood>.png` and `bust-<mood>.png`. They serve three uses:
- push and notification icons;
- Open Graph images;
- any surface that must stay an `<img>`.

The script is rerun whenever a rig changes. A test checks that the snapshots exist for every rig and mood.

### 5.5 Tests
- A render test for every rig × mood × crop.
- Mood mapping.
- The reduced-motion class.
- The registry guard from §4.3.

## 6. Phase 2: faces everywhere

- `CastPortrait` and `Feedback.Portrait` branch on `useArtSet()`. In drawn mode they render `<CastRig crop="head">` inside the same round disc, at the same xs/sm/md/lg sizes (30/40/64/112) and with the same accent ring.
- The stragglers get the same branch:
  - `Trombinoscope.tsx:154`;
  - `audio-session.tsx:670`;
  - `vocabulary/review.tsx:358`;
  - `CastIntro.tsx` and `Taste.tsx` in onboarding.
- **Backend (additive).** Cast payloads gain `cast_id` wherever only a URL travels today, so the client can choose the rig:
  - `model_sheet_url` (`serial.py:1072`);
  - `portrait_url` (`vocabulary.py:670`);
  - push payloads.
- **Pushes.** In drawn mode `serial_notifications.portrait_path` points at the PNG snapshots.
- **Surfaces covered**, from the inventory:
  - reader faces, RespondThread, ReplyStage, JourneySteps, JourneyTodayCard headline cast;
  - HeardLine, WhoSaid, JourneyRecap, SeasonPages, RuleCard;
  - Épreuve, Forge, ForgeFollowUp;
  - Courrier, Correspondance;
  - Cahier (CarnetTab, GrammarMap);
  - Trombinoscope, TodayEpisode, SeasonPage;
  - onboarding, voice call, Home (`pages/atelier.tsx:4536`), HomeScreen, LaUne, the vocabulary review anchor.

## 7. Phase 3: panels drawn as plate plus rigs

### 7.1 Backend (additive, no field removed)
- `StoryPanelRead`, `StoryPageRowRead` and `ScenePanel` gain three fields:
  - `plate_url`: always the location plate, even after `panel_art` drew the panel;
  - `location_id`;
  - `stage`: `[{cast_id, mood, speaking, hold?, facing?}]`.
- **Where `stage` comes from:**
  - the panel's speakers and line moods, already in `story_projection` lines;
  - plus who is in frame, from `panel_art.characters_in_panel` (`:429`), which already decides this for the image prompt.
- **Season tentpoles:** stage from the authored page rows (`app/services/story_page.py`).
- **Authored scenarios:** a `stage` per panel in `app/data/journey_scenarios/*/` next to `image_asset`, filled once by a script from each panel's speakers and checked by a test.
- `public_scene` emits `location_id` and `plate_url`.
- `TodayEnvelope.headline` gains `stage`, the cast for the La Une header.
- Regenerate the generated TS types with `npm run types:generate`.

### 7.2 Frontend
- **`PlateArt`** (FeuilletonReader) and the story-episode model: in drawn mode the panel draws `plate_url` plus the `stage` rigs (crop `bust`). The layout rules are:
  - at most 3 people per panel;
  - the speaker is in front, bigger, and faces the listener;
  - others stand behind, offset upwards;
  - Toi is seen from behind in the bottom corner when the panel carries Toi's line;
  - silent panels show the cast without mouth movement.
- In drawn mode `artStatus` is `ready` whenever `plate_url` exists, so speech bubbles render (`panelReaderVariant`). The walk check `page-draws-your-line` (`e2e/walk.mjs:153`) keeps passing.
- **Other surfaces composed the same way:**
  - the La Une header (`JourneyTodayCard`, `LaUne`, `HomeScreen`, `pages/atelier.tsx` `serialLeadImageUrl`);
  - the season poster (`SeasonPages`, `season-return-model.ts:177`);
  - archive thumbnails (`FeuilletonArchive.tsx:507,650`);
  - recap vignettes (`achievement_recap.py:208`);
  - the scene prompt art (`JourneySteps.tsx:394`).

## 8. Phase 4: speech and motion (the minimum, before WP-117)

- **Lip-sync.** While a line's audio plays, the speaker's mouth runs through the six visemes. Each shape follows the audio's playback position (`currentTime`), not a fixed timer, so it stays in sync on long lines and slowed replays.
  - If the TTS provider returns word or phoneme timings, use them.
  - Otherwise use a French grapheme-to-viseme approximation (`lib/visemes-fr.ts`), spread over the audio's duration.
  - Stop when the audio stops.
- **Blink and idle** for each character, as on the canvas: Lila bounces, Gus sways, Marchand nods, Romy's camera light blinks. All of it stops under reduced motion.
- **Exercise reactions** use only the mood switch:
  - a right answer → the character's happy mood;
  - a wrong answer → surprise, never cross. Today's `WhoSaid` turns the face cross on a wrong pick; that changes here.

  The rest of the interactivity is WP-117 (§11).

## 9. Decisions for the owner

1. **Camille's look before the learner sets Camille's gender (T1 Day B).** Proposed: show neither variant until then. Camille is seen from the side or with the helmet in front of the face, as T1 P8 already stages it.
2. **Odile on screen.** She now has a face. Proposed: only in Polaroid frames and flashbacks, as the bible says, never as a speaking avatar.
3. **Push icons.** Proposed: drawn PNG snapshots in drawn mode.
4. **When to remove painted files from the iOS bundle.** About 5 MB. Proposed: phase 7 only.
5. **The authored scenes** (`scenes/*/panel-N.webp`) have no plate of their own. Proposed: in drawn mode they fall back to the scenario plate plus `stage`.

## 10. Phases, order and verification

| Phase | What | Done when |
|---|---|---|
| 0 | Tag, manifest, `art_set.py verify/restore/report` | `verify` passes; `restore` tested on a temp copy |
| 1 | Rig library, PNG snapshots | Rig tests green; snapshots for 9 rigs × 5 moods |
| 2 | Faces on every surface behind the switch | Registry guard green; walk screenshots of every surface in **both** sets |
| 3 | Backend `plate_url`/`location_id`/`stage`; reader, La Une, archive, poster | Backend tests for the new fields; walk on the test copy shows people in every season panel |
| 4 | Lip-sync, blink, idle, reduced motion | The owner plays T1 on the test copy |
| 5 | Drawn mode on for the test copy (`ATELIER_ART_SET=drawn`) | The owner plays several days and decides |
| 6 | Default flips to drawn | The owner's yes |
| 7 | Removal: painted files move to `_archive/painted-2026-10-01/` and leave the native export; the Settings row goes | The owner's second yes; `restore` documented in `docs/art/README.md` |

**Every phase must:**
- extend the walk harness to screenshot both art sets (`ART_SET=painted|drawn`, side-by-side contact sheet);
- check the screenshots of every changed surface;
- run the backend and frontend suites;
- report files, commits, test counts before and after, and deferrals.

The shared-checkout rules hold:
- commit only your own paths with `git commit -- <paths>`;
- never use checkout, stash or reset;
- no pushes or deploys.

**Tests that change on purpose** (from the inventory):
- They assert painted paths and must assert the switch instead:
  - `lib/onboarding.test.js:30,186`;
  - `cast-reacts.test.js`, `feel-faces.test.js`, `journey-recap.test.js`, `forge-coach.test.js`;
  - `story-episode-model.test.js` (art status), `reader-render.test.js`;
  - backend `test_forge_coaches.py:55`, `test_serial.py:1430`, `test_wp80_pushes.py`, `test_wp99_facteur_depeches.py`, `test_season_one.py:631,657`.
- The painted assertions stay as painted-mode cases.

## 11. Next: WP-117, interactive characters

WP-117 is in `WP-117-LA-TROUPE-QUI-BOUGE.md`. It holds:
- principles for when the cast moves;
- a signature-move sheet for all nine characters;
- interaction patterns mapped to the recall ladder;
- the rig capabilities to add;
- a runtime recommendation: stay on inline SVG with CSS and the Web Animations API, not Rive;
- six interactions to ship first.

WP-117 starts after phase 3 of this package. Phase 1 must already expose `gaze` and a `hold` prop on every rig, so WP-117 needs no second pass through the rigs.

## 12. Where this is heading: generated seasons (owner, 2026-10-01)

**The vision.** Season 1 is authored and close to deterministic. The target app generates its seasons and episodes itself, from:
- how the learner plays;
- how the learner treats each persona;
- real news, facts and culture about the country and the city.

That is the version to build toward. Three consequences hold for this package now.

1. **Image generation stays.** Nothing in `panel_art.py`, `scripts/art/atelier_art.py`, the plate pipeline or the S3 storage is deleted.
   - Drawn mode switches off *per-panel character drawing* only.
   - New places still get a painted plate from the image model. A plate is drawn once per place, cached and reused, so it costs cents per location, not per panel.
2. **A panel is data, not a picture.** The `stage` field from §7 is the first version of a stage language that the story engine writes, and its first fields are `location`, `cast_id` and `mood`. It is designed to grow without breaking:
   - `pose` and `gesture`: point, shrug, bow, dance, sit, lean;
   - `hold`: any prop id;
   - `gaze`: who looks at whom;
   - `action`: an entry, an exit, or a one-shot like Gus's cards falling;
   - `objects`: things on stage with an optional event, such as `{"id": "wine_glass", "at": "table", "event": "falls"}`.

   The rig library and every surface render only what they know and ignore the rest. An engine that writes a gesture the client can't draw yet degrades to the mood alone.
3. **Props and objects become a library that can grow at runtime.** These are tiers to plan for, not to build in WP-116:
   - **Authored props:** SVG in the rig style (glass, cup, key, letter, camera, notebook), each with named states (`full`, `empty`, `broken`, `falling`).
   - **Generated props:** a language model writes an SVG for an object the story needs, constrained to the house grammar: the palette, no outlines, round construction, a fixed viewBox and a handle point. A validator checks it before anything is shown, then it is cached and reused for every learner. If an object fails validation it is dropped from the panel; the plate and the cast still tell the story.
   - **Generated plates:** the image model paints a background for a new place, a market or a museum the news brought in, in the plate style lock that already exists.

**The guardrails stay what they are for the story:**
- canon over cute;
- the no-spoil gates;
- one validator per generated thing;
- an authored fallback that always works.

## 13. Status

| Phase | Commit | What landed |
|---|---|---|
| 0 | b377401 | Tag `art-painted-2026-10-01`, the painted-set manifest (67 files), `scripts/art/art_set.py` |
| 1 | 6b126a4 | `web-frontend/components/cast/` (9 rigs, CastRig), `lib/art-set.ts`, `styles/cast-rig.css`, PNG snapshots |
| 2 | 4a74d66 | Faces behind the switch; Settings › Personnages; Camille's look from `headline.cast_variants`; `ATELIER_ART_SET` (pushes use the drawn PNGs, paid panel drawing off) |
| 3 | (this commit) | Panels: `plate_url` on every panel and page row (kept when a drawing replaces `image_url`); the reader draws the plate plus the speakers (`components/cast/PanelStage.tsx`); the walk checks `page-draws-the-cast` under `WALK_ART_SET=drawn` |

**Phase 2 in detail.**
- The faces in `CastPortrait`, the av2 `Portrait`/`Byline`, the Trombinoscope card, the voice call and the vocabulary anchor render `CastFace` (the rig, head crop) when the set is drawn.
- `art-surfaces.test.js` fails if any component or page builds a painted face URL without `useArtSet()`.
- **Odile** gets a drawn face.
- **Camille** gets one only once `headline.cast_variants` carries the learner's T1 Day B choice. Before that Camille keeps the initial, and is never shown with the grandfather's face.
- **Deferred to phase 3:** panels, the La Une picture, the season poster, archive thumbnails.
- **Deferred to WP-117:** the verdict mood. A wrong answer still maps to `cross`.

**Phase 3 in detail (2026-10-01).**
- **Who stands on a panel:** the panel's speakers, in order, the first one in front, at most three.
- **Toi:** stands from behind in the corner when the learner speaks in a panel without a balloon.
- **Sizing:** figures are sized by the panel's height with a head-anchored 180 × 220 crop, so faces keep one size in square and wide frames.
- **Camille:** stays off stage until the learner has chosen Camille's look.
- **Silent panels:** have no speakers, so they show the plate alone.
- **Deferred:**
  - the La Une picture, the season poster, archive thumbnails and the finale art, which are still the painted plate or drawing;
  - a backend `stage` for people who are in frame without speaking;
  - the wrong plate on the first T1 panel (the market instead of the quai de Valmy). That one is a season-location mapping issue that existed before WP-116.
