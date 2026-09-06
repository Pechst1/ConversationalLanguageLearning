# Frontend ↔ engine handoff

Owner: frontend/UI lead. Started 2026-09-06. The engine agent owns `app/`, prompts,
shared story/learning state, migrations, backend tests, and
`web-frontend/{types/daily-journey.ts, services/api.ts, services/daily-journey.ts}`.
This file is the frontend's record and the place interface requests are raised.
`STATUS.md` is not edited by the frontend while the engine agent is working.

## 1. The Claude design — inspected via the design MCP, spec below is authoritative

Imported through `DesignSync` from project `5ed85a9c-deef-4594-a0f4-8cad9ca1894e`
("Atelier app design overhaul", owner Vincent, `canEdit: true`). It does **not** appear
in `list_projects` because that filters to design-*system* projects; address it by id.

The owner's local export `docs/design-reference/Atelier app design overhaul.zip`
(extracted to `docs/design-reference/claude/`) is **byte-identical to the remote**
(`Atelier App.dc.html`, 39,453 bytes; identical file list). The export is current.

### ⚠ Correction — the bundled PNGs are the BEFORE, not the design

`claude/ref/*.png` are **board 0 of the canvas: "Current build, recreated from source —
for reference."** They show today's app (7-station ladder, "22 drills", "DAY 12",
A·FILL/B·WORD-BANK). An earlier revision of this document derived the visual language
from them and was **wrong in the opposite direction**. The design explicitly critiques
exactly those traits:

> "What I read in the current build: … hard 1px ink boxes, offset 'print block' shadows,
> red CTA, roman-numeral roadmap, uppercase 10–11px tracked labels everywhere … Three
> type voices and boxes-inside-boxes are what make it read as busy."

### The overhaul system (from `Atelier Home Directions.dc.html`, verbatim)

> "two fonts only — Garamond italic for the one headline per screen, Instrument Sans for
> everything else, sentence case, no tracked caps. Rounded 16–24px surfaces instead of
> ruled boxes. The Bauhaus mark's four shapes become the app's playful vocabulary:
> progress tokens, path nodes, tab icons. One tactile 3D-press button per screen.
> Red = action, blue = story/info, yellow = reward, ink = done."

Three home directions were explored — 1a "La Une, allégée", 1b "Le Parcours",
1c "Les Cartes". **`Atelier App.dc.html` resolves them: it implements 1a** (front page
cut to one story, one button, three tiles). Build 1a.

### Exact values, read from `Atelier App.dc.html`

**Colour**

| Token | Hex | Use |
|---|---|---|
| `--at-bg` | `#e9e4d8` | outside the device frame |
| `--at-paper` | `#f1ece1` | screen ground, sheet ground |
| `--at-card` | `#f8f3e8` | cards, tiles, chips, input wells |
| `--at-line` | `#e8e0cf` | hairlines, inactive progress |
| `--at-line-2` | `#d8cdb6` | pressed shadow on paper, sheet handle, dashed locks |
| `--at-ink` | `#14110d` | text, "done" |
| `--at-ink-2` | `#4a4538` | body secondary |
| `--at-muted` | `#6f6857` | labels, meta |
| `--at-red` / shadow | `#d8321a` / `#9c2411` | **action** |
| `--at-blue` | `#1d3a8a` | **story / info**, progress fill, learner bubble |
| `--at-yellow` / shadow | `#f3c318` / `#c49a0a` | **reward** |
| `--at-green` / shadow | `#2c6a5d` / `#1f4f45` | correct |
| feedback tints | `#e3efe9` correct · `#f7e1dc` wrong | feedback band |

**Type** — `Instrument Sans` 400/500/600/700 for everything; `EB Garamond` italic
400/500/600 for the single headline per screen, French content, and numerals.
Sentence case. No tracked caps. Label sizes 12–13px 600/700, meta 12px `--at-muted`.

**Geometry** — radii: pill `999px`; tile `18px`; button `16px`; card `16px`;
episode card `22px`; feuilleton hero `24px`; vocab card `28px`; sheet top `28px 28px 0 0`.

