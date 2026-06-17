# Mobile Design Parity Checklist

Source materials:
- `docs/mobile-designer-followup-requirements.md`
- `docs/design-handoffs/french-grammar-learning-reworked-1/atelier-mobile/system.jsx`
- `docs/design-handoffs/french-grammar-learning-reworked-1/atelier-mobile/screens-home-session.jsx`
- `docs/design-handoffs/french-grammar-learning-reworked-1/atelier-mobile/screens-notebook-missions-feuilleton.jsx`

Global mobile language:
- Warm paper background, ink text, no cards-inside-cards, no shadows.
- 52px masthead with Bauhaus mark, centered italic serif route title, one right action.
- Bottom nav is fixed, four tabs, 60px plus safe-area inset.
- Cards and sheets use 1px ink borders, sharp corners, and restrained spacing.
- Sheet motion is slide-up, 280ms ease-out, 40% ink scrim, grabber, title, content, sticky footer.
- Sticky CTA is one primary action, 56px height, 1px top rule, keyboard-aware.
- Chips are at least 36px tall, normal case where possible, never pill-heavy marketing UI.
- Rows are at least 60px, title first, one meta line, optional chevron.
- Feedback slips use green/red variants, concise correction copy, optional target sentence.

## Atelier

Route: `/atelier`

Loading:
- Expected: mobile masthead remains visible, centered loading card on warm paper, thin border, skeleton stack.
- Current target: `AtelierLoading` in `web-frontend/pages/atelier.tsx`.
- Verify: no desktop sidebar/rail leaks, bottom nav clearance remains.

Empty:
- Expected: calm caught-up state, one serif headline, one primary CTA, side doors moved into a compact list/sheet.
- Current target: `AtelierEmptyState`.
- Verify: first viewport is not consumed by desktop stats.

Error/offline:
- Expected: paper card with red/blue accent, retry CTA, cached/offline copy if available.
- Current target: loading failures in `loadToday`.
- Gap to watch: explicit offline cached state is still V2 unless implemented.

Active/default:
- Expected: "Today's practice" entry, next-action card, due/errata/fragile metrics, horizontal concept cards, Errata Due rows, More Today sheet entry.
- Current target: `TodayView`, `MobileNextActionCard`, `MobileErrataDue`, `MobileMoreTodaySheet`.
- Verify: one primary action only; card CTA is full-width and not shadowed.

Completed/caught-up:
- Expected: no heavy dashboard; show caught-up copy and lightweight next doors.
- Current target: `AtelierEmptyState`.
- Verify: bottom nav is not obscuring content.

Sheet open:
- Expected: More Today bottom sheet with scrim, grabber, title, rows, close CTA.
- Current target: `MobileMoreTodaySheet`.
- Verify: escape tap on scrim closes; content does not overlap bottom nav.

Keyboard/voice open:
- Expected: voice capture uses clear red recording state and transcript handoff.
- Current target: session `OutputLadderPanel` voice capture.
- Verify: voice controls stay above sticky CTA.

## Session

Route/state: `/atelier` with active session view.

Loading:
- Expected: focused session shell, not full desktop page.
- Current target: `SessionView` loading/empty fallbacks.

Empty:
- Expected: mobile session empty card with begin/return action.
- Current target: `MobileSessionEmpty`.

Error/offline:
- Expected: inline feedback slip or state card with retry/exit.
- Gap to watch: session-specific offline state is not fully separated from generic errors.

Active/default:
- Expected: masthead hidden in focused mode, compact progress topbar, concept focus card, round strip, exercise surface, sticky bottom CTA.
- Current target: `SessionView`, `MobileSessionTopbar`, mobile action row.
- Verify: no bottom nav in focused session mode; no horizontal overflow.

Submitted:
- Expected: feedback slip reveal, CTA turns red, label becomes Continue, next round slides in.
- Current target: `FeedbackSlip` style blocks and `action-row`.
- Verify: submitted feedback does not push CTA below viewport.

Completed:
- Expected: completion/recap sheet, exit back to Atelier.
- Current target: recap modal and completed state.
- Gap to watch: completion celebration is V2.

Sheet open:
- Expected: exit confirm as bottom sheet, copy: "Discard progress?" and "Keep going".
- Current target: `session-exit-sheet`.

Keyboard/voice open:
- Expected: sticky CTA remains keyboard-aware; spoken round shows red mic, waveform/status, transcript into answer.
- Current target: `OutputLadderPanel` voice UI.

## Notebook

Route: `/grammar`

Loading:
- Expected: masthead, reference-layer intro, search/filter skeleton, list skeleton.
- Current target: loading branch in `GrammarNotebookPage`.

