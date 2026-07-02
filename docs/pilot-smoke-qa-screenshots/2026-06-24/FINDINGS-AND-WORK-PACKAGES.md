# Pilot Smoke QA — Findings & Work Packages (2026-06-24)

Source: `docs/pilot-smoke-qa-screenshots/2026-06-24/` (`initial-run/`, `final-run/`).
Capture harness: `web-frontend/scripts/capture-mobile-states.mjs`.
Reviewed against live code on branch `codex/serial-season-engine-production`.

---

## 0. What this run actually proves (and what it does not)

- **Viewport:** mobile only — 390×844 @3x. No desktop/tablet frame, even though desktop parity is a standing requirement (`docs/mobile-implementation-agent-handoff.md`).
- **Coverage:** the manifest saved **9 frames**. The capture script defines ~20, including the interactive states that carry the real risk — `atelier-session-active`, `atelier-more-sheet`, `missions-switcher-sheet`, `missions-custom-sheet-step-1`, `missions-voice-sheet`, `feuilleton-task-sheet`, `feuilleton-final-task`, `notebook-detail`, `vocabulary-practice-sheet`. **None of those were captured in this run.** "All green" covers the static landing state of each route only.
- **Green ≠ correct.** Two of the nine "ok: true" frames are misleading (see P0-1, P0-2). The readiness probes assert "something rendered", not "the right thing rendered".
- **Initial → final delta:** initial run failed `atelier-home-active` and `missions-active-chat` on text-based probes (`Begin session|Continue session`). Those probes were swapped for selector-based ones (`.atelier-edition-stage`, `.missions-page .mission-stage`) and the run went green. The fix made the probe pass — it did not make the captured state correct.

---

## 1. Missing important points

### P0 — correctness bugs (root-caused in code)

**P0-1 · Double masthead on `/serial/episode`** — `final-run/serial-episode-detail.png`
The frame shows the global Atelier masthead **and** a second in-page masthead stacked above "Season 1 / Episode".
Root cause: `pages/serial/episode.tsx` is a re-export of `./episode/[index]`, so its pathname is `/serial/episode`. `OWN_SHELL_ROUTES` in `web-frontend/lib/product-shell.ts:65` registers `/serial`, `/serial/cast`, `/serial/episode/[index]` — **but not `/serial/episode`**. So `routeUsesOwnProductShell('/serial/episode')` is `false`, `Layout` renders its own `EditorialMasthead` (`components/layout/Layout.tsx:106`), and the page renders a second one (`pages/serial/episode/[index].tsx:74`).
Compounding: the smoke harness itself targets the broken URL — `capture-mobile-states.mjs:164` uses `route: '/serial/episode?index=0'` instead of the canonical `/serial/episode/0`. So the harness is exercising the one URL form that triggers the bug.

**P0-2 · "atelier-home-active" is occluded by the first-run onboarding modal** — `final-run/atelier-home-active.png`
The frame is named "active" but the screenshot is dominated by the onboarding overlay ("Your daily French serial starts here / START TODAY"). The active edition (`Mercredi 24 juin · Episode 1`) is only partly visible behind it. The readiness probe (`.atelier-edition-stage .ph/.current-panel/.spine`) matches the stage *behind* the modal, so the frame passes while the state under test is never actually shown. The active home has **not** been visually verified by this run.

### P1 — product/UX gaps

**P1-3 · The "!" feedback launcher reads as a stuck error badge.** It appears bottom-right on every authenticated screen (atelier, notebook, vocabulary, feuilleton, serial ×3, settings, missions). It is the `FeedbackWidget` launcher (`components/feedback/FeedbackWidget.tsx:152` — a 36×36 bordered box with glyph `!` and a hard shadow), not an error. In the editorial palette a lone `!` reads as "something is wrong", and it overlaps card content (e.g. the "Food & drink" set card in `vocabulary-notebook.png`, a mission card in `missions-active-chat.png`).

**P1-4 · Feuilleton presents two competing primary CTAs.** `feuilleton-active-or-empty.png` shows a red **"NEW SCENE →"** in the create panel and, directly below, a red **"CREATE FIRST SCENE →"** in the empty state — two equally-weighted primary actions doing nearly the same thing on one screen. Needs one primary.

**P1-5 · The pilot/test account is empty, so "active" states are never exercised.** Account is "Mobile Capture" (`settings.png`): Notebook `0 STARTED / 0 DUE ERRATA`, Vocabulary `0 DUE / 0 FRAGILE / 6 NEW · 0%`, Serial "No installments filed yet", Episode "Episode not filed". Most named-"active" frames render empty states. The smoke run cannot certify the populated experience until it runs against a seeded account.

