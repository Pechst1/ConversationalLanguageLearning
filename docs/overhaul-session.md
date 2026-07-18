# Overhaul — Grammar Session / Do-mode (`/atelier` session view) · "L'Épreuve"

Part of the journal-system overhaul; method + contract in `docs/JOURNAL_SYSTEM_OVERHAUL.md`.
Audited 2026-07-07 against `SessionView` + exercise panels in `web-frontend/pages/atelier.tsx`
(~3047–4300), the shared primitives in `web-frontend/components/ui/`, and
`web-frontend/components/layout/EditorialMasthead.tsx`. Extended 2026-07-07 with the
"L'Épreuve" elevation brief (owner direction: make the session stunning + maximally effective).

## Purpose

The grammar Session ("Do-mode", "press run") is the core learning loop: a focused,
one-exercise-at-a-time run through each concept's rounds — recognise (fill → classify →
word-bank ramp), transform, then the output ladder (sentence → spoken → conversation) and a
produce paragraph — with a rule sheet on demand, contextual feedback, retry, AI review, and a
printed recap. Reached from La Une's "Commencer/Reprendre la séance".

## 1. Works today (code-grounded) — this is the reference surface

Unlike Missions and the Feuilleton reader, the Session view is already the design-system
reference (it *was* the E0–E4 overhaul that seeded the tokens + primitives):

- **Theme-aware**: renders under `.atelier-page` → global `--app-*` tokens (light + dark).
- **Token-pure primitives**: `ExerciseShell`, `FeedbackSheet`, `ProgressBar`, `Button`,
  `Card` — zero hardcoded colours.
- **Voice wired**: the `speak` round records via MediaRecorder and transcribes.
- **Full loop**: rule-first ramp, `ConceptRulePanel` on demand, `FeedbackSheet` +
  `ExerciseFeedbackMoment`, retry/resubmit, `CorrectionAiReview` (async AI second look),
  report-exercise, `ErrataStack`, `RecapModal` with minted collectibles, `SentenceXRay`,
  submit-as-you-go persistence (attempts survive reload), press-run progress bar.
- **Reward economy attached**: flawless recognize screens mint `logo_token`s live; a flawless
  session mints a `gilt_seal` at completion.
- The one real drift found — `EditorialMasthead` force-pinning `--app-*` to light on every
  page it tops (session, notebook, serial) — was **fixed 2026-07-07**
  (`color-mix` translucent paper bg, token overrides removed).

**Verdict:** no drift-repair reskin needed. What follows is an *elevation* — pushing the best
surface from "clean" to "stunning + maximally effective", per owner direction.

## 2. Learning-engine status

> **Updated 2026-07-18.** Items #1-6 and #8 below are implemented. The adaptive lock is
> persisted by `app/api/v1/endpoints/atelier.py:310-356`; typed repair/re-test by
> `app/services/atelier.py:3359` and the attempt endpoint; confidence capture and SRS
> calibration by `app/services/atelier.py:60-74` and `:5626-5640`; provenance, audio, and
> recording render in `pages/atelier.tsx:3409`, `:4357`, and `:4482`; the quality flywheel
> lives at `app/services/atelier.py:3106`; and phrase rollover/La Une delivery at
> `app/services/atelier.py:5573`.
>
> The remaining connective item is #7. Current open work and acceptance criteria are
> canonical in `docs/audit-2026-07-18-status-and-work-packages.md`; do not re-implement
> completed items from this historical design brief.


1. **Adaptive mastery gate.** The ramp is fixed (~15 drills/concept) regardless of
   performance. Consult live correctness to skip ahead after 3 clean recognize items and to
   extend on misses; allow early plate-lock ("everything clean") using the existing
   time-budget machinery (`unified_srs._apply_time_budget`, `UserGrammarProgress.score`).
   Mostly backend; the UI needs one new moment (the early-lock stamp).
2. **Miss → typed micro-repair + same-session re-test.** After a wrong answer's feedback,
   the learner retypes the corrected sentence once (production of the fix), and a variant of
   the item is re-injected 2–3 exercises later. Backend + one new UI step.
3. **Confidence tap.** Optional *sûr / pas sûr* tap before reveal; feeds the SRS a
   calibration signal (confident miss ≠ hesitant miss). One small UI element + attempt field.
