# Overhaul — Feuilleton (`/graphic-novel`, `/serial/*`)

Part of the journal-system overhaul; method + contract in `docs/JOURNAL_SYSTEM_OVERHAUL.md`.
Audited 2026-07-07 against `web-frontend/pages/graphic-novel.tsx` (5,797 lines — the reader),
`web-frontend/pages/serial/index.tsx` (archive), `serial/cast.tsx`, `serial/episode/[index].tsx`,
`app/api/v1/endpoints/graphic_novel.py`, `app/api/v1/endpoints/serial.py`,
`app/services/graphic_novel.py`, `app/services/serial.py`.

## Purpose

The Feuilleton is the app's **serialised illustrated story** — a daily comic episode in the
Paris "serial world" (cast: Monsieur Marchand, Romy Tremblay, Marin, Lila…). Two beat types
alternate: you *read* an illustrated episode (feuilleton), or you *act* by writing a reply
(that beat is a Mission — see `docs/overhaul-missions.md`). This surface is the reading half:
the illustrated episode reader plus its archive and cast. It is the emotional hook of the app
and the "head picture" the La Une home now teases.

## 1. Works today (code-grounded)

- **Illustrated reader** (`GraphicNovelPage`, graphic-novel.tsx:109) — comic panels with
  generated art (`PanelCard` :1706), on-art **speech-bubble overlays** + a text transcript
  (`BubbleOverlay` :2038, `BubbleTranscript` :2070), **captions** (`CaptionBlock` :2091), an
  EN-translation toggle (`showMobileTranslations` :124), a reading progress bar
  (`MobileReadingBar` :917), and an edition dateline (`EditionMeta` :1401: "Le Feuilleton ·
  Season 1 · Épisode N · date").
- **Audio / TTS** — per-panel narration (`PanelAudioButton` :1821, plays
  `panel.audio_payload.url`) and an episode-level control (`EpisodeAudioControls` :1845).
  The audio pipeline is real, not a stub.
- **Read-first tasks** — study tasks are anchored to panels and revealed on demand
  (`PanelInlineTaskDisclosure` :1962, `ReadFirstTaskSection` :1902, `SerialTaskEmbed` :1171)
  plus a `FinalTask` (:2424) / `MobileFinalTaskCard` (:2465); attempts + completion via
  `POST /graphic-novel/scenes/{id}/attempts` and `/complete`. Reading leads, study follows.
- **Vocabulary** woven into panels/tasks (`FeuilletonVocabularyStrip` :1457,
  `PanelVocabularyMarker` :1483, `PostSceneVocabularySummary` :2656).
- **Cliffhanger + continuation** — `FeuilletonCliffhangerHero` (:2572), `MobileCompletionCard`
  (:1266), `FeuilletonContinuationCard` (:2699) leave the reader on a hook to tomorrow.
- **Generation states** — script-ready-but-art-printing (`status === 'generating'`, "Art is
  printing", :346), delayed (:381), preparing (`EditionPreparing` :1513), empty
  (`FeuilletonEmptyState` :872). Episodes generate in the background.
- **Archive** (`/serial`, serial/index.tsx) — a season "thread" map of episodes with roman
  numerals, lead character, completion date, location, the choice/outcome you made, and a
  thumbnail; a "filed" count; link to cast. Episode permalink at `/serial/episode/[index]`.
- **Cast + relationships** (`/serial/cast`) — a **dramatis personae** grid with per-character
  register (tu earned / vous), closeness 0–5, the episode a tu-switch was filed in, recent
  callbacks, and a last-interaction summary; plus an **avatar builder** for the learner's own
  serial character (`POST /serial/threads/current/avatar`).
- Backend: `graphic_novel` (/today, create scene, get, attempts, complete) and `serial`
  (/today, threads, current episodes, current cast, avatar, onboarding/seen, advance).

## 2. Missing / should add (prioritised)

> **Functional-layer status (2026-07-07):** the two design-independent items are
> IMPLEMENTED in `web-frontend/pages/graphic-novel.tsx` (the visual "Le Feuilleton"
> reskin in §5 is still a separate Claude Design pass):
> - **#1 Theme-awareness (headline fix)** — the reader's `.feuilleton-page` block no
>   longer hardcodes a light palette or re-aliases `--app-*` to it; its local
>   `--paper`/`--ink`/… now point at the theme-aware global tokens, so the whole reader
>   honours light/dark with zero layout change. Verified live: dark mode renders
>   (`--paper` → `#171510`, page bg dark) where it was previously force-locked light.
> - **#2 Relationship cue mid-read** — new self-contained `SerialRelationshipChip`
>   fetches the current thread cast (`getSerialCast`), matches the character appearing in
>   this `episode_index` with the closest bond, and shows a register (tu/vous) + closeness
>   chip in the reader masthead, linking to `/serial/cast`. Best-effort (never blocks the
>   read). Structurally verified (tsc/lint/build); not seen live because this account's
>   current beat is a Mission, so no feuilleton scene is on the stand.
> - **#3 Unified IA / discoverability** — new `FeuilletonSectionNav` (L’épisode · La saison
>   · Les personnages) added to the reader (`graphic-novel.tsx`) and mirrored on
>   `/serial` and `/serial/cast`, so the three previously-siloed routes cross-link as one
>   section.
> - **Cast page theme fix** — `serial/cast.tsx` hardcoded 34 colours (0 tokens, dark-blind,
>   same drift as the reader); its dominant palette was converted to `--app-*` tokens so the
>   cast page is now theme-aware too (the archive `/serial` already used tokens).
> The design pass subsequently shipped prominent audio, consequence/previously treatment,
> waiting states, `FePanel`, and beat-aware continuation. Remaining product follow-ups are
> word-level gloss and a richer avatar customiser. Verified 2026-07-18:
> `tsc`/`lint`/`npm run build`, frontend static tests, and signed-in light/dark live checks
> across reader, archive, cast navigation, Atelier, and Missions.


1. **The reader is theme-pinned and off-system.** graphic-novel.tsx **hardcodes** its palette
   (`--paper: #f1ece1`, `--ink: #14110d`, … :3269) and then *re-aliases the global tokens to
   its own locals* (`--app-paper: var(--paper)` :3284) — so the main read is **dark-mode
   blind** and actively overrides the app tokens inside its scope. (The serial archive/cast
   pages already consume `--app-*` directly and ARE theme-aware — the reader is the outlier.)
2. **Relationship stakes are invisible while reading/acting.** Register (tu/vous), closeness,
   and callbacks live only on `/serial/cast`. When you read an episode with, or write to, a
   character you've earned "tu" with, nothing on the page reflects that bond — the one
   mechanic that makes the cast feel alive is absent from the moment it matters.
3. **Fragmented IA.** Reader (`/graphic-novel`), archive (`/serial`), cast (`/serial/cast`),
   permalink (`/serial/episode/[index]`) are four routes with two different visual languages
   and weak cross-links (small text links). There is no single "Feuilleton section of the
   paper" the way La Une is one front page.
4. **Audio is buried.** Per-panel + episode TTS exist, but there is no prominent "écouter
   l'épisode" / audio-first affordance, despite `docs/AUDIO_ONLY_MODE_SPEC.md`. For a
   commute/eyes-free read this capability is nearly hidden.
5. **Your choice's consequence isn't dramatised in the read.** The archive records the choice
   you made per episode, but the reader doesn't open by showing "what your last reply changed"
   — the serial's core promise (your French moves the story) is under-felt.
6. **Waiting UX is thin.** "Art is printing" / delayed states work but are plain; in the
   journal metaphor they should read like a press room setting the plates (reuse La Une's
   `LuLead` press/late states).
7. **Weak handoff from La Une.** The home now teases the feuilleton as its lead picture, but
   opening it drops you into a different-looking surface — it should feel like turning to the
   illustrated centrefold of the same edition.
8. Minor: EN-translation is an all-panel toggle (no word-level tap-to-gloss); the avatar
   builder is a reference-image summary rather than a real customiser.

## 3. Design drift vs. the journal contract

- **Reader:** hardcoded light palette + token re-aliasing (item 1); Inter/serif are declared
  locally rather than inherited. Not theme-aware. This is the biggest single drift in the app.
- **Archive/cast:** mostly on-contract (use `--app-*`), but their layouts (avatar builder,
  cast grid, season map) were designed before La Une and don't share its furniture (masthead,
  kickers, stamps, double-rule folios).
