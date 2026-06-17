# Mobile Implementation Agent Handoff

This handoff is for the next agent taking over the mobile implementation for the French grammar learning app.

Latest clarification: the immediate task is designer-requirements cleanup, not another implementation slice. The corrected designer brief now lives in `docs/mobile-designer-followup-requirements.md`. Once that is accepted, further implementation should continue in `web-frontend`, using the live backend-backed desktop pages as the source of truth.

## Live Coordination

- Coordination rule for this turn: update this section before starting a slice. The parent Codex agent owns this handoff file and integration; worker agents should not edit this file.
- Current correction: Desktop parity must be restored. Mobile work should be additive and scoped to narrow breakpoints. Do not replace the existing desktop version.
- Current continuation round: resumed V1 mobile state hardening and QA polish on 2026-05-13 while preserving the restored desktop version.
- Complete: Atelier final phone-state pass (`web-frontend/pages/atelier.tsx`) — Worker E / Atelier agent. Added mobile loading and empty cards, compact session focus/fallback cards, sticky action fit, and spoken/paragraph/conversation mobile output briefs while preserving desktop auto-open and CTA behavior.
- Complete: Notebook final phone-state pass (`web-frontend/pages/grammar.tsx`) — Worker F / Notebook agent. Added mobile loading skeletons, empty clear-filter action, search clear/focus states, horizontal filter chips, inline detail note save states, overflow guards, and bottom-nav clearance while preserving desktop/tablet split view.
- Complete: Missions V1 mobile retry/voice/state polish (`web-frontend/pages/missions.tsx`) — Worker B / Missions agent. Added failed-send retry/edit, mobile recording/upload status, loading/empty CTA, chat-first ordering, and compact custom mission controls scoped to `max-width: 560px`.
- Complete: Feuilleton V1 mobile reading/task/generation polish (`web-frontend/pages/graphic-novel.tsx`) — Worker D / Feuilleton agent. Added mobile loading/generation states, task deck progress/status, recent correction/error feedback, and lifted sticky reading bar scoped to `max-width: 760px`.
- Complete: Parent + QA agent desktop/mobile regression review. Fixed QA findings by removing shared global body bottom padding, scoping Feuilleton phone CSS under `.feuilleton-page`, and making the Missions retry bar available on desktop failed-send states too.
- Verified: Parent Codex agent ran `npm run type-check`, `npm run lint`, and `git diff --check`. Lint passed with existing graphic-novel/stories `<img>` and `loadInitial` dependency warnings only. Browser visual QA ran against `http://localhost:3000` at desktop and phone widths after starting the dev server; desktop chrome stayed present and phone views showed the additive mobile nav/state surfaces.
- Current correction round: The prior pass did not sufficiently adopt the design team's new mobile visual design from `French Grammar Learning-9.zip`. Next work must use the package 9 mobile prototype as the visual source, not merely make the existing desktop editorial UI responsive.
- Complete: Package 9 mobile visual extraction. Concrete source files used: `docs/design-handoffs/french-grammar-learning-9/atelier-mobile/system.jsx`, `screens-home-session.jsx`, and `screens-notebook-missions-feuilleton.jsx`. Key adopted cues: warm paper shell, centered serif mobile mastheads, full-width bottom tab rail, sharp 1px sheet/card borders, pill/chip controls, chat-first Missions rhythm, reading-first Feuilleton rhythm, and phone-specific Atelier “Today’s practice” entry.
- Complete: Package 9 phone-only visual adoption pass while leaving desktop untouched. Updated shared mobile chrome (`web-frontend/components/layout/EditorialMasthead.tsx`), Atelier home (`web-frontend/pages/atelier.tsx`), Missions mobile switcher/chat shell (`web-frontend/pages/missions.tsx`), and Feuilleton mobile create/reading/task chrome (`web-frontend/pages/graphic-novel.tsx`).
- Complete: Shared masthead and Atelier desktop parity + mobile-only behavior split (`web-frontend/components/layout/EditorialMasthead.tsx`, `web-frontend/pages/atelier.tsx`) — Worker A / Atelier agent.
- Complete: Missions desktop parity + mobile-only retry/chat-first refinements (`web-frontend/pages/missions.tsx`) — Worker B / Missions agent.
- Complete: Notebook desktop parity + mobile-only responsive detail (`web-frontend/pages/grammar.tsx`) — Worker C / Notebook agent.
- Complete: Feuilleton desktop parity + mobile-only reading/task flow (`web-frontend/pages/graphic-novel.tsx`) — Worker D / Feuilleton agent.
- Verified: Parent Codex agent ran final type/lint/diff checks and browser-verified both desktop and phone viewports. Desktop keeps primary nav, active Atelier session auto-open, side rails, and original desktop flow. Phone viewport gets the additive mobile bottom nav, Atelier Continue card, Notebook inline detail, Missions chat-first flow, and Feuilleton reading/task flow.
- Verified: Parent Codex agent ran `npm run type-check`, `npm run lint`, and `git diff --check` after the Package 9 adoption pass. Lint passed with the existing graphic-novel/stories `<img>` and `loadInitial` dependency warnings. Browser verification used a temporary 390px mobile viewport against `/graphic-novel`, `/atelier`, `/missions`, and `/grammar`; routes rendered with no browser console errors. The temporary browser viewport was reset afterward.
- Complete: Missions Package 9 logic completion (`web-frontend/pages/missions.tsx`) — parent Codex agent. Added a real mobile mission switcher bottom sheet wired to existing mission data, objective/deadline copy (`0 of 6 objectives · ends Friday` style), deduped mission queue helpers, mobile mission selection, quick-mission creation from the sheet, and a mobile composer state machine for resting/typing/voice/sent/failed states. Desktop behavior remains intact.
- Verified: Parent Codex agent ran `npm run type-check`, `npm run lint`, and `git diff --check`; lint still only reports the existing graphic-novel/stories image and dependency warnings. Browser verification at 390px opened `/missions`, confirmed the switcher sheet dialog, quick mission CTA, no console errors, and the composer changing into the `Keyboard ready` state when text is entered. Temporary browser viewport was reset afterward.
- Complete: Feuilleton chronological mobile task fly-in (`web-frontend/pages/graphic-novel.tsx`) — parent Codex agent. Added mobile task stops tied to panel/final story moments, an IntersectionObserver-driven fly-in task sheet for the current chronological panel, per-panel "tasks here" launchers, a final-line mobile task stop, a task map that opens tasks at their story location, and a bottom reading bar that opens the next story task instead of scrolling to a task dump. Desktop overlays remain intact.
- Verified: Parent Codex agent ran `npm run type-check`, `npm run lint`, and `git diff --check`; lint still only reports existing image/dependency warnings. Browser verification at 390px on `/graphic-novel` showed the chronological task fly-in anchored to Panel 4, per-story task progress, no console errors, and the temporary browser viewport was reset afterward.
- Superseded: Mobile design correction list was initially treated as an implementation slice. The user clarified on 2026-05-13 that the goal is to rewrite the requirements for further designer work, not to continue implementing that list immediately.
- Complete: Designer follow-up requirements rewritten in `docs/mobile-designer-followup-requirements.md`. Use that document as the corrected request to the design team before any further mobile implementation broadens.
- Complete: Atelier Home mobile design adoption review (`docs/design-handoffs/french-grammar-learning-9/atelier-mobile/screens-home-session.jsx`, `docs/design-handoffs/french-grammar-learning-9/atelier-mobile/system.jsx`, `web-frontend/pages/atelier.tsx`, `web-frontend/components/layout/EditorialMasthead.tsx`) — parent Codex agent. Added the Package 9-style mobile streak action, one mobile next-action card, compact horizontal concept cards, visible Errata Due rows, and a More Today bottom sheet. Desktop parity remains scoped through existing desktop markup/CSS.
- Complete: Atelier Session mobile design adoption review (`docs/design-handoffs/french-grammar-learning-9/atelier-mobile/screens-home-session.jsx`, `docs/design-handoffs/french-grammar-learning-9/atelier-mobile/Atelier Session.html`, `web-frontend/pages/atelier.tsx`, `web-frontend/components/layout/EditorialMasthead.tsx`) — parent Codex agent. Adopted focused mobile session chrome by hiding the app masthead during phone sessions, adding the compact progress top bar, turning concept and round selection into chip-like strips, moving the exercise surface ahead of the reference board, hiding desktop sidebars on mobile, adding feedback slips, and making the action row behave like a sticky single-primary CTA. Browser verification was blocked by the in-app browser localhost policy after implementation; code checks passed.
- In progress: Missions mobile design adoption from reworked archive (`/Users/vincentpechstein/Downloads/French Grammar Learning (1).zip`, `docs/design-handoffs/french-grammar-learning-reworked-1/atelier-mobile/screens-notebook-missions-feuilleton.jsx`, `web-frontend/pages/missions.tsx`) — parent Codex agent. Scope: import the new design package, compare the proposed Missions mobile flow against the current live implementation, and patch the mobile-only Missions surface for chat-first layout, mission switcher, custom mission sheet, composer/voice states, feedback, and sticky controls while preserving desktop behavior.