4. **Provenance margin note.** Errata carry their source; show *why this item today*
   ("Manqué mercredi, dans ta lettre à M. Marchand"). Data exists; needs a designed slot.
5. **Model audio + shadowing in `speak`.** You can record but never hear the target.
   TTS exists in the stack (`generateSpeech`, feuilleton panel audio). Add "écouter" on the
   example sentence; hear → speak → compare.
6. **Quality flywheel (no UI).** Wire report-exercise + `AtelierGenerationEvent` error rates
   to auto-retire and regenerate bad items.

Connective moves (flagship, cross-surface):
7. **Final conversation round = two real turns with a serial character** (the Missions turn
   engine already does in-character replies + quiet corrections).
8. **"La phrase du jour"**: the learner's best produced sentence is typeset onto tomorrow's
   La Une with their byline (recap already stores produced sentences).

## 3. Design drift vs. the journal contract

None remaining. The masthead theme pin was fixed 2026-07-07. The still-live `.ph` load-error
fallback now uses `--app-*` tokens; it was retained because the markup is reachable.

## 4. Weave-in vision — "L'Épreuve" (setting tomorrow's type)

The session is already *named* press run — commit fully: **the learner is setting the type
for tomorrow's edition.** Progress is a typesetter's composing stick filling with lead slugs;
corrections are proofreader's marks on the learner's own sentence; the finished session is a
locked plate stamped **BON À TIRER** (the real French printing term for "good to print");
the recap is *l'épreuve* — the proof sheet. Word-bank chips are movable type; each concept's
existing Bauhaus `visual_motif` assembles piece-by-piece as its rounds complete. The final
round hands into the serial world, and the best sentence gets printed in tomorrow's paper.
Same tokens, stamps, and hairlines as La Une / Le Courrier — one publication, its print shop.

---

## 5b. Wiring status (updated 2026-07-18)

The "L'Épreuve" design package arrived (`Atelier (5).zip`) and is ported to
`web-frontend/components/epreuve/Epreuve.tsx` (all ~45 primitives, TSX + typed props;
`epreuve.css` embedded in `LEpreuveStyles`, converted to `--app-*` tokens with theme-aware
`--ep-*` derived values via `color-mix` + a global-theme `--ep-bon` dark override; design
package preserved in `docs/design-reference/epreuve.*`).

**Wired into `SessionView` (verified live, light + dark, with real session data):**
- `EpShell` wrapper + `LEpreuveStyles` (theme-aware — `.ep` renders dark in dark mode).
- `EpTopbar` composing-stick progress (slugs set/current from `completedDrills`/`totalDrills`)
  + "Terminer" (the finish gate moved here as `finishDisabled`).
- `EpEyebrow` (round · mode · i/n), `EpConcept` + `EpMotif` (the concept's Bauhaus
  `visual_motif` primitives mapped to house-forms via `epMotifPrimsFrom`, assembling one more
  piece per round), `EpRule` rule sheet (wraps the existing `ConceptRulePanel`).
- `EpBar` ink press-bar as the Check action ("Vérifier la ligne"), replacing `ActionRow`.

**Stage 2 is wired.** Exercise bodies use movable-type primitives
(`pages/atelier.tsx:4017-4028`); proofreader feedback uses `EpGalley` and the repair marks
(`:3674-3684`); the recap starts at `EpRecapHead` (`:4686`) and maps tallies, proofs,
collectibles, streak, BAT stage, and phrase. The learning moments are live:
`EpProvenance` (`:3409`), `EpLock` (`:3513`), `EpConfidence` (`:3587`), model listen
(`:4357`), and recording (`:4482`), backed by persisted adaptive locks, micro-repairs,
same-session re-tests, confidence, and calibration.

Remaining work is recorded in `docs/audit-2026-07-18-status-and-work-packages.md`.

## 5. Claude Design brief — "L'Épreuve"

> Copy from here down into Claude Design.

# Design brief: "L'Épreuve" — the grammar session as setting tomorrow's type