- **Cross-surface:** no shared header/section identity; four routes feel like three products.

## 4. Weave-in vision — "Le Feuilleton" (the illustrated supplement)

In a real paper the feuilleton is the **illustrated serial / centrefold supplement**. Treat
the whole cluster as ONE section of the edition, in the La Une type + token system, phone-first,
theme-aware:
- **The reader** = today's illustrated episode: on-art speech bubbles, editorial captions,
  a dateline masthead ("LE FEUILLETON · SAISON 1 · ÉPISODE N"), reading leads and the study
  task follows, then a cliffhanger that hands to tomorrow — with a visible relationship cue for
  the character in scene (a small "tu · proche" chip) so the bond is felt as you read/act.
- **"Écouter"** = a first-class audio affordance (play the episode as narrated panels), the
  same paper, for eyes-free reading.
- **The archive** = "La saison reliée" — the bound volume / season thread: each past episode as
  a filed plate with its stamp, date, lead character, and the choice you made.
- **The cast** = "Les personnages" — the dramatis personae / who's-who page: each character with
  their portrait, your register (tu/vous) as an earned stamp, closeness, callbacks, and your own
  avatar. Relationships shown as a living ledger.
- Same masthead, kickers, hairlines, stamps, and the print-in (grayscale→colour) done-state as
  La Une and Le Courrier — one publication, its Sunday comics section.

