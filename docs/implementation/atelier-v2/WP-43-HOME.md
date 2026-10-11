# WP-43 — Home and the shell on the nouvelles-pages design

Done by the integration owner on 2026-09-15 after two Opus attempts stalled
before editing. Contract: `docs/design-reference/nouvelles-pages-2026-09-15/`
(`Main.dc.html`, `AccueilSombre.dc.html`, the screen-foot pattern of
`Bilan.dc.html`) and the canvas notes.

## What changed

| Where | Change |
|---|---|
| `journey/journey-copy.ts` | **One chrome language per screen (WP-39 D-3).** `CHROME_KEYS` (eyebrow, start/resume/continue, send, help, retry, finish early, pause, step and stage names, voice controls, listen-first labels…) read French for every control language via `journeyCopy()`; every sentence *said to* the learner (objective, hints, verdict bodies, voice explanations) stays in their language. |
| `journey/JourneyTodayCard.tsx` | The card carries the scene — art, story-blue label, serif title, byline, the learner-language line. The **one red action sits under the card** (`JourneyPrimary`), never inside it. The estimate is French chrome («5 min»). |
| `ui/Feedback.tsx` (`Artwork`) | `collapseWhenAbsent`: the Home card renders **no plate at all** without an image (the artboard forbids the empty striped block); the reader keeps its plate. |
| `journey/JourneySession.tsx` | Step caption is French chrome: «Étape 1 sur 3 · 3 min». |
| `pages/atelier.tsx` | With the journey on screen (`practiceEntry` non-null — WP-16) La Une draws **no second episode card**. The five Home requests go through `oncePerLoad`. |
| `lib/once-per-load.ts` (+ test, `test:once-per-load`, CI) | **WP-39 D-4.** Coalesces identical requests in a 1.5 s window: 9 backend calls per Home load, down from ~130. A failure is shared, not retried five times in one burst. |
| `ui/ScreenFoot.tsx` (+ export) | The screen foot **in the flow**: hairline, paper, 14 px, verdict tint; `margin-top: auto` so it ends the page. Props: `children`, `tone` (`neutral`/`correct`/`wrong`), `className`. |
| `styles/atelier-v2.css` `/* WP-43 */` | On phones the **route shell reserves the tab bar once** (`.app-route-shell { padding-bottom: var(--phone-bottom-nav-space) }`); the session shell's and the screen body's own reservations are folded into it. The floating feedback launcher is hidden on phone widths. |
| `feedback/FeedbackWidget.tsx`, `pages/settings.tsx` | The panel opens from a Réglages row «Signaler un problème» through `FEEDBACK_OPEN_EVENT`, so nothing floats over the reading column on a phone and the feedback path stays. |

## Verified

- `type-check`, `lint` clean; `next build` compiled.
- Node: `journey` (with the new WP-43 block; one pin re-pinned: `speak` is chrome and therefore French everywhere), `atelier-ui` (+ WP-43 block), `once-per-load` 4/4, `journey-latency`, `recovery`, `resume-target`, `self-repair`, `atelier-next` — all pass.
- Backend source scans over the touched files: `test_frontend_pilot_experience`, `test_wp39_qa_walk`, `test_wp37_hooks`, `test_wp38_last_seams`, `test_atelier_honest_edition`, `test_core_mobile_user_flows`, `test_frontend_vocabulary_biography` — 104 passed. Full suite: see STATUS.
- Fake-provider harness, 390 pt, light and dark: Home shows «Aujourd'hui · Le Mistral», art, byline, native line, one red «Reprendre» below the card, no second card, «Demain — …» colophon; **9 requests per load**.

## Open

- The English objective line on the harness («Suggest how you can help…») is the fake provider's, not a defect.
- WP-45's placement/répétition/journal/documents should switch their own foot wrapper to `ScreenFoot` (their handoff says so).
- No file screenshots: the pane's screenshots are not writable to disk from this session.
