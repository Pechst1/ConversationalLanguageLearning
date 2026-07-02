> Absorbed into `ATELIER_UIUX_OVERHAUL_PLAN.md` (Package E) — use that as the master
> UI/UX spec. This doc remains as the focused "first 15 seconds" rationale/detail.

# Atelier — Package D: First 15 Seconds (cut text, speed the first win)

Goal: a first-time or returning user gets to a single, satisfying correct answer in
under ~15 seconds, with the editorial brand kept as *chrome* but never as a
comprehension tax. Theme: clarity over cleverness; one obvious action per screen.

This is mostly frontend (`web-frontend/pages/atelier.tsx`, `components/layout/`,
`styles/globals.css`). It overlaps deliberately with
`ATELIER_LEARNING_LOOP_PLAN.md` (rule card B2.1, vocab rail B2.4) — cross-reference,
don't duplicate. Keep the *Le Feuilleton* aesthetic; reduce reading load.

Principle: the brand metaphor (signatures / in press / edition) is beautiful but it
makes an A1 learner decode the product's vocabulary on top of French. Keep the flavor
in headers and the serial; make every *action* literal and instant.

---

## Task D1 — Trim the today/edition header

File: `web-frontend/pages/atelier.tsx` (today view ~line 865; meta strings at
~837 `signatures set`, ~843 `~N min left · 20 min edition`, ~889 `Today's edition · in
press`, ~1096 `CEFR PROMISE`).

- Reduce the above-the-fold header to: **date + one primary CTA**. The CTA copy is the
  literal next action ("Continue" / "Start today"), not "Begin session · 20 min".
- Move `signatures`, `~min left`, `20 min edition`, and the CEFR promise strip into a
  collapsible "Today's plan" disclosure or a weekly summary screen — not the default
  session header.
- Drop the "20 min edition" framing from the entry point; long sessions are opt-in.
  Lead with "one quick beat".

Acceptance: the today screen above the fold shows ≤2 lines of text before the CTA;
CEFR/signatures/time are reachable but not shown by default.

---

## Task D2 — Time-to-first-win

- Returning user with an in-progress session: the primary CTA lands **directly on the
  next answerable item**, not on the edition overview. Skip or one-tap-through the
  intermediate roadmap for the resume case.
- New user: after the serial welcome, route straight into the first (easiest) item of
  the first concept (pair with the difficulty ramp in `ATELIER_LEARNING_LOOP` B2.2 and
  the rule-first card B2.1 — the rule shows, then *immediately* an easy fill item).
- Add a brief correct-answer microinteraction (subtle check + progress tick). No
  confetti; keep it editorial. Reuse existing styling tokens in `globals.css`.

Acceptance: from app open, a returning user reaches an answerable item in ≤2 taps;
a correct answer gives immediate visible feedback.

---

## Task D3 — Progressive disclosure across the drill

File: `web-frontend/pages/atelier.tsx` drill/session view; rule card is
`payload.rule_panel`.

- Rule card: expanded on a concept's **first** drill, collapsed thereafter
  (implement once — shared with `ATELIER_LEARNING_LOOP` B2.1).
- Hide the vocabulary chip rail on recognize drills (shared with B2.4); surface target
  vocab only where it's used (produce step).
- Stats, CEFR, streak details live behind a tap, not inline on every drill.

Acceptance: a recognize drill shows, above the fold: concept title (short) → the
exercise. Rule/vocab/stats are one tap away, not stacked inline.

---

## Task D4 — Tighten drill chrome / one focus per screen

Today the drill stacks: rubric + long title + vocab chips + rule card + tab row +
exercise. Reduce vertical chrome so the *exercise* is the focal point above the fold.

- Shorten the rubric/title block (the concept name can wrap to ≤2 lines; the rubric
  word "RECOGNIZE/SENTENCE" can be a small tag, not a heading-sized line).
- Collapse the tab row (`A·FILL / B·WORD-BANK / C·CLASSIFY`) into a slim progress
  indicator; the active mode is implied by where you are in the ramp.
- Audit spacing in `globals.css` / the drill styled-jsx for oversized gaps.

Acceptance: on a 390pt-wide device, the exercise prompt + first answer control are
visible without scrolling for the common drills.

---

## Task D5 — Lean into the serial as the spine (lightweight)

The serial (Feuilleton) is the strongest retention hook (narrative pull). Without a
big rebuild:
- Frame the daily entry around the story beat where natural ("today's scene" →
  "unlock it / continue it by completing today's drills").
- Ensure the serial CTA is at least as prominent as the grammar CTA on the home/today
  screen.

Acceptance: the home screen makes the story beat a first-class, visible reason to
return today, not a secondary card.

---

## Out of scope (note, don't build here)
- StatusBar plugin / further native polish (separate package).
- Full serial gameplay rework (separate package) — D5 is framing only.

## Suggested PRs
1. PR D-1: D1 header trim + D2 time-to-first-win.
2. PR D-2: D3 progressive disclosure + D4 drill chrome (coordinate merges with the
   Learning Loop PRs touching the same components).
3. PR D-3: D5 serial framing.

## Definition of done
A returning user opens the app and is answering a question within ~15 seconds and 2
taps; the editorial brand still reads as premium, but no screen makes the learner read
a paragraph of product meta-text before acting.