---

## 5. Claude Design brief — "Le Feuilleton"

> **Design pass IMPLEMENTED (2026-07-08).** The package (`Atelier (4).zip` →
> `docs/design-reference/feuilleton{.css,-parts,-boards,-screens}.jsx`) was ported
> into the app token system:
> - **`web-frontend/components/feuilleton/Feuilleton.tsx`** — the shared "supplement"
>   primitives (FeMasthead, FePreviously, FePanel/FeBubble/FeTranscript, FeRelChip,
>   FeAudioBar/FeAudioCTA, FeTask, FeCliff/FeContinuation/FeFiled, FeArchivePlate,
>   FeCastCard/FeMeCard/FeRegStamp, FeSectionNav, FeSkeleton/FeNotice) + `FeuilletonStyles`.
>   **Tokens only** — the design doc's hardcoded `:root` palette and `.fe[data-theme]`
>   preview overrides are dropped; `.fe` maps its locals onto the theme-aware `--app-*`,
>   with documented derived values (`--fe-halftone`, `--fe-scrim`, `--char-*`). A
>   layout-free `.fe-embed` scope lets the primitives drop into the reader's own
>   two-column shell. Real cast members' `accent_colour` overrides the world-bible
>   `--char-*` via the `accent` prop.
> - **`/serial` (archive)** → "La saison reliée": FeArchivePlate rows (roman · portrait ·
>   date/location · your réplique · outcome · thumbnail · filed stamp), season progress
>   line, cast entry, first-run empty. Maps `episodes[].{choice,outcome,thumbnail_url,
>   completed_at,required_cast,status}`.
> - **`/serial/cast`** → "Les personnages": FeCastCard ledger (register stamp, closeness
>   0–5, tu-switch episode, callbacks, last line) + FeMeCard avatar (keeps the
>   `setSerialAvatar` avatar/POV logic behind a "Personnaliser" affordance). Maps
>   `member.relationship.{register,closeness,register_switch_episode,callbacks,last_summary}`.
> - **`/graphic-novel` (reader)** — the section-identity surfaces adopt the shared
>   primitives via `.fe-embed`: FeMasthead (folio + serif-italic title + dateline +
>   reading-progress rule) + FePreviously + FeRelChip replace the bespoke `SerialReaderMast`;
>   `EpisodeAudioControls` is redrawn as the first-class FeAudioBar ("Écouter l’épisode");
>   `FeuilletonCliffhangerHero` is redrawn as FeCliff. Panel and task presentation later
>   adopted `FePanel` (`pages/graphic-novel.tsx:1362`, `:2032`) while preserving
>   `attemptsByTask`, `mobileTaskStops`, audio payloads, and generation-failure behavior.
>   Continuation now uses `FeContinuation`/`FeFiled`, French copy, and beat-aware routing;
>   dead legacy `.s-*` rules were pruned. Bottom nav (`PhoneProductNav`) is unchanged.
> Deferred follow-ups are word-level tap-to-gloss and a real avatar customiser. Current open
> work is tracked in `docs/audit-2026-07-18-status-and-work-packages.md`. Verified
> tsc/lint/build and frontend static tests green.