## Current State

- Workspace: `/Users/vincentpechstein/Downloads/Pixel-lab/ConversationalLanguageLearning`
- Latest designer archive supplied by user: `/Users/vincentpechstein/Downloads/French Grammar Learning (1).zip` (reworked package received 2026-05-13)
- Imported design files are currently untracked at:
  - `docs/design-handoffs/french-grammar-learning-9/`
- Git status at handoff time:
  - `?? docs/design-handoffs/`
- Current tracked implementation edits now include Package 9 mobile adoption in shared masthead, Atelier, Missions, and Feuilleton. Older "no meaningful edits" note is no longer true for the current workspace state.
- The user is frustrated because too much time was spent auditing and too little code changed. Do not restart discovery from scratch.

## Critical User Context

- Latest clarification from 2026-05-13: the list of missing design work should be rewritten as requirements for further designer work. Do not treat that list as an immediate engineering checklist unless the user explicitly asks to resume implementation.
- The user corrected an earlier mistake: do not compare against stale desktop mockups. Start the real application and compare mobile against the live app.
- Goal: import the new mobile prototype, then implement the proposed mobile designs in the actual app.
- If something is still missing from the designer package, implement a best-fit version in the same editorial design language.
- Target is the live web frontend, especially:
  - Atelier home
  - Atelier session
  - Notebook
  - Missions
  - Feuilleton / graphic novel
