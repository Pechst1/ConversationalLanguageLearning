# Work packages — 2026-09-22 (design): the shapes do the work

Owner brief: make the app beautiful, lean, aesthetic and cute **without abandoning the design
that exists**: keep the geometric forms, the logo, the fonts and the colours. These packages
follow `WORK-PACKAGES-2026-09-22.md` (WP-69..85) and sit in its Wave C/D. They are numbered
**WP-D1..D8** (D = design) because the plain sequence continues elsewhere (WP-86/87 are the
story-engine packages in `WP-86-87-ENGINE.md`).

Design reference: the Claude Design canvas «L'Atelier — cute & lean, inside the system»
(claude.ai/artifact/JWrAXjcpRnZtgAQmSdyWxm): eight phone boards and a kit board. The resolved
design stays `docs/design-reference/claude/Atelier App.dc.html`.

## Rules every package follows

- **Nothing new in the palette or type.** Only `--av2-*` tokens (light and dark), EB Garamond
  italic for the one headline per screen, Instrument Sans for everything else, sentence
  case, no tracked caps. Character accents only through the existing `--char-*` tokens.
- **The four shapes keep their meaning** (`ui/Shapes.tsx`): blue circle = story, yellow
  square = reward, red triangle = action, ink square = done. A shape is always paired with
  a word or an accessible name.
- **One 3D-press primary per screen**, 16–24 px rounded surfaces, 44 px tap floor.
- **Cute comes from the cast and what exists:** the cast portraits, the Seal, ReactForm. No
  mascot, no confetti. The one illustration style is the owner-approved screen print of
  WP-D8, for characters and places alike.
- Every motion respects Reduce Motion. Both themes and three learner languages are walked
  before a package is closed.

## Packages

#### WP-D1 · The mark is the day's plan
The logo's four shapes are the day's four parts, and they fill in as the learner goes:
`scene` → blue circle, `recall` → yellow square, `respond` → red triangle, `resolution` →
ink square (see `journey_contracts.py:77-81` and `:575-583`).
- A pure helper `dayMarkState(journey)` (next to `journey-state.ts`) returns each
  group's state: `done | active | todo | absent`. A group is done when all of its steps are
  `completed|skipped`. `absent` covers a day shape with no recall steps (check
  `short`/`reprise`) and draws in `--av2-line`, never as an outline.
- `AtelierMark` (`ui/Shapes.tsx`) takes an optional `progress` prop. A done shape is
  filled in its colour. A todo shape is the same solid shape in `--av2-line` (a "ghost").
  **No shape is ever outlined or given an ink stroke** (owner, 2026-09-22). A shape that
  fills does so with `at-pop`. Its accessible name is «Aujourd'hui : 2 sur 4 — …».
- Home (`HomeScreen.tsx:185-205`): the mark grows from 26 to 44 px and carries today's
  progress. Under the primary action, one row of four shape + word labels (Scène · Mots ·
  Réponse · Bouclé) replaces the `DayTile` grid (`:264`, built at `atelier.tsx:2392-2434`).
  This serves WP-81's element budget.
- Session head: the mark sits in the empty right-hand slot that
  `JourneySession.tsx:183-197` reserves, and pops when the respond step is accepted.
- **Decided (owner, 2026-09-22):** the mark is the day's only gauge, so WP-79's "daily goal
  ring" is not built. Minutes stay a line of text.
- **Done when:** unit tests cover `dayMarkState` for each of the five day shapes and an
  `ended_early` day. At 375 px, Home shows the mark with the right fill after each step in
  both themes, and nothing is announced by colour alone.

#### WP-D2 · The cast reacts (finishes WP-77 in the journey)
The portraits (commit 4a417dc) are used only in onboarding (`Taste.tsx:240`) and in
`CastIntro.tsx:55`.
- Move `CastPortrait` (`components/onboarding/Portrait.tsx`) and `moodForVerdict`
  (`lib/onboarding-taste.ts`) into `components/atelier-v2/ui` and `lib/`, with onboarding
  importing them from there.
- Respond step: the speaker is a `CastPortrait` (md, `--char-*` ring) beside the
  character's line, in the design's bubble shape (20/20/20/6 radius, card fill).
- Verdict (`JourneySteps.tsx:902-925`): the portrait swaps to `moodForVerdict(verdict)`
  with `at-pop`. The `FeedbackBand` stays as it is, with one line added under it:
  «Marin vous sourit ↑» on correct.
- Recap (`JourneyRecapView`, `JourneySession.tsx:497-627`): the `storyCallbackFr` line
  gets the portrait and the mood chip.
- **Done when:** every character line in scene → respond → verdict → recap has a face; a
  character without art falls back to the initial disc; there is no portrait in a card
  that has no character line.

