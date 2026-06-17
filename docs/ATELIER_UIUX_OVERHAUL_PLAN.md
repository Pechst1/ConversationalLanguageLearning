# Atelier — Package E: UI/UX Overhaul ("The daily edition, beautifully simple")

Absorbs and extends `ATELIER_FIRST_15_SECONDS_PLAN.md` (use this as the master UX
spec). Coordinates with `ATELIER_LEARNING_LOOP_PLAN.md` (rule→apply) and
`ATELIER_AI_FIRST_GENERATION_PLAN.md` (content is now AI-generated + AI-corrected).

## North star

A calm, premium **daily French edition you can actually finish.** Keep the editorial
soul that makes the app distinctive (not a cartoon), but borrow Duolingo's discipline
(one obvious action per screen, instant feedback, a clear path) and Anthropic's
restraint (whitespace, typographic hierarchy, warm neutrals, no gimmicks).

The single organizing idea: **two registers.**
- **Read mode** (Today cover, Notebook, Feuilleton): rich, editorial, browse-able.
- **Do mode** (drills): stripped to one exercise, one action, instant feedback.

Most of today's clutter comes from running *read-mode density on do-mode screens.*
Split them and the rest follows.

## Design principles

1. **One screen, one action.** It is always unmistakable what to do next.
2. **Only the necessary, always.** Everything else is one tap away (progressive
   disclosure). No meta-soup headers.