- Existing desktop functionality and backend behavior must remain intact.

## Designer Package Assessment

Package 9 is better than package 8, but still not a full implementation-ready spec.

What package 9 added:

- Updated `Atelier Mobile.html`
- Updated `Atelier Session.html`
- Updated `screens-home-session.jsx`
- Static visual coverage for the additional session round types:
  - Sentence
  - Paragraph
  - Spoken
  - Conversation

Still missing or incomplete in the designer package:

- Clickable prototype still mostly covers Recognize, Transform, and Write.
- Session round names do not exactly match backend/frontend names.
- Recognize submodes are not fully represented.
- State matrix is not complete enough to drive implementation.
- Component specs are partial.
- Custom mission creation is not fully mocked in mobile.
- Mission switcher is partly conceptual.
- Some “Tweaks” controls remain in prototype and should not ship in app UI.
- Print/static HTML artifacts are stale in places.
- The corrected designer follow-up brief is now `docs/mobile-designer-followup-requirements.md`.

Use package 9 as visual direction, not as a complete product spec.

## Product Decisions Already Made

V1 required:

- Loading skeletons
- Empty states for every main screen
- Failed-send retry for Missions
- Voice recording UI
- Exit confirmation sheet
- Custom mission creation

V2 / nice-to-have:

- Offline / cached read
- Mission completed celebration
- Feuilleton generation with live progress beyond the current simple progress treatment

Design focus:

- Push hardest on final mockups, state matrix, component specs, and interaction notes.
- Moderate fidelity is acceptable for clickable prototype, final copy, and desktop parity notes.

Session rounds:

- Implement all four newer production rounds in mobile fidelity:
  - Sentence
  - Paragraph
  - Spoken
  - Conversation

Live tweak toggles:

- Do not expose prototype tweak toggles in the shipped app.
- Bake one recommended direction.

Editorial voice:

- Use lightly editorial copy: clear utility first, with a little French feuilleton flavor.

Recommended interaction decisions:

- Atelier opens on Home even if there is an active session.
- Active session appears as a Continue card.
- Session is focused mode on mobile.
- Concept context is compact and available through chips/sheet-like presentation.
- Feuilleton is reading-first on mobile.
- Feuilleton tasks are per-panel inline chips immediately below the relevant story panel. The detail can open in a sheet, but the trigger belongs at the chronological panel, not in an all-at-end task pill or task dump.
- Missions should feel chat-first on mobile.

## Existing Live Implementation Map

The app already has much of the backend-backed functionality. The main work is responsive layout, state presentation, mobile chrome, and a few missing states.

### Shared Frontend