**The 3D press** — one per screen, on the primary action only:
`box-shadow: 0 5px 0 <shadow>` and on press `transform: translateY(5px); box-shadow: 0 0 0`.
Secondary/tile press is `transform: scale(.96)`; choice options use `0 3px 0`.
Transitions `.08s`. Keyframes in the design: `at-pop .3s` (feedback), `at-rise .3s
cubic-bezier(.2,.8,.2,1)` (sheet), `at-fade .2s` (scrim, rule card).

**The Bauhaus mark** — 28×28 svg: ink square `rx=2`, blue circle, yellow square `rx=2`,
red triangle. Its shapes become progress tokens, path nodes and tab icons.

**Navigation** — four tabs, French: **Atelier · Missions · Feuilleton · Cahier**.
Active tab = icon in a `44×28` pill `#e8e0cf`, label 700; inactive `--at-muted` 600.
Tabs hidden on Séance and Lexique (immersive screens).

**Screens present in the design**: Home, Séance (session), Lexique (vocab cards),
Cahier (notebook), Missions (chat), Feuilleton (episode list), Réglages (bottom sheet).

**Sheet** — scrim `rgba(20,17,13,.35)`, handle `40×5` `#d8cdb6`, radius `28px` top,
`at-rise` in. Settings sheet content: streak squares, "Temps par édition" 5/8/15 min
segmented, toggles.

**Feuilleton screen** — blue `#1d3a8a` hero card, 16:9 art, "Épisode 3 · aujourd'hui",
Garamond italic title, paper-on-blue CTA "Lire et répondre · 8 min"; below, a list of
read episodes (ink checkmark badge) and a locked next episode (2px dashed `#d8cdb6`,
padlock). Copy is French.

### Divergences the frontend must decide deliberately

The design's session screen is a 3-exercise grammar drill with a streak counter. The
accepted product is the 3–5 step journey (scene → recall → respond → resolution) and
CONTRACTS forbids fabricated streaks. **Reuse the design's session chrome** — close X,
blue progress bar, rule chip, option cards, feedback band, one 3D primary — and drive it
from the real plan. Do not ship the "12 jours de suite" streak unless the engine exposes
a real one. Record each such mapping in §4.

## 2. File allocation

| Area | Owner |
|---|---|
| `components/atelier-v2/ui/`, `styles/atelier-v2.css`, `lib/atelier-v2-copy.ts`, `public/fonts/` | subagent A — design system + daily UI |
| `components/atelier-v2/journey/` renderers (presentation only) | subagent A |
| `components/feuilleton/`, `pages/graphic-novel.tsx`, `pages/serial/*` | subagent B — reader |
| `components/layout/*`, `lib/product-shell.ts`, `pages/atelier.tsx`, integration, review | frontend lead |
| `app/**`, prompts, migrations, `types/daily-journey.ts`, `services/api.ts`, `services/daily-journey.ts` | **engine agent — frontend does not edit** |

`useDailyJourney`, `journey-state.ts`, `journey-requests.ts` and the recovery layer are
**behaviour** and must be reused unchanged; the visual migration replaces renderers only.

## 3. Interface requests to the engine agent

_None yet. Each entry will state the exact request/response/state requirement, why the
current contract cannot express it, and the frontend fallback in the meantime._

## 4. Design gaps and mapping decisions

Recorded by subagent A (WP-01 + WP-07 visual), 2026-09-06.

### 4.0 Frontend lead ratification, 2026-09-06

**The three foreign-file edits are approved.** Each was flagged for consent rather than
slipped in. Verified independently: `package.json` gains one `test:atelier-ui` script with
**no dependency and no lockfile change**; `_app.tsx` gains one CSS import (Next only allows
a global stylesheet to be imported there); `RouteAuthGate.tsx` lists `/atelier-v2-gallery`
beside `/mobile-visual-qa`, and that page's `getStaticProps` returns `notFound` when
`NODE_ENV === 'production'` — the identical gate — so production auth is not widened and
the route does not exist in a production build.