**P1-6 · Field/string polish.**
- Settings email is clipped mid-string: `mobile-capture-1782323011727@…` (`settings.png`).
- Cast "MODEL SHEET ASSET" field surfaces a raw internal path `assets/serial/characters/user/model-sheet…` as user-facing copy (`serial-cast.png`).

### P2 — QA harness gaps

**P2-7 · No desktop/tablet capture.** Parity regressions (the explicit non-goal of breaking desktop) cannot be caught by a mobile-only run.
**P2-8 · No negative assertions.** Probes only check presence. Add assertions: exactly one masthead per route, onboarding dismissed before "active" capture, no unexpected error surfaces.
**P2-9 · Partial run shipped as the record.** Only 9/~20 frames saved; the interactive sheets/sessions (the risky surfaces) are absent. Either capture the full set or rename the artifact to "landing-states only".
**P2-10 · Seeded-account fixture missing.** A deterministic populated account is needed so active/due/installment states are reproducible across runs.

---

## 2. Work packages for the implementation agent

> Scope rule (from the handoff): mobile work is additive; **do not regress desktop**. Each WP lists files + acceptance criteria.

**WP-1 — Fix double masthead on the serial episode route** *(P0-1, small)*
- Add `/serial/episode` to `OWN_SHELL_ROUTES` and `resolveProductSection` in `web-frontend/lib/product-shell.ts`, **or** remove the `pages/serial/episode.tsx` re-export and make the harness/links use the canonical `/serial/episode/[index]`.
- Update `capture-mobile-states.mjs:164` to `/serial/episode/0`.
- Accept: `/serial/episode?index=0` and `/serial/episode/0` both render exactly one masthead; other serial routes unchanged.

**WP-2 — Onboarding must not occlude the captured "active" home** *(P0-2, small)*
- Decide the rule: the daily-serial onboarding modal should not show for an account with an active edition/returning state (or the "active" capture must dismiss it first).
- Update the `atelier-home-active` probe to assert the onboarding modal is closed before screenshot; add a separate, intentionally-named `atelier-onboarding` frame for the first-run overlay.
- Files: `web-frontend/pages/atelier.tsx` (onboarding trigger condition), `capture-mobile-states.mjs`.
- Accept: returning account opens straight to the active edition; first-run overlay captured under its own frame name.

**WP-3 — Resolve the Feuilleton dual-primary CTA** *(P1-4, small; needs design call → §3)*
- Collapse to a single primary action per state in `web-frontend/pages/graphic-novel.tsx`. Likely: when no scene exists, show only "Create first scene"; once a scene exists, "New scene" becomes primary and the empty card is gone.
- Accept: at most one red primary CTA visible per Feuilleton state.

**WP-4 — Feedback launcher affordance** *(P1-3, small; needs design call → §3)*
- Replace the bare `!` glyph with an unambiguous feedback affordance and ensure it never overlaps interactive card content (offset above bottom nav and any sticky CTA). File: `components/feedback/FeedbackWidget.tsx`.
- Accept: launcher is not mistakable for an error badge; no overlap with cards/CTAs at 390px.

**WP-5 — Copy/field hygiene** *(P1-6, small)*
- Settings email: show full address or middle-truncate (`mobile-…@domain`) rather than clipping; verify at 390px. File: `web-frontend/pages/settings.tsx`.
- Cast model-sheet field: present a human label / thumbnail instead of the raw `assets/...` path, or hide the internal path from the learner-facing form. File: `web-frontend/pages/serial/cast.tsx`.
- Accept: no raw internal paths or clipped identifiers in user-facing fields.

**WP-6 — Seeded pilot account fixture** *(P1-5, P2-10, medium)*
- Provide a deterministic populated account (started concepts, due errata/vocab, ≥1 filed installment, ≥1 archived episode) the capture script can authenticate as.
- Files: capture/seed tooling under `web-frontend/scripts/` + backend seed (coordinate with `app/services`), env wiring in `capture-mobile-states.mjs`.
- Accept: re-running the smoke produces populated active/due/installment frames deterministically.

**WP-7 — Harden the smoke harness** *(P0-1, P2-7/8/9, medium)*
- Add a desktop viewport (≥1280×800) alongside mobile.
- Capture the full frame set (sheets + session states), or split into clearly-labelled "landing" vs "interactive" manifests; do not present a partial run as complete.
- Add negative assertions: exactly one `EditorialMasthead` per route; onboarding dismissed before active capture; no error surface present.
- Files: `web-frontend/scripts/capture-mobile-states.mjs`.
- Accept: a run fails (not silently passes) on duplicate chrome, onboarding occlusion, or a missing frame.