- `web-frontend/components/layout/EditorialMasthead.tsx`
  - Shared masthead used by the relevant pages.
  - Best place to add a mobile bottom navigation.
  - `lucide-react` is already installed in `web-frontend/package.json`.

- `web-frontend/services/api.ts`
  - API client already covers most live endpoints.

### Atelier

- `web-frontend/pages/atelier.tsx`

Important anchors:

- `RoundName` is defined near the top:
  - `recognize | transform | sentence | produce | speak | conversation`
- UI labels should map:
  - `produce` -> Paragraph
  - `speak` -> Spoken
- `recognizeModes` includes:
  - `fill`
  - `word_bank`
  - `classify`
- `hydrateSession` currently opens the session view automatically.
- `startSession` creates/continues a real session.
- `TodayView` renders the Atelier home.
- `SessionView` renders the live session.
- `OutputLadderPanel` handles production and voice-oriented rounds.

Backend/API reality:

- Atelier endpoints and services live in:
  - `app/api/v1/endpoints/atelier.py`
  - `app/services/atelier.py`
  - `app/schemas/atelier.py`
- Existing backend supports:
  - today payload
  - sessions
  - active session
  - attempt submission
  - completion
  - errata review flows

High-value implementation steps:

1. Change session hydration so loading an active session does not automatically force `view = 'session'`.
2. Add active session card on Atelier home with Continue CTA.
3. Keep Begin CTA when no active session exists.
4. Add mobile focused session chrome:
   - compact top progress
   - concept chips or compact concept tray
   - round strip as horizontal scroll
   - sticky bottom CTA
5. Add mobile exit confirmation sheet before leaving an in-progress session.
6. Fix mobile overflow/clipping:
   - page `overflow-x: hidden`
   - single-column work grid
   - horizontal scroll chips where needed
   - stable sticky CTA area
7. Preserve all existing desktop behavior.

### Notebook

- `web-frontend/pages/grammar.tsx`

Existing functionality:

- Notebook list fetched from `/grammar/notebook`.
- Detail fetched from selected concept.
- Search and filters exist.
- Notes save exists.
- “Practice this concept” link exists.
- Loading and empty blocks already exist.

High-value implementation steps:

1. Make mobile list/detail behavior feel intentional:
   - search and filters first
   - concept rows compact
   - detail stacks below selected item
   - sections collapsible or visually compact
2. Keep notes save and Practice CTA visible but not oversized.
3. Add bottom spacing for mobile nav.
4. Prevent first viewport from being consumed by stats/large desktop framing.

### Missions

- `web-frontend/pages/missions.tsx`

Existing functionality:

- Mission today payload.
- Mission chooser for active/post-session/weekly/recent.
- Custom mission creation fields already exist.
- Chat turns already exist.
- Voice recording/transcription already exists.
- Audio upload exists.
- Mission completion exists.
- Scene link into Feuilleton exists.

Important anchors:

- `MissionsPage`
- `submitTurn`
- `transcribeAudio`
- `RealityMessenger`
- `MissionChooser`
- `Objectives`
- `SceneLens`

Missing/weak V1 states:

- Failed-send retry should be added.
- Mobile should be chat-first.
- Side panels should become compact sections or sheet-like blocks.
- Custom mission creation needs mobile-friendly disclosure, not a large desktop slab above chat.

High-value implementation steps:

1. Add `failedTurnText` / retry state around `submitTurn`.
2. Show a retry bar in `RealityMessenger` when send fails.
3. Reorder mobile layout so chat thread and composer dominate.
4. Move mission chooser/objectives/scene lens into compact stacked blocks on mobile.
5. Ensure phone shell is `width: 100%; max-width: 100%; min-width: 0`.
6. Preserve current custom mission creation, but make it compact on mobile.

### Feuilleton / Graphic Novel

- `web-frontend/pages/graphic-novel.tsx`

Existing functionality:

- Today payload.
- Scene generation.
- Generation progress block.
- Page or panel rendering.
- Panel tasks and final task.
- Task attempts/correction.
- Completion.
- Queue/target/correction side panels.

Important anchors:

- `GraphicNovelPage`
- `SceneBrief`
- `PanelCard`
- `TaskBox`
- `FinalTask`
- `extractTasks`
- `TargetCard`
- `CorrectionStack`

High-value implementation steps:

1. Make mobile reading-first:
   - scene brief
   - panels
   - per-panel task chips immediately below the relevant panel
   - task detail opened from the panel chip, usually as a compact sheet