## Context
You are elevating the grammar-session ("Do-mode") surface of a French-learning app whose home
is a newspaper front page ("La Une"), whose Missions are a correspondence desk ("Le Courrier"),
and whose serial is the illustrated supplement. This surface is already the app's cleanest —
token-pure, theme-aware, right interaction skeleton — so this is an **elevation pass, not a
rescue**: keep the skeleton (one exercise at a time, rule on demand, check → feedback → next),
raise the craft, and stage five new learning moments. Study first:
- `web-frontend/components/laune/LaUne.tsx` — masthead, kickers, rubber stamps (`LuStamp`),
  press notices, ink press-bar CTA, print-in done-state.
- `web-frontend/components/ui/ExerciseShell.tsx`, `FeedbackSheet.tsx`, `ProgressBar.tsx` —
  the primitives you are restyling/extending (props stay).
- `web-frontend/pages/atelier.tsx` `SessionView` (~line 3047) + panels: `RecognizePanel`,
  `TransformPanel`, `OutputLadderPanel`, `ProducePanel`, `ConceptRulePanel`, `SentenceXRay`,
  `ExerciseFeedbackMoment`, `ErrataStack`, `RecapModal`.
- `web-frontend/styles/globals.css` — the `--app-*` tokens. Tokens only; light AND dark.

## The concept
**The learner is a typesetter finishing tomorrow's edition.** Each exercise sets a line of
type. Errors get proofreader's marks in red ink. A finished concept locks its plate. The
session ends stamped **BON À TIRER**, and the recap is *l'épreuve* — the proof sheet of what
was set, what was corrected, and what got minted. The metaphor must never obstruct speed:
this is a ~3–8 minute daily loop; every flourish must cost zero extra taps.

## Anatomy (mobile-first 375–430px, one column; keep the existing skeleton)
1. **Topbar** — close (×), the composing-stick progress (see below), Finish. Slim, sticky.
2. **The exercise sheet** (`ExerciseShell`) — eyebrow kicker (round · mode · i/n), the concept
   title in serif italic, rule toggle (?) opening the rule sheet (`payload.rule_panel` +
   anchor examples), and the exercise body per round type.
3. **Check → feedback → next** — single primary action (ink press-bar), then the feedback
   moment, then next. Never two competing CTAs.
4. **Recap** — l'épreuve (proof sheet) modal at completion.

## The signature pieces (design these carefully)

### A. The composing stick (progress)
Replace the plain bar: a typesetter's stick where each completed drill sets a small lead slug
into the current line (`completedDrills` / `totalDrills`, concept boundaries visible as line
breaks). Compact enough for the sticky topbar; a fuller version may appear in the recap.

### B. Proofreader's marks (the feedback language — the heart of this brief)
When an answer is wrong, mark the learner's OWN sentence like an editor's galley: strikethrough
on the error span, a caret with the fix in red in the margin, the "why" as a graphite pencil
note underneath. Data available: `correction.errata[]` with `learner_text`,
`corrected_target`, `why_wrong`/`reason`, `display_label`; `payload.xray` gives
`{sentence, marks[]}` for span anchoring. Correct answers get a small BON stamp, not a modal.
Design both inline (under the exercise) and sheet (`FeedbackSheet`: status correct/wrong,
title, rule line, correction items, Next) treatments. Include the async
**AI second look** state (`ai_review.status: pending → complete`) as a discreet "relecture en
cours…" marginal note that resolves in place.

### C. Movable type (the word-bank round)
Word-bank tokens (`tokens[]` → build `answer_tokens[]`) become type slugs set into a line —
tap to set, tap to unset, the meaning cue (`meaning_cue`, English) printed above as the
compositor's instruction. Fill blanks (`fill.items[]`: prompt with a visible blank + choices)
become empty sorts in a set line; classify (`labels[]`) becomes sorting slugs into labelled
cases. Same interactions as today — only the physical language changes.

### D. The assembling motif (per-concept progress)
Every concept ships a Bauhaus `atelier_blueprint.visual_motif` (`canvas`, `primitives[]` with
roles, `concept_metaphor`). Stage it small beside the concept title: one primitive prints into
place as each round of that concept completes; the motif is whole when the concept is done.
Design the empty/partial/complete states and a reduced-motion variant (no animation, state
changes only).