> Copy from here down into Claude Design.

# Design brief: "Le Feuilleton" — the illustrated serial supplement of the journal

## Context
You are redesigning the Feuilleton cluster (routes `/graphic-novel` reader, `/serial` archive,
`/serial/cast` cast, `/serial/episode/[index]` permalink) of a French-learning app whose home
screen is already a newspaper front page ("La Une") and whose Missions surface is being redrawn
as "Le Courrier". This must be the same publication — its illustrated Sunday-supplement section.
Study first:
- `web-frontend/components/laune/LaUne.tsx` — masthead, kickers, hairline rules, rubber stamps
  (`LuStamp`), press notices, skeletons, the ink "press bar" CTA, the lead illustration frame
  with credit line, and the grayscale→colour "print-in" done-state.
- `web-frontend/styles/globals.css` — the `--app-*` tokens (paper/sheet/ink ×3, red, blue,
  yellow, `--app-serif` = EB Garamond) + phone-shell vars. **Tokens only**; must render in light
  AND dark. (The current reader hardcodes its palette and re-aliases these tokens — that is the
  #1 thing to remove.)
- `docs/design-reference/serial-world-design-package.md`, `serial.css`, `serial-screens.jsx`,
  `serial-components.jsx` — the established serial art direction (ligne-claire European comic,
  the Paris cast and locations) and prior screen sketches.
- `docs/AUDIO_ONLY_MODE_SPEC.md` — the audio-first reading intent.

## The concept
The Feuilleton is the edition's **illustrated serial supplement**. One section, four views, one
type system. The reader is the centrefold comic; the archive is the bound season; the cast is
the dramatis personae; the permalink is a single filed plate. Reading always leads; the study
task follows the read; a cliffhanger hands to tomorrow. The learner's French moves the story,
and the relationships they build are visible where they matter.

## The four views to design

### A. The reader (`/graphic-novel`) — today's episode
1. **Dateline masthead** — "LE FEUILLETON · SAISON 1 · ÉPISODE N", the episode title as serif
   italic, the dateline, and a discreet way back to La Une. Reading progress as a thin rule.
2. **"Previously"** strip when returning mid-thread (`SerialPreviously`) — what your last reply
   changed, one line, so the consequence of the learner's French is felt at the open.
3. **Panels** — generated comic art with **on-art speech bubbles** (position-anchored) and a
   readable transcript fallback; **editorial captions** set as standfirsts; an EN-translation
   affordance (keep the toggle; ideally allow word-level tap-to-gloss). Design the panel frame,
   bubble, caption, and the credit line to match La Une's lead-image treatment.
4. **Relationship cue** — a small chip for the character in scene: register earned (tu/vous) +
   closeness, so the bond is present while reading/acting. Pull from the cast relationship data.
5. **"Écouter l'épisode"** — a first-class audio control (play narrated panels; per-panel play
   too). Design idle / playing / per-panel states. This is a headline upgrade, not a footnote.
6. **Read-first study task** — anchored to a panel, revealed on demand after the read, then a
   final task; correction shown quietly. Reading is never interrupted by the drill.
7. **Cliffhanger + continuation** — end on a hook with a "demain" tease and the next-beat handoff
   (read next / go act in Le Courrier), stamped when the episode is filed.

### B. The archive (`/serial`) — "La saison reliée"
The season as a bound volume / thread: each past episode a filed plate — roman numeral, lead
character portrait, date, location, the **choice you made**, its outcome, thumbnail, and a
"filed" stamp; a season progress line; entry to the cast. Current/next episode highlighted.

### C. The cast (`/serial/cast`) — "Les personnages"
Dramatis personae / who's-who: each character as a portrait card with your **register as an
earned stamp** (tu/vous), closeness (0–5), the episode a tu-switch was filed in, recent callbacks,
and a last-interaction line — a living relationship ledger. Plus the learner's own **avatar**
(their serial character) with a real reference/customise affordance.

### D. Permalink (`/serial/episode/[index]`) — one filed plate, reader layout reused read-only.

## States to design (all of them)
1. Reader mid-episode (panels + bubbles + a revealed panel task + relationship chip).
2. Audio-playing state.
3. Episode complete / cliffhanger / filed (stamped, print-in colour).
4. Art "generating" (press room setting plates) and "delayed" (a printed apology, text leads) —
   reuse La Une's `LuLead` press/late language.
5. Empty (no thread yet) and first-run.
6. Archive populated + near-empty.
7. Cast populated (a tu earned, callbacks) + early (all vous, no callbacks).
8. Loading skeleton (press style) and error press-notice.
9. Every state in **light and dark** (tokens make this near-free — verify contrast on art).

## Copy rules
French for the publication/story world (section names, kickers, stamps, "Écouter l'épisode",
"La saison reliée", "Les personnages", "Demain"); English only for out-of-fiction chrome. Never
mix languages in one line. Write ALL copy for all states.

## Hard constraints
- `--app-*` tokens only; **remove all hardcoded palette and token re-aliasing** from the reader;
  derived values (e.g. a newsprint gray for undone panels) documented. Must work light + dark.
- EB Garamond (`--app-serif`) for headlines/story/captions; grotesk for chrome.
- Panels carry generated raster art — design the frame/bubble/caption system to sit on top of
  arbitrary illustrations without breaking; keep bubbles legible over art.
- Animations transform/opacity/filter only; respect `prefers-reduced-motion`.
- Honest data: every element maps to a named field (`scene.panels[].{image_url,bubbles,caption,
  audio_payload}`, `scene.status` generating/delayed/completed, `episode_index`, `title`,
  archive `episodes[].{choice,outcome,thumbnail_url,completed_at,required_cast}`, cast
  `member.relationship.{register,closeness,callbacks,register_switch_episode,last_summary}`,
  vocabulary, tasks, cliffhanger/continuation). Design the empty variant of anything optional.
- Do not redesign the bottom nav or the home page. Keep the existing reading/task/audio/
  completion LOGIC — you are redrawing surfaces, not changing the play loop.

## Deliverables
1. High-fidelity mobile frames (390px) for reader states 1–4, the archive, and the cast — light
   + dark for at least the reader and cast.
2. A component spec: the shared "supplement" primitives (dateline masthead, panel frame, on-art
   bubble, caption, relationship chip, audio control, filed-plate/archive row, cast card + register
   stamp, avatar) with props and payload mapping, spacing scale, and the print-in/stamp transition.
3. Full French copy deck for all states.
4. A migration note mapping each new component onto what it replaces across graphic-novel.tsx,
   serial/index.tsx, serial/cast.tsx (and confirming which existing logic components stay).