2. Add sticky mobile reading/task bar.
3. Prevent speech bubbles and generated panels from causing horizontal overflow.
4. Make `panel-grid` single-column on mobile.
5. Do not show a deferred all-at-end task pill/map on mobile.
6. Preserve desktop panel/task layout.

## Shared Mobile Chrome Recommendation

Add bottom mobile nav in `EditorialMasthead.tsx` at `max-width: 760px`.

Suggested tabs:

- Atelier -> `/atelier`
- Notebook -> `/grammar`
- Missions -> `/missions`
- Feuilleton -> `/graphic-novel`

Use `lucide-react` icons. Suggested icons:

- Atelier: `PenTool` or `GraduationCap`
- Notebook: `BookOpen`
- Missions: `MapPinned`
- Feuilleton: `Newspaper`

Behavior:

- Hide desktop nav on mobile.
- Keep a slim sticky brand/header.
- Add fixed bottom tab bar with safe-area padding.
- Add page bottom padding on mobile so sticky CTAs and tab bar do not overlap.
- On focused Atelier session mobile, hide the bottom nav and use session-specific chrome.

## Backend Notes

Do not add backend endpoints until the frontend confirms it actually needs them. The current backend already supports most V1 mobile behavior.

Potential backend additions only if useful:

- Mission list/switcher endpoint with richer normalized payload.
- “Bridges for today” mobile summary.
- Feuilleton generation status endpoint with richer progress.
- Atelier mobile summary payload.

But for the first implementation slice, prefer using existing payloads.

## API / Naming Reality

Session round names in code are not the same as all design labels:

| Product Label | Frontend/Backend Round |
| --- | --- |
| Recognize | `recognize` |
| Transform | `transform` |
| Sentence | `sentence` |
| Paragraph | `produce` |
| Spoken | `speak` |
| Conversation | `conversation` |

Do not rename backend round values casually. Map labels in UI.

## Suggested First Patch

Make one visible slice before broadening:

1. `EditorialMasthead.tsx`
   - Add mobile bottom nav.
   - Hide desktop nav on mobile.
   - Add safe-area spacing.

2. `atelier.tsx`
   - Stop active session from auto-opening on load.
   - Add Continue card to `TodayView`.
   - Add session exit confirmation.
   - Add focused mobile CSS for `SessionView`.

3. `missions.tsx`
   - Add failed-send retry state.
   - Add mobile chat-first CSS.

Then run:

- `cd web-frontend && npm run type-check`
- `cd web-frontend && npm run lint` if lint config works

After that, start the app and visually inspect:

- `/atelier`
- `/atelier` with an active session
- `/grammar`
- `/missions`
- `/graphic-novel`

## Start Commands

Frontend:

```bash
cd /Users/vincentpechstein/Downloads/Pixel-lab/ConversationalLanguageLearning/web-frontend
npm run dev
```

Backend:

```bash
cd /Users/vincentpechstein/Downloads/Pixel-lab/ConversationalLanguageLearning
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

There are also scripts:

- `start-frontend.sh`
- `start-backend.sh`

The script `start-backend.sh` references `.venv`; verify the local environment before relying on it.

## Verification Checklist

Use real app screens, not stale desktop mockups.

Desktop regression checks:

- Atelier home still loads.
- Starting/continuing a session still works.
- Each session round still submits.
- Notebook search/filter/detail/notes still work.
- Missions create/send/voice/transcribe/complete still work.
- Feuilleton generation/task submission/completion still work.

Mobile checks:

- No horizontal scroll on Atelier Session, Missions, or Feuilleton.
- Bottom mobile nav is visible on main pages.
- Bottom mobile nav does not cover CTAs.
- Atelier active session shows Continue instead of forcing user straight into the session.
- Session exit asks for confirmation.
- Session round strip and concept controls are usable on narrow screens.
- Missions chat composer remains reachable.
- Failed mission send can be retried.
- Feuilleton panels fit the viewport.
- Feuilleton tasks do not overwhelm the reading flow.

## Guardrails

- Do not revert user or existing changes.
- Do not delete the imported design handoff.
- Use existing local patterns and inline `style jsx global` blocks in these pages unless a broader CSS extraction is clearly warranted.
- Keep desktop behavior intact.
- Prefer frontend implementation first; backend additions can follow only when a real gap remains.
- Avoid another long audit before making visible code changes.
