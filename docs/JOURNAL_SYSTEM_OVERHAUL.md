# Journal System Overhaul — shared procedure

**Goal:** bring every product surface (Missions, Feuilleton, Notebook, Settings, the
grammar Session/Do-mode screens) into the **one** visual + interaction language the home
screen now uses — the "La Une" newspaper/edition system — so the whole app reads as one
printed publication instead of five separate apps.

This file is the **shared method** every agent follows when overhauling a surface. Read it
before starting any surface. Do the work one surface at a time; update the status table
and the surface's own audit file as you go.

---

## 0. Single source of truth (read these first)

- **Reference implementation:** `web-frontend/components/laune/LaUne.tsx` (the home screen,
  route `/atelier` `TodayView`) — the canonical components, states, and the CSS "press"
  vocabulary already wired to real data. Copy its patterns; do not invent a new language.
- **Design token contract:** `web-frontend/styles/globals.css` — the `--app-*` custom
  properties (`--app-paper`, `--app-paper-2`, `--app-paper-3`, `--app-sheet`, `--app-ink`,
  `--app-ink-2`, `--app-ink-3`, `--app-blue`, `--app-red`, `--app-yellow`, `--app-serif`)
  plus the phone-shell vars (`--app-viewport-width/height`, `--phone-shell-max`,
  `--phone-safe-top`). These are **theme-aware** (light / dark / system via `data-theme`).
- **Design-reference kit (the "press" language):** `docs/design-reference/press.css`,
  `press-drill.jsx`, `press-forms.jsx`, `press-reward.jsx`, `press-stats.jsx`,
  `serial-*.jsx`, `serial.css`, `serial-world-design-package.md`.
- **Claude Design brief template:** `docs/atelier-home-rework-design-brief.md` — the format
  that produced La Une. Every surface's design prompt follows this shape.

## 1. The design contract (non-negotiable for every surface)

1. **Tokens only.** Use the `--app-*` custom properties for all colour and type. Never
   hardcode hex or define a surface-local palette (the current Missions page defines its
   own `--mission-*` set and hardcodes Inter — that is exactly the drift we are removing).
   If a surface needs a derived value (e.g. a "newsprint gray"), derive it from a token and
   document it.
2. **Theme-aware.** Because you use `--app-*`, the surface must render correctly in light
   AND dark (verify both). No `:root { … }` overrides that pin one theme.
3. **Type system.** EB Garamond serif (`--app-serif`) for headlines/story voice; the grotesk
   for UI chrome. Uppercase letter-spaced kickers, hairline rules, double-rule folios — the
   newspaper furniture from La Une.
4. **Phone-first, single column.** Design 375–430px first; safe-area aware; tap targets
   ≥44px. A desktop variant may widen to a multi-column front page, but is deferred unless
   stated.
5. **Language rule.** French for the publication world (section names, kickers, dates,
   stamps, dispatches); English (later German — the base is `fr_to_de`) only for
   instructional chrome (buttons like "Retry"). Never mix languages in one line.
6. **Honest data.** Every number, name, date, streak, teaser, and estimate maps to a named
   API field. Design the empty/zero/loading/error variant for each. No placeholder shown as
   real. (See the La Une audit lessons: no fake streaks, no invented teasers.)
7. **State completeness.** Every surface designs: loading (skeleton = "coming off the
   press", not a spinner), empty, error ("press notice" with a label + message + Retry —
   reuse the `LuNotice` pattern), the primary populated state, and any done/settled state.
8. **Motion.** transform/opacity/filter only; respect `prefers-reduced-motion`.
9. **Bottom nav untouched.** `PhoneProductNav` stays; do not redesign it in a surface pass.

## 2. Per-surface method (repeat for each surface)

1. **Audit (code-grounded).** Read the page + its backend endpoint(s) + service. Produce
   three lists in `docs/overhaul-<surface>.md`:
   - *Works today* — the real functional capabilities (with file:line evidence).
   - *Missing / should add* — gaps, especially backend capabilities the frontend ignores.
   - *Design drift* — where it breaks the journal contract above.
2. **Decide scope with the owner** — what is design work vs. functional work vs. deferred.
3. **Write the Claude Design brief** (following `docs/atelier-home-rework-design-brief.md`):
   states, data fields, copy deck (French), component specs, deliverables. Put it at the
   bottom of `docs/overhaul-<surface>.md`.
4. **Owner runs the brief through Claude Design**, imports the package.
5. **Implement**: build the components under `web-frontend/components/<surface>/`, wire the
   real API data, delete the drifted styling. Follow the La Une wiring pattern (map every
   prop to a real field; handle every state).
6. **Verify**: `npx tsc --noEmit`, `npm run lint`, `npm run build`, relevant tests, plus a
   live browser check in **both themes** and every state. Update static tests that pin old
   markup (as was done for La Une).
7. **Record**: update the status table below, the surface audit file, and `MASTER_CODEX.md`.