**Font aliasing (`AtelierSerif`/`AtelierSans`) is kept, and the agent was right to ask.**
`styles/globals.css` already requests `"EB Garamond"` and currently falls back to Times.
Registering the real family name would have silently restyled every legacy
journal/Feuilleton/Cahiers surface **while V2 is disabled** — precisely what WP-01's
acceptance criteria forbid. The binaries are unmodified and the OFL Reserved Font Name is
untouched, so this is a CSS alias, not a font modification. Reversal is two added
`@font-face` rules and belongs to WP-08, when legacy surfaces are migrated deliberately.

**Legacy isolation verified, not taken on trust.** `styles/atelier-v2.css` has 182 rule
blocks and **zero** unscoped selectors — every rule sits under `.av2`, `:root`, `html`, or
an `@font-face`/keyframe.

**Two self-caught bugs worth noting** because they are the kind a visual pass usually
ships: paper-white on red measured **4.32:1** (under AA) and was corrected to `#fff`, which
is what the design used anyway; and `forceTheme="light"` lost to the OS dark preference.
Both now have build-failing guards, one of them for the exact drift `globals.css` shipped
once before.

### 4.1 States the design has no artboard for

A static canvas never fails, so seven of the daily journey's renderable states have
no design. Each is **extended from the design's own primitives**, not invented:

