# Mobile Designer Follow-Up Requirements

This is the corrected request for the design team. It is not an implementation checklist for engineers. The aim is to close the remaining mobile design gaps so engineering can implement without guessing.

## Baked Decisions

These decisions should be reflected in the next design package, not presented as toggles or alternatives.

- Mobile is additive. Preserve the existing desktop product; do not redesign desktop flows except for explicit parity notes.
- Remove all Tweaks panels and live option controls from designer-facing canvases. They were useful for exploration, but the product direction is now decided.
- Feuilleton tasks are per-panel. Each story panel that has a task gets an inline task chip immediately below that panel. Do not use an all-at-end pill, task dump, or deferred task map as the main mobile pattern.
- Feuilleton task detail may open in a bottom sheet, but the entry point must remain attached to the chronological panel.
- Missions is chat-first on mobile. The composer and conversation loop are the primary screen, with mission controls moved into sheets.
- The mission switcher sheet shows only the active mission and recently completed missions. Do not show every queued/recommended mission in that sheet.
- Custom mission creation is a 3-step bottom sheet: topic/context, target concepts, confirm/name.

## V1 Design Deliverables

### 1. Feuilleton Per-Panel Task Flow

Deliver final mobile frames for the Feuilleton reading experience with six story panels.

Required states:

- Panel before task chip is revealed.
- Panel after task chip fades in below the panel.
- Task chip opened into the task sheet.
- Task submitted with success feedback.
- Task submitted with correction-needed feedback.
- Final completion card after all six panels are read and all panel tasks are submitted.

Completion card content:

- Panels done count.
- Tasks done count.
- One grammar takeaway.
- Primary CTA: Back to Atelier.

Interaction note:

- Task chip appears 150ms after its panel enters the viewport.
- Task order must follow story chronology.

### 2. Missions Chat-First Flow

Deliver final mobile frames for Missions with the composer and chat thread as the visual priority.

Required states:

- Default active mission chat.
- Typing in composer.
- Message submitted.
- Failed send with retry/edit affordance.
- Voice recording takeover sheet with transcript handoff.
- Mission switcher sheet showing active + recent completed only.
- Empty/no-active mission state.

Custom mission creation:

- Step 1: topic/context.
- Step 2: target concepts.
- Step 3: confirm/name.
- Include validation, keyboard-aware layout, back/next controls, and final create CTA.

### 3. State Matrix Artboard

Create one 720x520 artboard on the warm paper background.

Rows:

- Home
- Session
- Notebook
- Missions
- Feuilleton

Columns:

- Loading
- Empty
- Offline / error
- Active / default
- Submitted
- Failed
- Completed

Each cell needs one concise note describing what renders. Mark each cell as V1 required or V2 nice-to-have.

### 4. Component Spec Sheet

Create one 720x680 artboard documenting mobile component specs.

Include:

- Bottom nav: icon + label, 60px height plus safe-area handling.
- Masthead: 52px, Bauhaus mark, serif italic title, one action.
- Sheets: grabber, title, content area, sticky footer behavior.
- Sticky CTA: 56px, 1px top rule, keyboard-aware.
- Chips: 36px minimum height, normal case, no uppercase treatment.
- Cards: 1px ink border, sharp corners.
- Rows: 60px minimum, title first, one meta line, chevron.
- Composer: 44px minimum-height field, send button, voice mic.
- Feedback slips: green/red variants, check/cross icon, "+1 erratum", optional target sentence.

### 5. Interaction Notes Sheet

Create one 720x640 artboard with annotated interaction specs.

Include:

- Sheet open/close: slide up, 280ms ease-out, 40% ink scrim.
- Feedback slip reveal: slide up, 180ms, no bounce.
- Session advance: CTA turns red, label becomes Continue, tap advances, next round slides in from right over 220ms.
- Voice recording takeover: bottom sheet slides up, red mic button, waveform, stop closes sheet and shows transcript in composer.
- Feuilleton per-panel task reveal: task chip fades in 150ms after panel enters viewport.
- Exit confirm: bottom sheet, not nav pop. Copy: "Discard progress?" and "Keep going".

### 6. Desktop Parity Notes

Create one 720x480 artboard listing intentional mobile differences.

Include:

- Mobile has no sidebar; secondary controls live in sheets.
- One primary action per screen.
- Session hides tabs and bottom nav in focused mode.
- Feuilleton uses per-panel task chips; desktop may show richer side-by-side task context.
- Missions is chat-first, not mission-queue-first.
- Masthead is slimmer and does not include secondary nav links.

## V2 / Nice-To-Have Design Work

These are useful after V1 is locked:

- Offline cached-reading states beyond a simple error/empty treatment.
- Mission completion celebration.
- Rich Feuilleton generation progress.
- Full mission archive browsing.
- Additional desktop refinement, only after mobile parity is stable.

## Do Not Spend Design Time On

- A Tweaks panel or live decision toggles.
- An all-at-end Feuilleton task pill as the primary mobile pattern.
- A mission switcher that lists every queued mission.
- A mobile sidebar.
- A landing page or marketing hero.
- Large desktop redesigns unrelated to mobile parity.

## Acceptance Criteria

- The package can be handed to engineering without open layout decisions for Feuilleton tasks, mission switching, custom mission creation, or core component dimensions.
- Every required V1 state is visible in at least one artboard or annotated frame.
- Copy and labels match production names where possible: Atelier, Notebook, Missions, Feuilleton; Paragraph maps to `produce`, Spoken maps to `speak`.
- Mobile frames account for safe areas, keyboard overlap, and sticky bottom actions.