Suggested order: **WP-1, WP-2** (P0) → **WP-7, WP-6** (make QA trustworthy + repeatable) → **WP-3, WP-4, WP-5** (polish, after the design calls in §3).

---

## 3. Design input needed from Claude Design

1. **Feuilleton CTA hierarchy (WP-3).** Which single action is primary in the no-scene state vs the has-scene state, and what the empty "No scene on the stand / Task sheet locked" card should look like once "Create first scene" is the only primary. Need final frames for: empty, generating, scene-ready.
2. **Feedback affordance (WP-4).** A feedback launcher that does not read as an error/alert in the editorial palette — glyph/label, resting vs open state, and its safe position relative to the bottom nav and sticky CTAs at 390px.
3. **First-run onboarding vs active home (WP-2).** When the daily-serial onboarding overlay should appear, how a returning/active user enters, and the dismissal/return interaction — so "active home" is a distinct, designed state from "first run".
4. **Empty vs populated states across surfaces (WP-5/P1-5).** Designed empty states are mostly present; confirm the intended *populated* frames for Atelier home (active edition), Notebook (started/ due-errata), Vocabulary (due/fragile), Serial index (filed installments) and Episode detail — these are what the seeded account should reproduce.
5. **Cast "model sheet asset" presentation (WP-5).** How the learner avatar / model-sheet should be surfaced in the POV form instead of a raw asset path (label, thumbnail, or hidden).
6. **"!" / error-state language globally (P1-3).** A consistent visual vocabulary distinguishing *feedback*, *error*, and *attention/badge* so persistent affordances aren't confused with failures.

---

# Round 2 — After the P0/P1 fixes (mobile-first; desktop deferred)

Round-1 (WP-1…WP-7) is reported fixed; the `/serial/episode` double-masthead fix is confirmed in `web-frontend/lib/product-shell.ts:43,72`. With correctness handled, the next move is **not** more QA breadth (desktop is explicitly out of scope for now). It is to make the shipped UI match the team's own already-locked design spec.

## The gap that matters

`docs/ATELIER_UIUX_OVERHAUL_PLAN.md` ("Package E") is the locked UI/UX spec. Its locked decisions —
*"visual identity: clean/minimal, ink-block shadow as a **sparing** brand accent (one hero element per screen)"* and *"one screen, one action"* — are exactly what the captured screens violate today: every card carries a border + ink-shadow, red does double duty (primary action **and** alert), and the Atelier home is a dashboard of competing surfaces rather than a single daily call-to-action. The spec exists; the implementation hasn't caught up to it. That delta is the work.

## Design-language verdict

Keep the language — it is a real asset (editorial *Le Feuilleton* register, on-theme for "learn French through a daily serial", ownable, premium, un-cartoonish). The problem is **execution discipline, not direction**:
- ink-shadow is applied to *everything*, so nothing leads (violates the locked "one hero per screen");
- red = action and red = alert collide (the "!" confusion, "DUE ERRATA");
- mono "REFERENCE LAYER / ADMINISTRATION LAYER" kickers are a comprehension tax on an A1 learner already decoding French (violates "keep the soul, drop the tax").
Verdict: **refine, don't rebrand.** Enforce restraint — fewer boxes, more whitespace, one ink-shadow hero, disciplined red.

## Redesign the Atelier home? Yes — "refocus", per E1

Today's home is read-mode density on what should be a one-tap launchpad. Collapse it to the **edition cover**:
- Above the fold: **date · one serif scene-teaser · one red primary CTA ("Continue") · a quiet streak.** Nothing else.
- Demote streak detail, errata count, mission, signatures, time, CEFR promise, the I–VI roadmap into a default-collapsed **"Today's plan ▸"** disclosure.
- Exactly **one** ink-shadow hero; literal CTA verb (never "Begin the edition").
- The CTA lands directly on the next answerable item (time-to-first-win).
(Acceptance from E1: ≤2 short lines before the CTA; everything statistical is one tap away. See the current-vs-proposed mockup in chat.)

## Work packages (continue the implementation agent's queue)

> These map 1:1 onto Package E and should be built in its locked PR order (E-0 → E-2 → E-3 → E-1 → E-4 → E-5/E-6 → motion). Do not paste vendored design JSX/CSS; rebuild on the real tokens.