Empty:
- Expected: "No matches" style state below sticky search/filter, clear-filter CTA.
- Current target: empty concept list state.

Error/offline:
- Expected: paper error card, retry and cached read-only option.
- Gap to watch: explicit cached read-only state is V2 unless added.

Active/default:
- Expected: search and level chips first, title-first rows, one meta line, detail opens inline on mobile and can collapse by tapping selected concept again.
- Current target: list/detail layout in `web-frontend/pages/grammar.tsx`.
- Verify: stats do not consume first viewport; detail typography matches workbook/reference sheet.

Completed/submitted:
- Expected: notes saved state, saved badge, Practice this concept CTA.
- Current target: notes form and save status.

Sheet open:
- Expected: any secondary filters/details use bottom-sheet language if detached.
- Gap to watch: most Notebook detail is inline, not sheet-based.

Keyboard/voice open:
- Expected: notes textarea clears bottom nav and keyboard space.
- Verify: sticky nav does not cover save notes button.

## Missions

Route: `/missions`

Loading:
- Expected: chat-first shell with loading thread placeholders, not queue-first list.
- Current target: `MissionLoadingState`.

Empty:
- Expected: no-active mission state with one create CTA.
- Current target: `MissionEmptyState`.

Error/offline:
- Expected: "Missions are offline" card, retry, create custom mission from sheet.
- Current target: `MissionErrorState`.

Active/default:
- Expected: chat thread dominates; mission metadata is compact; objective/deadline copy sits above thread; composer fixed at bottom.
- Current target: `RealityMessenger`, mobile `.phone-shell`.
- Verify: mission switcher contains active plus recent completed only.

Submitted:
- Expected: sent bubble, assistant reply, accepted-count badge explained by objective progress.
- Current target: turn cards and correction chips.
- Gap to watch: accepted badge language should be clearer if still exposed as "Accepted 2/4".

Failed:
- Expected: failed-send slip with retry and edit affordance.
- Current target: failed message bar in `RealityMessenger`.

Completed:
- Expected: completion card/summary and optional Feuilleton bridge.
- Gap to watch: richer completion celebration is V2.

Sheet open:
- Expected: mission switcher bottom sheet; custom mission 3-step bottom sheet with validation and sticky back/next/create controls.
- Current target: `MobileMissionSwitcher`, `CustomMissionSheet`.

Keyboard/voice open:
- Expected: composer grows safely; voice recording takeover sheet with transcript handoff.
- Current target: mobile composer states and `mobile-voice-sheet`.

## Feuilleton

Route: `/graphic-novel`

Loading:
- Expected: reading-first shell with generation/loading card and simple step indicators.
- Current target: `feuilleton-loading`, `mobile-generation-steps`.

Empty:
- Expected: source/current-events card, one create CTA, no desktop side rail on first viewport.
- Current target: empty scene branch.

Error/offline:
- Expected: generation failure card with retry/create options; no silent toast-only failure.
- Gap to watch: some generation errors still surface primarily through toast.

Active/default:
- Expected: reading-first story panels, actual panel image, caption, dialogue/speech bubbles, per-panel task chip below relevant panel.
- Current target: `MobilePanel`, `MobileStoryTaskLauncher`, task stops.
- Verify: task entry appears chronologically, not as all-at-end task dump.

Submitted:
- Expected: task sheet closes or shows success/correction feedback slip; task chip updates to reviewed state.
- Current target: `MobileCorrectionNote`, task launcher completion state.

Completed:
- Expected: final completion card after panels and tasks: panels done, tasks done, one grammar takeaway, Back to Atelier CTA.
- Current target: `MobileCompletionCard`.

Sheet open:
- Expected: per-panel task opens in bottom sheet/fly-in with grabber and sticky submit footer.
- Current target: `MobileTaskSheet`.

Keyboard/voice open:
- Expected: task textarea/input remains above sticky footer and safe area.
- Verify: sheet footer does not cover input.

## Visual QA Frames To Capture

Minimum repeatable mobile frames:
- `atelier-home-active`
- `atelier-more-sheet`
- `atelier-session-active`
- `notebook-list`
- `notebook-detail`
- `missions-active-chat`
- `missions-switcher-sheet`
- `missions-custom-sheet-step-1`
- `missions-voice-sheet`
- `feuilleton-empty-or-active`
- `feuilleton-task-sheet`
- `feuilleton-completed`

Capture method:
- Use `web-frontend/scripts/capture-mobile-states.mjs`.
- Store frames under `docs/mobile-visual-checks/latest/`.
- Compare against this checklist before broadening implementation.
