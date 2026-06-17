# Atelier — Package G: Geometric Forms & Reward System

Extends `ATELIER_UIUX_OVERHAUL_PLAN.md` (E) — uses the E-0 tokens, the feedback sheet,
the progress bar, and the E-4 session-complete moment. Goal: make the learning screens
feel alive (not empty) and give a genuine reward feeling, **without** going cheesy or
manipulative.

## Locked decisions (owner)
- **Form expression: minimal mark, motion-led.** The logo's forms (blue circle, yellow
  square, red triangle) react through physics; a subtle dot-pair + 1px mouth appears
  *only on reaction*. No names, no persistent faces, no assigned personalities.
- **Reward peak: session end.** Concentrate delight at the end (peak–end rule); only a
  calm micro-hit per correct answer. The session-end seal is variable + collectible.

## Why (research grounding — keep these in mind when tuning)
- Dopamine tracks **anticipation / prediction-error**, not the payout (Schultz) → make
  the seal slightly **variable**, not identical each time.
- **Variable reinforcement** (Skinner) + **endowed-progress/collection** (Nunes & Drèze)
  → a collectible daily seal and a partially-filled weekly set out-pull a fixed "well
  done".
- **Peak–end rule** (Kahneman) → spend the delight at the end; don't over-reward every
  tap (it cheapens).
- **Goal-gradient** (Hull; Kivetz) → the progress bar should accelerate/warm near the
  finish.
- **Competence** (Self-Determination Theory) → surface mastery climbing, not just points.

---

## G1 — The reacting forms (motion-led, minimal mark)
- New `AtelierForms` component (SVG): the three logo forms, prop
  `reaction: 'neutral' | 'correct' | 'wrong'`.
  - correct → a small settle/hop (`translateY`, `var(--dur-fast)`), mouth = gentle up-curve.
  - wrong → a small wince-tilt (`rotate(-7deg)`, reduced opacity), mouth = flat/down.
  - neutral → calm, marks minimal or absent.
- Placement: in the drill margin / beside the exercise (fills the empty space the owner
  flagged), small and quiet — a recurring motif, not an attention magnet.
- `prefers-reduced-motion` → reactions degrade to a static state change (no animation).
- Files: add to `web-frontend/components/ui/`; render inside the E-2 drill surface
  (`atelier.tsx` do-mode) near the answer area.

## G2 — Per-answer micro-reward (calm, understated)
- Correct: `AtelierForms` hop + an "ink sets" touch on the chosen answer + a **soft
  native haptic** (`@capacitor/haptics` light impact; install if absent, gate on
  `isNativePlatform()`).
- Wrong: the wince + the existing `FeedbackSheet` (E-3) with the AI correction. No
  punitive animation beyond the tilt.
- Keep it fast and small — the peak is at session end, not here.

## G3 — Goal-gradient progress ("the press run")
- The `.atelier-progress-bar` ("PRESS RUN") **warms/accelerates in the final ~20%** — a
  shift toward `--accent-action` and a subtle pulse on the last stretch — to exploit the
  goal-gradient effect. Respect reduced-motion.

## G4 — Session-end seal (the peak)
- In the E-4 session-complete screen: the three forms **lock into a printer's-colophon
  seal** stamped onto the page. The **ink-block shadow is allowed here** — this is the
  one hero moment.
- **Variable + collectible:** the seal's arrangement/colorway varies per edition,
  derived deterministically from the edition number/date (a small generator), so each
  day's seal is a little different → variable reinforcement.
- **Collection loop:** show the open loop ("Nº 12 · 11 collected · 3 to a complete week")
  — endowed progress + Zeigarnik. Completing a week → a special-edition seal.
- Pair the seal with **tomorrow's serial hook** so the peak also plants anticipation.

## G5 — The seal collection (Notebook)
- A quiet, editorial "collection" surface in Notebook showing earned seals — the
  collectible archive. Low-key, browse mode.

## G6 — Guardrails (deliberately not cheesy / not manipulative)
- No loss-aversion streak panic, no lives/gems economy, no slot-machine variable-ratio
  compulsion. Variability serves **delight**, not addiction. Dignified and on-brand —
  which is also the ethical choice.

---

## Assets
- Forms and seals are **SVG** (no raster). Seal variation = a small deterministic
  generator (arrangement + colorway from edition number). Reuse the logo geometry
  already in `AtelierMark`.

## Suggested PRs
1. PR G-1: `AtelierForms` component + drill-margin placement + reduced-motion.
2. PR G-2: per-answer micro-reward (hop + ink-set + haptic) wired to the answer result.
3. PR G-3: goal-gradient progress bar.
4. PR G-4: session-end variable/collectible seal in E-4 + tomorrow's hook.
5. PR G-5: seal collection surface in Notebook.

## Definition of done
The learning screens feel inhabited (the forms react with restraint, never cheesy); a
correct answer gives a small calm hit; finishing the edition delivers a memorable,
slightly-different, collectible seal that leaves a weekly loop open — engaging by design,
manipulative by none.