**WP-8 — E-0 design-system pass** *(do first; everything rides on it)*
Tokens + the 5 core components (`ExerciseShell`, `ProgressBar`, `FeedbackSheet`, etc. — partly present per roadmap) finalized in `web-frontend/styles/globals.css` and `components/ui/`, verified on `/dev/styleguide`. Encode the locked rules as tokens: an **ink-shadow utility scoped to do-mode only** (the exercise/drill card and the "ink-set" feedback moment) — read-mode surfaces (home, Notebook, Missions, Feuilleton, serial covers) are flat, 1px ink border + whitespace, no offset shadow; and **separate red-action vs alert/attention colors** so they can never collide. Audit and strip ink-shadow from all non-exercise surfaces.
Accept: ink-shadow appears only inside the exercise/feedback surfaces; no offset shadow on any read-mode card; action-red and alert color are distinct tokens; styleguide route renders all five components.

**WP-9 — E-2 drill "do" surface** *(highest impact)*
One centered exercise, slim "press-run" progress bar + close, no `A·FILL/B·WORD-BANK/C·CLASSIFY` tab row, no vocab chip rail, rule-on-demand sheet (expanded once on a concept's first drill), exactly one primary button ("Check" → "Next"). File: `web-frontend/pages/atelier.tsx` session view + `.mobile-session-topbar`.
Accept: at 390pt, prompt + first answer control visible without scrolling; exactly one primary action.

**WP-10 — E-3 feedback moment**
Warm instant correct/wrong feedback wired into the live AI-correction flow (FeedbackSheet is built but not yet wired into the drill loop per roadmap #5/#6). Teach in the instant of the mistake; minimal text.
Accept: every checked answer produces an in-context feedback state, not a toast.

**WP-11 — E-1 Atelier home → edition cover** *(the redesign above)*
File: `web-frontend/pages/atelier.tsx` today view (`.ph` / `.edition` / `AtelierEditionHead`). Implement the cover; move meta into the collapsed "Today's plan"; CTA routes to first answerable item.
Accept: cover shows ≤2 lines before the CTA; flat cover (no ink-shadow); stats behind one tap. (Full design brief: `docs/atelier-home-rework-design-brief.md`.)

**WP-12 — E-4 session complete / "edition printed"**
Close the loop with a small ritual (seal/almanac reward already built — `components/ui/Seal.tsx`) and a "tomorrow's hook" teaser into the next serial beat. Reuse existing reward components; do not rebuild.
Accept: finishing an edition shows a printed-summary ritual + a reason to return.

**WP-13 — E-5/E-6 Notebook archive + Feuilleton lead-with-scene**
Notebook stays read-mode rich (archive density, page-turn feel); Feuilleton leads with the scene and keeps per-panel task chips (per `docs/mobile-designer-followup-requirements.md`). Resolve the dual-primary CTA from round-1 WP-3 here if not already done.
Accept: Feuilleton opens on the scene; one primary per state.

**WP-14 — E-motion pass**
Page-turns, ink-set feedback, haptics, and a full `prefers-reduced-motion` path. Apply only after surfaces settle.
Accept: motion is calm and meaningful; reduced-motion fully supported.

**WP-15 — Seeded-baseline smoke loop** *(closes round-1 WP-6/WP-7)*
After each surface lands, re-run the hardened mobile smoke against the seeded populated account and commit the frames as the visual baseline. This is the regression net for the redesign.
Accept: a populated baseline set exists and is refreshed per surface; negative assertions (one masthead, onboarding dismissed, no error surface) pass.

Suggested order: **WP-8 → WP-9 → WP-10 → WP-11 → WP-12 → WP-13 → WP-14**, with **WP-15** running after each.

## Where Claude Design input is still needed (round 2)

- **E-0 color semantics:** the exact action-red vs alert/attention palette split, and the single canonical "hero shadow" spec (offset, weight) so engineering applies it once per screen.
- **E-1 edition cover:** final frames for the cover in three states — active/returning, first-run, and "all done today" — plus the expanded "Today's plan" sheet.
- **E-2 drill ramp:** the canonical fill → classify → word-bank "do-mode" frame and the rule-on-demand sheet (and its first-drill expanded variant).
- **E-3 feedback:** correct and correction-needed moments as designed states (not toasts).
- **E-4 completion ritual:** how the existing seal/almanac reward composes into the "edition printed" close + tomorrow's-hook teaser.
- **Kicker language:** whether to keep/drop the "REFERENCE LAYER / ADMINISTRATION LAYER" mono kickers, or replace with plainer labels for A1 learners.