### E. BON À TIRER + l'épreuve (completion)
- Early mastery lock (new feature): when the engine ends a concept early because everything
  was clean, stamp the concept's plate "PLOMB VERROUILLÉ" or simply strike it done — design
  this moment so skipping feels like an earned promotion, not missing content.
- Session completion: the whole page gets the **BON À TIRER** stamp, then the recap —
  *l'épreuve*: a proof-sheet layout showing lines set (`recap.attempts`), concepts
  strengthened (`strengthened`), errata filed (`errata_logged`), the minted collectibles
  (`minted_collectibles`: logo tokens; `gilt_seal` for a flawless run — reuse the existing
  Seal art), streak line (`streak_before/after`), and the handoff (back to La Une / on to the
  Feuilleton). Include a slot for **"La phrase du jour"**: the learner's best produced
  sentence typeset as a boxed quote with their byline, flagged "à paraître dans l'édition de
  demain".

## New learning moments to stage (design all five)
1. **Confidence tap** — before Check, an optional two-chip tap: *sûr* / *pas sûr*. Must be
   skippable by just hitting Check; zero friction.
2. **Typed micro-repair** — after a wrong answer's marks, one inline step: "Recopie la
   correction :" with the corrected sentence as a ghost to type over; then Next. Design its
   correct/incorrect-retype states.
3. **Re-test flash** — when a repaired item's variant returns later in the session, a tiny
   marginal tag: "Retour · déjà corrigé" so the learner recognises the loop.
4. **Provenance note** — a graphite margin line under the eyebrow when an item comes from a
   past error: "Manqué mercredi · lettre à M. Marchand" (source data exists on errata).
5. **Écouter + shadowing (speak round)** — the example sentence gets a play affordance
   (existing TTS); flow: écouter → parler (record: idle/recording/transcribing states exist) →
   the transcript comes back with proofreader's marks like any other answer.

## States to design (all of them, light + dark)
1. Recognize/fill mid-exercise (with rule sheet open and closed variants).
2. Word-bank (movable type) mid-build.
3. Transform with a wrong answer → proofreader's marks → typed micro-repair.
4. Correct-answer moment (BON stamp, no modal) + the confidence tap before it.
5. Speak round: écouter / recording / transcribing / marked transcript.
6. AI second-look pending → resolved.
7. Early concept lock (mastery skip) moment.
8. Session complete: BON À TIRER + l'épreuve recap (with and without gilt seal; with and
   without phrase du jour).
9. Resume mid-session (composing stick partially set), loading skeleton (press style),
   error press-notice.

## Copy rules
French for the print-shop world (stamps, round names may keep their editorial labels,
"Recopie la correction", "Relecture en cours", "Bon à tirer", "L'épreuve", "La phrase du
jour"); English only for out-of-fiction chrome. Never mix languages in one line. Write ALL
copy for all states — real strings.

## Hard constraints
- `--app-*` tokens only; light + dark; EB Garamond serif for sentences/titles (French
  sentences are the hero type — keep them large), grotesk for chrome.
- **Keep the interaction skeleton and component contracts**: one exercise at a time; single
  primary action; `ExerciseShell`/`FeedbackSheet`/`ProgressBar` props may be extended, not
  broken; all existing logic (answers, retry, AI review, report, persistence) stays.
- Speed first: no flourish may add a tap or block input; animations transform/opacity/filter
  only; every animated moment needs a reduced-motion variant.
- Honest data only — every element maps to the named payload fields above; design the empty
  variant of anything optional (no xray, no motif, no provenance, TTS unavailable).
- Do not redesign the bottom nav, La Une, or the rule *content* (rule_panel text comes from
  the concept blueprint).

## Deliverables
1. High-fidelity mobile frames (390px) for states 1–9, light + dark for at least states
   2, 3, 5, and 8.
2. Component spec: composing stick, proofreader's-mark system (span marks, caret, margin
   note, pencil why), type-slug/word-bank pieces, assembling motif, stamps (BON, BON À TIRER,
   plate lock), confidence chips, repair step, provenance note, épreuve recap — each with
   props mapped to the payload fields named above, spacing scale, and transition specs.
3. Full French copy deck for all states.
4. Migration note mapping each piece onto what it replaces/extends in `SessionView` and the
   `components/ui` primitives (explicitly listing which props are added vs unchanged).