#### WP-D3 · Progress tokens with faces
`StepProgress` (`ui/Surface.tsx:139-165`) draws neutral segments. It becomes one shape
per step, from the same step → shape mapping as WP-D1.
- Done steps are ink (ink = done). The active step shows its shape in its own colour with
  two eyes. Future steps use `--av2-line`.
- Port `ReactForm`'s faces (`components/ui/Seal.tsx:178`, CSS `globals.css:473-500`) into
  av2 CSS, dropping its 2 px ink stroke: the shapes are flat fills, with only eyes and mouth. On a verdict the active token grins (correct) or frowns (wrong) for ~600 ms,
  then settles. **Faces live only here.** They are never a mascot and never on buttons or
  cards.
- The count caption (`positionOnScreen`) stays for screen readers and is hidden when
  tokens are visible.
- **Done when:** a 3-, 5- and 8-step day render without wrapping at 320 px; the grin/frown
  is skipped under Reduce Motion; the tokens have an accessible label «Étape 3 sur 8».

#### WP-D4 · The Seal presses at the end of the day (the keepsake of WP-79)
The Seal already exists (`components/ui/Seal.tsx:85`, `sealForEdition`, the `seal-press`
keyframes) but only appears on the legacy reward layer (`pages/atelier.tsx:1888`).
- Rebuild `Seal` in the av2 language (owner, 2026-09-22: the legacy one is "too flat" and
  off-system). The disc is a card-face circle with the large press (`0 8px 0 --av2-line-2`),
  with no ink border and no offset shadow. The ring text is sentence case in Instrument
  Sans 600, `--av2-muted` («Atelier · le feuilleton» / «Nº 47 · 22 sept.»), without tracked
  caps. The centre is a paper well (inset `--av2-line`) holding the shapes, filled and with
  **no strokes**. Each shape sits on its own `*-deep` press, so the forms read as the 3D
  buttons do. The four-shape composition is the logo itself. The `SealMini` discs in the
  collection use the small press (`0 3px 0 --av2-line-2`), also without strokes.
  `sealForEdition` keeps the composition stable per edition.
- `JourneyRecapView`: when the journey is `completed` (never `ended_early`), the Seal
  presses as the hero. Below it are three facts in the design's tile style (Scène
  `~N min` · Mots `+N` · Série `N jours`), the words learned with their gender shapes
  (WP-D6), the mood line (WP-D2) and the teaser colophon. The one primary action is
  «Ranger le sceau».
- The edition number is derived from `episode_index + 1` today (`atelier.tsx:2183-2186`).
  Expose it once from the journey payload so Home, the recap and the collection agree.
- **Done when:** a completed day ends on the pressed Seal with honest facts; an
  `ended_early` day shows no Seal; the same edition always shows the same composition.

#### WP-D5 · The streak is a collection of seals
- One source of truth. The Home streak is `User.grammar_streak_days`, but the calendar at
  `GET /analytics/streak` counts `LearningSession.started_at`
  (`app/services/analytics.py:222-257`). Build the calendar from completed journey days,
  so the number and the grid can never disagree.
- The «jour de relâche» from WP-79 (one freeze earned per full week) is stored per day, and
  the calendar returns `completed | relache | missed | today | future` with the edition's
  seal variant.
- «Vos sceaux» in Cahier → Relevé, reached from the Home streak link: a 7-column week
  grid of `SealMini` discs. A relâche day is a yellow reward token in a dashed disc, today
  is a dashed red disc, and future days are dotted. Below it is one card for today's seal
  («encore 2 formes», from WP-D1) and the record.
- **Done when:** a test proves the calendar and `grammar_streak_days` agree across a
  missed day, a relâche day and a day-boundary in the learner's timezone; the grid renders
  4 weeks without horizontal scroll at 320 px.

#### WP-D6 · The gender is the shape
`VocabularyWord.gender` is stored (`app/db/models/vocabulary.py:40`, schema
`app/schemas/vocabulary.py:18`) but no frontend reads it.
- Serve `gender` (and part of speech) on the Lexique, word-sheet and recap payloads.
- A `WordToken`: a feminine noun is a circle, a masculine noun a square (8 px radius),
  anything else a triangle. The article (`la` / `le` / `l'`) sits inside it in Garamond
  italic, and its accessible name is «féminin» etc. **Colour keeps its role** (blue =
  learning, yellow = new, ink = known), so gender is carried by shape alone. That is
  colour-blind safe and never collides with red = action.
- Used in the Lexique list (`pages/vocabulary.tsx`, `MotsDuJour.tsx`), the word sheet
  (`WordBiographySheet.tsx`) and the recap's words (WP-D4). Each row also shows who said
  the word (a sm `CastPortrait`) and the scene sentence.
- Depends on WP-84's gender backfill and POS fix. Without a known gender, the token is a
  plain ink outline and nothing is guessed.
- **Done when:** every noun with a stored gender shows the right shape and article in the
  three surfaces; a snapshot test pins the three shapes; `l'addition` reads «féminin».