## 3. Surface sequence & status

| # | Surface | Route(s) | Audit | Design brief | Implemented | Notes |
|---|---------|----------|-------|--------------|-------------|-------|
| 0 | Home (La Une) | `/atelier` today | done | `docs/atelier-home-rework-design-brief.md` | **done** | Reference implementation. Dead parcours/legacy code fully removed 2026-08-31 (68 functions + 82 CSS blocks); density pass applied — see `docs/design-overhaul-2026-08-31.md`. |
| 1 | **Missions** | `/missions` | **done** — `docs/overhaul-missions.md` | **drafted** — `docs/overhaul-missions.md` §5 | **done** (2026-07-07) | "Le Courrier" visual pass shipped: `components/courrier/Courrier.tsx` (ported courrier-parts.jsx / courrier.css into `--app-*` tokens, reuses LaUne stamp/notice/skeleton primitives); `pages/missions.tsx` reskinned — desk header, situation standfirst, dépêche slips, graphite repair, phone memo, mic composer, resolved-dossier stamp + minted token, French copy, dark-mode via tokens. Functional layer (5 formats + voice + twist + cadence + reward + archive) preserved. |
| 2 | **Feuilleton** | `/graphic-novel`, `/serial/*` | **done** — `docs/overhaul-feuilleton.md` | **done** — `docs/overhaul-feuilleton.md` §5 | **done** (2026-07-18) | Archive, cast, reader, `FePanel` presentation, and `FeContinuation`/`FeFiled` completion are shipped. Signed-in light/dark live verification completed after the NextAuth preview-origin fix. |
| 3 | **Notebook** | `/notebook`, `/grammar`, `/vocabulary` | **done** — `docs/overhaul-notebook.md` | **done** — `docs/overhaul-notebook.md` §5 | **done** (2026-07-20) | "Les Cahiers" visual pass shipped: `components/cahiers/Cahiers.tsx` ports the design package (`cahiers-parts.jsx` / `cahiers.css` → all `Nc*` primitives on `--app-*` tokens; `.nc` phone-shell + `.nc-flow` no-layout scope). `/notebook` shell redrawn (NcMasthead + NcModeTabs file-dividers + NcFeuilleFile), `/grammar` as the rules index + fiche (NcIndexRow drill-down, NcSec/NcExample/NcErrRow proofreader errata, NcMarginNotes 4-state notes, NcCta), `/vocabulary` as the registre (NcWordRow queue+deck, NcFilingSummary, atlas fold with NcCoverageTrack + NcMasteryMap, nc-dossier). Direct routes use slim masthead + cross-link; embedded views inherit the shell tabs. Detail word-sheet (review/seed/biography) kept working inside the new frame. Verified: tsc/lint/`npm run build` green (62 routes); static tests updated + green; **live-checked both themes** via a temporary dev harness (auth gate blocks the real routes). |
| 4 | **Session / Do-mode** | `/atelier` session view | **done** — `docs/overhaul-session.md` | **delivered** — `Atelier (5).zip` → `components/epreuve/Epreuve.tsx` | **done** (2026-07-18) | Full stage-2 wiring shipped: movable type, proofreader feedback, recap, adaptive lock, confidence, typed repair/re-test, provenance, listen/record. Confidence calibrates SRS; bad sets retire/regenerate; phrase du jour prints on tomorrow's La Une. |
| 5 | Settings | `/settings` | **done** — `docs/overhaul-settings.md` | **drafted** — `docs/overhaul-settings.md` §5 | **done** ("L'administration", WP-C2) | Shipped with the pilot wave; French fiction copy, `--app-*` tokens. |

**2026-08-31 simplicity pass:** a cross-surface overhaul (density, language contract,
dead-code excision, single-CTA rule) is recorded in `docs/design-overhaul-2026-08-31.md` —
read it together with the contract in §1 before touching any surface. Notable IA change:
the Cahier's embedded Progrès tab was removed (it carried the pre-journal English Anki
dashboard); `/progress` + `/achievements` are parked off-nav until their own reskin.

## 4. Conventions for the audit files

Name them `docs/overhaul-<surface>.md`. Structure:
1. One-paragraph purpose of the surface.
2. **Works today** (bullets, file:line evidence).
3. **Missing / should add** (prioritised).
4. **Design drift vs. the journal contract**.
5. **Weave-in vision** (how it should feel as part of the edition).
6. **Claude Design brief** (self-contained, following the template).

## 5. Superseded decisions

- `docs/MISSIONS_OVERHAUL_PLAN.md` (v2) locked "**No separate design agent** — build to the
  lean Mission mockup." That is **superseded** as of 2026-07-06: the owner now wants Missions
  (and the other surfaces) reworked to weave into the La Une journal system via a Claude
  Design pass. Keep the *functional* north-star from that plan (FUN / REAL / CREATIVE,
  ~2–4 min, world reacts, mint-not-score); replace its *visual* direction with this system.
