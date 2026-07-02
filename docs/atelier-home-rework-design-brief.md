# Claude Design Brief — Atelier Home Rework ("the edition cover")

Audience: Claude Design. This is a design request, not an engineering checklist. The aim
is to deliver final mobile frames for the **Atelier home screen** (route `/atelier`,
"today" view) so engineering can implement without open layout decisions.

Mobile-first. Do **not** design desktop for this round — desktop parity is deferred.

---

## Why this screen specifically

Every other mobile surface already matches a delivered Claude Design package
(Feuilleton per-panel tasks, chat-first Missions with switcher / custom / voice sheets,
focused Session mode, Notebook reference layer, Serial World + Press Run). The **home is
the one screen with no single source of truth** — it has drifted across three different
concepts:

1. the original parity checklist (`TodayView` + next-action card + errata rows + a "More
   Today" bottom sheet),
2. the shipped code today (`AtelierEditionHead` + an `atelier-edition-stage` "path /
   roadmap" of `PathStep`s; note: the "More Today" sheet was never built), and
3. the locked overhaul plan (`docs/ATELIER_UIUX_OVERHAUL_PLAN.md`, E1: the "edition
   cover").

Result on the device: a dashboard of competing cards, no single obvious action, and
read-mode density on what should be a one-tap launchpad. We are consolidating on the
**edition cover** and need it drawn definitively.

---

## Baked decisions (reflect these; do not present as alternatives)

- **One screen, one action.** Above the fold it is unmistakable what to do next: a single
  primary CTA. No second competing CTA, no card grid.
- **The home is calm read-mode.** It browses; it does not drill.
- **Ink-shadow is reserved for exercises only.** The offset ink-block shadow is now the
  signature of *do-mode* (the drill/exercise card, and the "ink-set" feedback moment) —
  **not** a general card style. The home, Notebook, Missions, Feuilleton and serial
  covers are **flat**: 1px ink borders and whitespace do the work, no offset shadow.
  Emphasis on the home comes from scale, the red CTA, and typographic hierarchy — never
  from a shadow. (This refines the old "one hero shadow per screen" rule: the hero shadow
  now lives in the exercise, so the home has none.)
- **Keep the soul, drop the tax.** Editorial *Le Feuilleton* flavor stays in the
  masthead, the serif teaser, and copy. Action labels are literal verbs ("Continue",
  "Start today"), never metaphor ("Begin the edition").
- **Progressive disclosure.** Everything statistical (streak detail, errata count,
  signatures, ~min left, "20 min edition", the CEFR promise, the I–VI roadmap) lives
  behind one tap — a default-collapsed "Today's plan" disclosure/sheet — not on the
  cover.
- **The serial is the spine.** The day's scene is the emotional hook; the CTA leads
  toward "what happens next?".
- **Red is for the primary action only.** A separate alert/attention color carries
  errata/warnings. Action-red and alert must be visually distinct (this was a confusion
  source — see the "!" badge issue).

---

## Above-the-fold contents (the cover, in order)

1. Masthead — existing 52px, Bauhaus mark, centered italic serif "Atelier", one right
   action. A **quiet streak** indicator may sit in the right action slot (small, flame +
   "Day N"), reassurance not decoration.
2. A one-line mono kicker: date + "today's edition" (e.g. `MERCREDI 24 JUIN · TODAY'S
   EDITION`).
3. The **serial teaser as the hero**: a serif scene line (the day's beat, e.g. *"Romy ne
   répond plus."*) + a one-line plain-language sub ("One quick beat. Reply to the
   scene.").
4. **One primary CTA** (56px sticky-CTA spec, 1px top rule, flat — no shadow): "Continue"
   (resume) or "Start today". It must land directly on the next answerable item
   (time-to-first-win).
5. Nothing else above the fold. Target: **≤2 short lines of text before the CTA.**

Below / one tap away:
- A single quiet row: "Today's plan · N due" with a chevron, opening the disclosure.

---

## Required frames to deliver

Deliver the home in these states, on warm paper, mobile width, safe-area aware:

1. **Active / returning** — mid-edition, CTA reads "Continue", streak visible, "N due".
2. **First run / empty** — first-ever open: one welcoming serif line, CTA "Start today",
   no stats, no errata. Distinct from the active state.
3. **Caught-up / all done today** — calm "you're caught up" state, lightweight next doors
   (e.g. read the serial archive, browse Notebook), no heavy dashboard. CTA is soft.
4. **"Today's plan" disclosure (expanded)** — the bottom sheet/disclosure that holds
   streak detail, errata count, the I–VI roadmap, signatures, time/effort, CEFR promise.
   Sheet language: grabber, title, rows (≥60px, title-first, one meta line, chevron),
   close. Slide-up 280ms ease-out, 40% ink scrim.
5. **Loading** — masthead stays, centered loading card on paper, skeleton stack, bottom
   nav clearance, no desktop rail leak.
6. **Offline / error** — paper card, retry CTA, cached/offline copy if available
   (currently V2 — mark it V1 or V2 explicitly).

For each frame, one concise note on what renders and which elements are tap-targets.

---

## Reuse / constraints (match production)

- Masthead 52px; bottom nav fixed, four tabs, 60px + safe area (home is **not** focused
  mode, so bottom nav stays).
- Sticky CTA 56px, 1px top rule, keyboard-irrelevant here.
- Chips ≥36px, normal case, no uppercase marketing pills.
- Rows ≥60px, title-first, one meta line, optional chevron.
- Type: keep the serif for the masthead + scene teaser; mono only for the single date
  kicker. Plain sans for the sub and CTA.
- Copy/labels match production names: Atelier, Notebook, Missions, Feuilleton.

---

## What to cut from today's home

- The duplicate serial card (the cover already *is* the serial).
- The standalone mission card on the cover (missions are an opt-in spine surfaced
  ~2–3×/week, not a daily home fixture — keep them in the plan disclosure / their own
  tab).
- The `atelier-edition-stage` I–VI path/roadmap as a default-visible element → into the
  plan disclosure.
- The meta-soup (signatures · ~min left · 20 min edition · CEFR promise) → into the plan
  disclosure.
- Any offset ink-shadow on home cards → flat.

---

## Do not spend design time on

- Desktop home.
- A second primary CTA or a card grid.
- Putting the full mission queue or every spine on the cover.
- Marketing hero / landing treatment.
- Ink-shadow as a general card style anywhere outside the exercise.

---

## Open questions for the designer

- **Kicker language:** keep editorial mono kickers, or plain-language them for A1
  learners? (The "REFERENCE LAYER / ADMINISTRATION LAYER" style kickers read as a tax.)
- **Streak placement:** masthead right-slot vs. a small line under the kicker — which
  keeps the cover calmest?
- **Caught-up state doors:** which 2–3 secondary actions belong there?
- **Offline cached home:** V1 or V2 for this round?

---

## Acceptance criteria

- The cover shows ≤2 short lines before a single primary CTA; all statistics are one tap
  away.
- No offset ink-shadow appears anywhere on the home in any state.
- Action-red and alert/attention are visually distinct.
- Every required state above appears in at least one frame, with tap-targets annotated.
- The package can be handed to engineering with no open layout decisions for the home.