#### WP-D7 · Small touches: the tile's mould and the sealed letter
- Word tiles (`ui/Choice.tsx:109` `WordTiles`): a placed tile leaves a dashed
  `--av2-line-2` mould of the same width in the bank, so the bank never reflows. Placed
  tiles use the selected style (2 px blue border). Land this together with WP-76's fix
  of the duplicate bank (`JourneySteps.tsx:403` and `:416`).
- Courrier unread card (`CrArtefactUnread`, `Courrier.tsx:854-866`): the Feuilleton
  hero's blue surface with an envelope drawn from the shapes (a card-coloured
  rectangle plus the triangle as its flap), sealed with the sender's `CastPortrait` in their
  `--char-*` ring, and a small red triangle as the stamp. A read letter's row keeps the
  ink check square. The button is the design's card-coloured press button «Lire et
  répondre · N min».
- **Done when:** placing and removing tiles never moves the other tiles; the envelope is
  pure CSS/SVG from tokens (no new image asset) and reads correctly in dark mode.

#### WP-D8 · The new cast and the image pipeline (owner-approved art direction, 2026-09-23)
The owner chose a new art direction for everything drawn: flat screen-print illustration in the brand palette
(canvas boards 10, 15 and 16). The current portraits, model sheets and sepia plates are retired.
- **Cast references.** One approved chest-up portrait per character, transparent background, stored under
  `public/assets/serial/characters/{id}/` (replacing `model-sheet.webp` as the generation reference). Faces are
  written into the prompt (bone structure, eyes, nose, age, skin), which is what keeps them individual; never
  "unique features" alone. The old model sheets must not be sent as references again: they pull every result
  back into the generic comic look.
- **Moods.** `portrait-{neutral,happy,cross,moved}.webp` for each character, each produced by an
  `images/edits` call on that character's approved portrait ("same person, change only the expression").
  `lib/onboarding-portraits.ts` and `CastPortrait` (WP-D2) gain the `moved` mood. Round avatars are head crops
  cut from the same files, not separate generations.
- **Location plates.** Generated with the style prompt and a **no people** rule, then run through a palette
  lock: a median filter, a snap to the `--av2-*` inks blended at about 55 %, and paper grain. A new location or
  season goes through the same step, so every plate lands in the same inks. Characters are layered on top of the
  plate, not painted into it.
- **Scene composition.** The episode reader composes plate plus character cut-outs plus mood per beat. A
  generated full panel with people is kept for rare story peaks only, with the approved portraits as references.
- **Ops.** The image API allows 5 input images per minute, so edit jobs are paced; each image is priced in the
  cost ledger (about US$0.05 at 1024 px medium). The spike scripts
  (`make_plates.py`, `make_cast_s.py`, `moods_s.py`) become one `scripts/art/` tool with the prompts in version
  control.
- **Consent.** Characters are not modelled on real, identifiable people unless that person has agreed in writing.
- **Status (2026-09-23):** done: the four 256 px portraits per character (`6ddf47b`), the
  approved references and mood busts in `docs/design-reference/cast/{id}/`, all 12 location
  plates redrawn with no people and palette-locked, and the tool `scripts/art/atelier_art.py`
  (`plate`, `reference`, `moods`, `crop`, `lock`). Open: the story engine's episode panels
  still follow the old art direction (`world_bible_paris_v2.json` → `visual_design`,
  "ligne-claire … clean ink contours") and send the old `model-sheet.webp` as references
  (`serial.py:1054`); switch both to this style and the new references.
- **Done when:** all six characters have four approved moods and avatars in the repo; every learner-facing
  surface uses them (WP-D2); the location plates are regenerated through the palette lock; no screen still
  shows a sepia plate or an old portrait.

## Order

1. **WP-D2** first: the portraits exist, and faces lift every screen after them.
2. **WP-D1 → WP-D3**, which share the step → shape mapping.
3. **WP-D4 with WP-79** (the same recap screen), then **WP-D5**.
4. **WP-D6 after WP-84** (it needs the gender backfill).
5. **WP-D7** with WP-76 (the same tile component) and WP-83 (Courrier layout).
6. **WP-D8** before WP-D2 ships: the faces WP-D2 puts on every screen should be the new ones.

Not packaged, still on the canvas: the «Édition du soir» (after 4/4, Home offers an optional
read with no red button). It only needs the existing dark tokens and can follow WP-D1.

## Owner decisions (2026-09-22)

- **The mark is the day's only gauge.** No goal ring anywhere; minutes stay a line of text
  (WP-D1, and WP-79/81 are amended to match).
- **The primary button is the av2 3D press:** `.av2-btn`, 16 px radius, red face with its
  deep-red press, sentence case, one per screen. It supersedes the ink pill from
  2026-09-02 on every surface. Secondary is the card-face press; correct is the green press.