| State | Extended from | Rule applied |
|---|---|---|
| `retrying` | rounded card + blue circle token | notice, never the feedback band |
| `empty_answer` (422) | blush tint + red triangle token | `role="alert"`; never a wrong-answer card |
| `unscored` (`pending: true`) | feedback band, **neutral** tone, open-circle glyph | grading that did not happen, not a verdict |
| `reconciled` (409 refetched) | rounded card + blue circle | states the scene moved on; no score shown |
| transport `error` | blush tint + red triangle | retry offered; explicitly not a verdict |
| offline / `pending_sync` | dashed outlined surface (the design's "locked episode") | no tint, no tick — a connection fact |
| `preparing` / `unavailable` / `paused` | `StateBlock` over the outlined and blush surfaces | one action each |

**The load-bearing rule: only a graded verdict gets the feedback band and its tint.**
`journey-state.ts` guarantees that separation in the data; the renderers keep it true
in the pixels. `supported` (correct-with-help) is given the **blue** badge rather than
green, so "on your own" and "with help" are visibly different outcomes — the design has
only correct/wrong.

### 4.2 Divergences from the design

1. **No streak.** The design's home masthead and Séance header both carry
   "12 jours de suite" / "Édition Nº 12". Nothing in the contract exposes a real
   streak and CONTRACTS forbids inventing one, so the slot is **empty**, not filled
   with a placeholder. If the engine later exposes a real consecutive-day count this
   is a one-component addition to the session header.
2. **Progress is segmented, not a drill percentage.** The design's bar is
   `exercise / 3`. `StepProgress` renders **one segment per real planned step**, so it
   cannot claim a number the plan does not contain, and it renders *nothing* when
   there is no plan. `ProgressRule` with `max: 0` reports no `aria-valuenow` at all —
   "we do not know" and "you have done none of it" are different facts.
3. **`#fff`, not paper-white, on red.** The design uses `color:#fff` on `#d8321a` in
   all four of its red surfaces. Paper-white (`#f8f3e8`) there measures **4.32:1**,
   under AA for the 17px action label; `#fff` is **4.78:1**. Following the design was
   also the accessible choice here.
4. **Font family names are CSS-local.** The vendored faces are registered as
   `AtelierSerif` / `AtelierSans`, not `EB Garamond` / `Instrument Sans`. `globals.css`
   already declares `--app-serif: "EB Garamond", …`, which resolves to Times today;
   registering the real name would silently restyle every legacy journal, Feuilleton
   and Cahiers surface while V2 is off. Binaries are unmodified and the OFL Reserved
   Font Names are untouched. Flipping legacy over later is two added `@font-face`
   rules — recorded in `public/fonts/LICENSE.md`.
5. **Navigation labels are localized.** The design's four tabs are French
   (Atelier · Missions · Feuilleton · Cahier). `TabBar` takes labels as props and
   `lib/atelier-v2-copy.ts` ships en/de/fr, because the product decision is that a
   learner must not have to learn the chrome vocabulary to finish the scene. French
   is kept verbatim for `fr`. The primitive is **not wired into the app shell** —
   `components/layout/**` is the lead's.
6. **Séance is 3–5 journey steps, not a 3-exercise grammar drill.** The chrome is
   reused verbatim (close X, blue progress, "La règle" pill, option cards, feedback
   band, one 3D primary); the content is the real plan.

### 4.3 Things the design specifies that are built but not yet placed

`Lexique` (vocab card, `0 8px 0` press, flip), `Cahier` (rows, search), `Missions`
(chat bubbles, composer with mic), `Feuilleton` (blue hero, episode rows, dashed lock)
and `Réglages` (bottom sheet, segmented control, toggles) all compose from the shipped
primitives — `Surface`, `Row`, `Chip`, `Action`, `BottomSheet`, `Artwork`, `Portrait`,
bubbles. They belong to WP-08/WP-09 and to subagent B, not to WP-01.

### 4.4 Accessibility rules the design cannot express

* Status is **never colour alone** — every graded state carries a glyph and a
  visually-hidden word; the active tab uses `aria-current`.
* A disabled control dims its **face, never its label**; `opacity` is never applied to
  a whole button or a graded option.
* 44px effective touch target on every control, at every text size.
* Sheets and dialogs trap focus, restore it to the trigger, close on Escape, and lock
  background scroll.
* No horizontal overflow at 320px with 200% text. The D-6 cause — a grid/flex item's
  `min-width: auto` — is zeroed once for the whole scope.

## 5. Verification status

### WP-01 + WP-07 visual (subagent A), 2026-09-06

Commands, all from `web-frontend/`, all passing:
`npm run type-check` · `npm run lint` (0 warnings) · `npm run test:journey` ·
`npm run test:recovery` · `npm run test:atelier-next` · `npm run test:atelier-ui` (new) ·
`npm run build` (compiled successfully).

Measured in the browser on the dev server, at the dev-only gallery
`/atelier-v2-gallery` (34 controls, every primitive state on one page):

| Width | 100% text | 200% text |
|---|---|---|
| 320 / 390 / 440 / 768 / 1280 | 0 overflowing descendants, 0 controls < 44px | 0 overflowing descendants, 0 controls < 44px |

`document.scrollWidth === clientWidth` at every combination; smallest control
44.0×44.0, tallest 189.2px at 200%. Light minimum contrast **4.78:1** (the primary
action), dark minimum **5.64:1** (label/meta). Sheet verified: focus enters on open,
`aria-modal="true"`, Escape closes, focus returns to the trigger, background scroll
released. Fonts confirmed loading as `AtelierSerif` / `AtelierSans` from `/fonts/`,
`latin` loaded and `latin-ext` correctly deferred until needed.

**Fixture-only / not yet verified against real APIs:** the daily-journey renderers are
covered by the frozen public fixtures through `journey.test.js` (26 fixtures, every
phase and feedback state) but have **not** been driven against a live journey — the
preview auth gate blocks `/atelier` without a session. Recheck once the lead wires
`pages/atelier.tsx`. Native/iOS and the software-keyboard check are also outstanding.

---

## 4B. Design gaps and mapping decisions — subagent B (Feuilleton reader), 2026-09-06

### 4B.1 The panel-by-panel reader is genuinely absent from the design

`Atelier App.dc.html` specifies the **Feuilleton index** completely (blue `#1d3a8a`
hero, radius 24, 16:9 art, "Épisode 3 · aujourd'hui", Garamond italic title,
paper-on-blue 48px CTA with `0 4px 0 #cfc4ad`; read rows `#f8f3e8` radius 16 with a
56×56 radius-12 thumb and a 26×26 ink radius-6 check; a `2px dashed #d8cdb6` locked
row). `pages/serial/index.tsx` now implements that verbatim.

It specifies **no reader**. The reader was extended from the design's own primitives
rather than from the old ruled-box look:

| Reader element | Derived from |
|---|---|
| top bar: 44px round quit + 14px rail `#e8e0cf` → `#1d3a8a` fill | Séance screen chrome |
| running head: 13px 600 muted eyebrow + one Garamond italic headline | Feuilleton index head |
| panel plate, radius 24, blue ground | Feuilleton hero card |
| speech card `#f8f3e8` radius 18, 4px accent edge | Missions chat bubbles + world-bible accents |
| choice options: 56px min, radius 16, `0 3px 0`, 22px dot | Séance option cards |
| feedback: 26px round token + Garamond italic verdict | Séance feedback band |
| word-help sheet | the one sheet spec (scrim `rgba(20,17,13,.35)`, `#f1ece1`, `28px 28px 0 0`, 40×5 `#d8cdb6` handle, `at-rise`) |
| stage tokens: ink square = read, blue circle = here, red triangle = the closing beat | "the Bauhaus mark's four shapes become progress tokens" |

### 4B.2 Deliberate divergences

1. **No locked "Épisode 4 · demain" row.** `GET /serial/threads/current/episodes`
   returns only completed episodes plus the current one; there is no future episode to
   lock. Drawing a padlocked next chapter would promise content the server has not
   planned. The row returns the moment the engine publishes a scheduled next episode.
2. **No "· 8 min" on the CTA.** The design's hero CTA reads "Lire et répondre · 8 min".
   No episode payload carries a duration estimate, so the CTA reads "Lire et répondre".
   Add the estimate as soon as the engine exposes one (see §3B).
3. **Character accents extended to unnamed speakers.** Standalone (non-serial) editions
   really do come back with `speaker: "Clerk" / "Supervisor" / "Bystander"` and an empty
   `speaker_id` — verified on a live generated scene. A world-bible speaker always wins;
   otherwise one of the same seven accents is assigned deterministically by name, so two
   speakers are never the same colour and a speaker keeps its colour across panels and
   reloads. Nothing is claimed about who they are.
4. **Type converted to `rem`.** The design quotes px. Everything a learner reads is in
   rem so the app's Apparence font-size setting still moves the page; geometry (radii,
   rail height, icon buttons) stays in px, as designed.