3. **Keep the soul, drop the tax.** Editorial flavor stays in chrome and copy; action
   labels are literal ("Continue", "Check", "Next"), never metaphor ("Begin the
   edition").
4. **Show, don't tell.** Calm, meaningful motion and instant feedback over explanatory
   text.
5. **The story is the spine.** The Feuilleton serial is the emotional hook; the daily
   path leads toward "what happens next?".
6. **Guide, don't overwhelm.** One highlighted next step, soft (no hard locks) — matches
   the existing product direction in `MASTER_CODEX.md`.

---

## E0 — Design-system pass (do first; everything else rides on it)

Files: `web-frontend/styles/globals.css`, `web-frontend/components/ui/*`,
`tailwind.config.js`.

The palette is already Anthropic-adjacent (warm paper `--app-paper`, ink `--app-ink`,
serif `EB Garamond` + sans `Inter`). Tighten it into a real system:

- **Color roles, one accent per screen:** ink = text; **red = the one live action /
  "now"**; blue = links/info; yellow = reward/highlight. Never use 3 accents on one
  screen.
- **Keep the signature ink-block shadow** (`box-shadow: Npx Npx 0 var(--app-ink)`) as a
  deliberate, *sparing* brand accent — reserve it for the one hero element per screen
  (the primary CTA, the cover, the "edition printed" seal). Do mode stays otherwise
  flat and quiet; the ink block is the punctuation, not the texture. Never stack it on
  multiple elements on the same screen.
- **Type scale (lock it):** display serif (cover/headlines), title, body sans, caption,
  mono (counters). ~5 sizes, two weights (400/500) — kill the heavier weights.
- **Spacing rhythm:** an 8pt grid, generous vertical air. Define `--space-*` tokens and
  use them; remove ad-hoc paddings in the drill styled-jsx.
- **Component diet:** one `Card`, one primary `Button`, one focal `Exercise` shell, one
  `FeedbackSheet`, one `ProgressBar`. Audit and delete one-off patterns across
  `atelier.tsx`, `notebook.tsx`, etc.
- **Motion tokens:** `--dur-fast` (120ms), `--dur` (220ms), one easing. Respect
  `prefers-reduced-motion`.

Acceptance: a one-page style reference (Storybook page or a `/dev/styleguide` route)
showing the locked tokens + the 5 core components. Every later task uses only these.

---

## E1 — Today / the "edition cover" (read mode, minimal)

File: `web-frontend/pages/atelier.tsx` today view (`.ph` / `.edition` / `AtelierEditionHead`).

- Above the fold: **date · one big CTA · the serial teaser · a quiet streak.** Nothing
  else. The CTA reads "Continue" (resume) or "Start today" and lands directly on the
  next answerable item.
- Demote to a tap-to-open "Today's plan": signatures, `~min left`, `20 min edition`,
  the CEFR promise, the I–VI roadmap. Default-collapsed.
- Replace the time/effort framing with "one quick beat"; long sessions are opt-in.
- The serial teaser is a first-class card ("Today's scene → continue the story"), at
  least as prominent as the grammar CTA.

Acceptance: the cover shows ≤2 short lines before the CTA; everything statistical is
behind one tap.

---

## E2 — Drill / the "do" surface (the highest-impact screen)

File: `web-frontend/pages/atelier.tsx` session view + `.mobile-session-topbar`.

Redesign to **one exercise, centered, with breathing room:**

- **Slim top bar:** a thin "press run" progress bar + a close (×). Drop the
  `A·FILL / B·WORD-BANK / C·CLASSIFY` tab row — mode is implied by the ramp; show it as
  a tiny caption at most.
- **The exercise is the hero:** prompt large and legible, answer controls directly
  below, lots of whitespace. No vocab chip rail (target vocab is woven into the
  sentence now — `ATELIER_AI_FIRST_GENERATION_PLAN`).
- **Rule on demand:** replace the stacked rule card with a small "?" / "rule" affordance
  that opens the `rule_panel` as a sheet — except on a concept's *first* drill, where it
  shows once, expanded, then the first (easiest) item (the rule→apply loop from
  `ATELIER_LEARNING_LOOP` B2.1/B2.2).
- **One primary button:** "Check" → then "Next". Never two competing CTAs.
- **Ramp:** fill → classify → word-bank, easy→hard.

Acceptance: on a 390pt device, prompt + first answer control are visible without
scrolling; exactly one primary action on screen.

---

## E3 — The feedback moment (teach in the instant of the mistake)

Backend AI correction now exists (LLM-primary). Surface it as the emotional core of
learning:

- **Correct:** a calm "ink sets" microinteraction — a check, a brief color wash, the
  answer line settling. Optional gentle haptic on device. No confetti.
- **Wrong:** a `FeedbackSheet` slides up with the AI tutor's contextual explanation +
  the targeted fix (not "Rebuild as: {target}"), and the relevant rule line. Actions:
  "Try again" / "Got it, next".
- Keep it short and warm; the AI copy should be one or two sentences.

Acceptance: every answer produces immediate visible feedback; a wrong answer teaches in
context, in ≤2 sentences, with a single clear way forward.

---

## E4 — Session complete / "edition printed" (close the loop, plant the hook)

New end-of-session screen:

- An editorial "today's edition — printed" moment (a stamp/seal motion), not a stats
  dump.
- Three things only: what you practiced, the streak ticking up, and **tomorrow's hook**
  (the next serial beat teaser → anticipation).
- One CTA: "Read today's scene" (→ Feuilleton) or "Done".

Acceptance: finishing a session feels like a small ritual and gives one reason to come
back tomorrow.

---

## E5 — Notebook / the "archive" (read mode, rich is fine here)

Files: `web-frontend/pages/notebook.tsx`, `grammar.tsx`, `vocabulary.tsx`.

This is where editorial density belongs. Make it a calm, browse-able library:

- Grammar rules you've learned (the `rule_panel`s), as a readable reference.
- Vocabulary deck (FSRS state visible but quiet).
- Progress/CEFR as a considered page, not scattered across drills.

Keep inline Grammar/Vocabulary switching (already built). Just apply E0 tokens and
trim chrome.

Acceptance: Notebook reads like a well-typeset journal; nothing competes with the
Atelier "do" flow.

---

## E6 — Feuilleton / lead with the scene

File: `web-frontend/pages/graphic-novel.tsx`.

- Open on the **scene/panel**, not metadata. "Act in French" (write the line that
  changes the story) is the primary action.
- Tie back: completing today's drills "develops" today's edition; the serial is the
  payoff. Make that connection explicit and visible.

Acceptance: the serial leads with story and a single clear "act" action.

---

## New / creative mechanics (pick from these, don't build all)

- **The press run:** the session progress bar styled as a print run filling.
- **The seal:** an "edition printed" stamp on completion — the one moment of delight.
- **Daily ritual:** a quiet, warm streak ("Day 12 — unbroken") framed as a ritual, not
  a pressure gauge; no loss-aversion dark patterns.
- **Warm-up → main → cool-down arc:** open with one easy recall item, end with a small
  production win, so every session has a satisfying shape.
- **"You write the next line":** lean the serial into co-authorship — the learner's
  French sentence visibly changes the next panel.
- **Page-turn transitions** between sections (editorial motion, cheap to implement).

---

## What to cut (the "less text" mandate, concretely)

- The today meta-soup (`signatures · ~min left · 20 min edition`, CEFR promise strip)
  → collapsed.
- The drill tab row and the disconnected vocab chip rail → gone.
- Stacked drill chrome (rubric + big title + chips + rule card + tabs) → one focal
  exercise.
- Metaphor-as-instruction in action labels → literal verbs.

---

## Implementation sequence (PRs)

1. **PR E-0:** design-system tokens + 5 core components + styleguide route.
2. **PR E-2:** drill "do" surface (highest impact; uses E-0).
3. **PR E-3:** feedback moment (correct/wrong) on top of the AI correction backend.
4. **PR E-1:** today cover trim + time-to-first-win routing.
5. **PR E-4:** session-complete + tomorrow's hook.
6. **PR E-5/E-6:** Notebook archive polish + Feuilleton lead-with-scene.
7. **PR E-motion:** page-turns, ink-set feedback, haptics, reduced-motion.

## Definition of done

A returning user opens the app, sees a clean cover, taps once into a single focused
exercise, gets instant warm feedback, finishes a short edition with a small ritual and
a reason to return — and at no point reads a paragraph of product meta-text or wonders
what to do next. The app looks unmistakably premium and unmistakably *one* product.