5. **Tabs stay visible in the reader.** The design hides tabs on Séance and Lexique.
   The Feuilleton is a top-level destination, a read can last many sessions, and leaving
   mid-episode is normal and lossless (position is persisted), so hiding the tabs would
   trap the learner rather than protect focus. The reader has its own quit control as well.
6. **Word tokens are below 44px.** Tappable words are inline targets inside a sentence,
   which WCAG 2.5.8 exempts. Every standalone control is ≥44px.

## 3B. Interface requests to the engine agent — subagent B

1. **A scheduled next episode.** `GET /serial/threads/current/episodes` returns
   `episodes` (completed only) + `current_episode`. To draw the design's locked
   "Épisode 4 · demain" row the frontend needs a typed *planned* next episode
   (index, provisional label/topic, `available_at`) — or an explicit "nothing planned".
   *Fallback:* the row is omitted.
2. **A duration estimate per episode**, for the design's "Lire et répondre · 8 min".
   *Fallback:* the CTA omits the estimate.
3. **Archive rows have no title for a mission-kind episode** (`_archive_episode_payload`
   sets `title = "Episode"` unless a mission/scene resolves), and `episode_label` is
   English ("Season 1 · Episode 3") while the surface is French. The reader derives its
   own French label from `episode_index`; a localized label would be better.
   *Fallback:* `hook_text` → `title` → `Épisode {n}`, built client-side.
4. **`hook` is `{}` on standalone editions**, so the closing stage carries only the final
   prompt and no "à suivre". Handled; noted so it is not read as a frontend bug.

## 5B. Verification status — subagent B (Feuilleton reader)

**Against real APIs** (backend on `127.0.0.1:8010`, synthetic `@example.com` account,
registered and logged in over HTTP):

* `POST /api/v1/graphic-novel/scenes` → 200, real asynchronous generation ran to
  completion: `writing` → `generating` (4 panels) → `available` with 4 of 4 images.
* `GET /api/v1/graphic-novel/scenes/{id}` polled through every one of those states.
* `GET /api/v1/serial/today`, `GET /api/v1/serial/threads/current/episodes` — a fresh
  learner's episode 1 is a **mission**, so `/serial` shows the mission hero and an empty
  archive; that path is exercised, the feuilleton-hero path is not.
* `GET /api/v1/vocabulary/lookup?word=…` — driven from the running reader in the browser;
  returned a real gloss for a tapped word.

**In the browser** (`/mobile-visual-qa?reader=…`, dev-only harness whose scene body is a
captured real `GET /scenes/{id}` response): panel next/previous, keyboard
Arrow/Home/End, the word sheet opening on a tapped word and returning to the same
panel, Escape closing it with focus restored to that word, reload-and-resume by stage
identity, "Déjà lu" versus "À vous de répondre", one 3D press, printing and missing art.
Measured: 0px horizontal overflow at 320/390/440/768/1280 and at 200% root text on 320;
stage dots 44×44, prev/next 48px, quit 44×44.

**Verified by server-rendering the component** (`reader-render.test.js`), because the QA
page hydrates unreliably in this preview: the filed episode, the answered/read-only
panel, and the stale banner.

**Not verified:** the authenticated `/graphic-novel` and `/serial` routes in a browser —
the shared `RouteAuthGate` requires a session and I did not enter credentials into the
sign-in form. Swipe was not exercised (pointer injection was unavailable). Native/iOS
untested.


## 6. Frontend lead — independent verification, 2026-09-06

I re-ran the gates and drove the reader myself rather than accepting the subagents'
reports. All in a real browser at 375×812 against the dev server on :3000.

### Verified by me

| Check | Result |
|---|---|
| `type-check`, `lint`, `test:journey`, `test:recovery`, `test:atelier-next`, `test:atelier-ui`, `build` | all pass |
| `test:reader` | **37 pass, 0 fail** |
| Horizontal overflow at 375px | **0 overflowing elements**, `scrollWidth === clientWidth === 375` |
| Control sizes | every sub-44px control is either an inline tappable word (WCAG 2.5.8 exempts inline targets in a sentence) or the legacy QA page's own chrome. **No reader control is under 44px** |
| Stage navigation | 1/5 → **3/5** after two Next presses |
| Word help sheet | opens with `aria-modal="true"`, **focus moves into it** |
| **Position preserved during word help** | counter stayed **3/5** with the sheet open — the load-bearing requirement |
| **Position preserved across reload** | after a full page reload the reader restored to **3/5** from persisted `stageIndex: 2` |
| Position identity | stored as `{stageIndex, stageKey: "panel:<uuid>", furthest}` — keyed by identity, so late-arriving art cannot move the learner |
| `atelier-v2.css` scoping | 182 rule blocks, **zero** unscoped selectors |
| Gallery production gate | `getStaticProps` returns `notFound` in production, same as `/mobile-visual-qa` |
| `ReaderHarness` | returns `null` server-side and without `?reader=`, so CI's static capture of `/mobile-visual-qa` is unaffected |

### NOT verified — stated plainly

* **Escape-to-close and focus-return on the word sheet.** Real pointer and key injection
  times out in this preview pane (it reports the pane as hidden/unresponsive), which
  matches subagent B's note that the QA page hydrates unreliably here. The behaviour has
  permanent tests, but **I did not confirm it in a browser** and am not claiming it.
* **The authenticated `/graphic-novel` and `/serial` routes.** `RouteAuthGate` requires a
  NextAuth session. I will not type a password into a form, and I will not forge a session
  cookie. **This needs one owner sign-in**, then a re-run of the panel / word-help /
  resume / stale-scene pass on the real route.
* Native/iOS, software keyboard, and swipe (pointer injection unavailable here).

### Risk found while integrating — for the engine/config owner

`web-frontend/lib/auth.ts:20` defaults to **`http://localhost:8000`**:

```js
return process.env.API_URL || 'http://localhost:8000';
```

Port 8000 is **a different project's server** on this machine. `.claude/launch.json`
correctly sets `API_URL=http://localhost:8010`, so the normal dev flow is fine — but
anyone running `npm run dev` without it would POST credentials to another application.
This is the same class of defect as WP-12's D-8 (`capture:mobile` defaulting to 8000).
Raised rather than changed here: `lib/auth.ts` is auth code and belongs to the engine
owner. Recommendation: fail fast on a missing `API_URL` instead of guessing a port.
