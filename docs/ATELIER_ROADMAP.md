# Atelier Roadmap — single front door

The one index for the Atelier **learning-quality + UX + modes** workstream. Each row
links a detailed plan and gives its current status and dependencies. For iOS/native and
broader project history, see `MASTER_CODEX.md`.

Legend: ✅ done · 🟡 in progress · ⬜ next · ⛔ superseded/absorbed

## Dependency-ordered plan

| # | Package | Detailed doc | Status | Depends on |
|---|---------|--------------|--------|-----------|
| 1 | Exercise correctness fix (validator, fallback, contract) | `ATELIER_EXERCISE_FIX_PLAN.md` | ✅ done | — |
| 2 | AI-first generation & correction | `ATELIER_AI_FIRST_GENERATION_PLAN.md` | ✅ done | 1 |
| — | Content bank + deterministic engine | `ATELIER_CONTENT_BANK_PLAN.md` | ⛔ superseded by #2 | — |
| 3 | Rollout & verify generation (pre-warm + audit) | `ATELIER_LEARNING_LOOP_PLAN.md` Part 1 | ✅ done | 2 |
| 4 | Design system E-0 (tokens + 5 components + styleguide) | `ATELIER_UIUX_OVERHAUL_PLAN.md` E-0 | ✅ done | — |
| 5 | Drill "do" surface E-2 | `ATELIER_UIUX_OVERHAUL_PLAN.md` E-2 | 🟡 in progress | 4 |
| 6 | Feedback moment E-3 | `ATELIER_UIUX_OVERHAUL_PLAN.md` E-3 | ⬜ next | 4, 2 |
| 7 | Rule→apply loop (rule-first, difficulty ramp) | `ATELIER_LEARNING_LOOP_PLAN.md` Part 2 | ✅ done | 5, 6 |
| 8 | Today cover E-1 + first-15-seconds | `ATELIER_UIUX_OVERHAUL_PLAN.md` E-1 (detail: `ATELIER_FIRST_15_SECONDS_PLAN.md`) | ✅ done | 4 |
| 9 | Session complete E-4 ("edition printed" + hook) | `ATELIER_UIUX_OVERHAUL_PLAN.md` E-4 | ✅ done | 5 |
| 10 | Notebook archive + Feuilleton lead E-5/E-6 | `ATELIER_UIUX_OVERHAUL_PLAN.md` E-5/E-6 | ⬜ | 4 |
| 11 | Motion polish (page-turn, ink-set, haptics) | `ATELIER_UIUX_OVERHAUL_PLAN.md` E-motion | ⬜ | 5–10 |
| 12 | Missions (messaging, AI scenarios, life + story) | `ATELIER_MODES_INTEGRATION_PLAN.md` Part 1 | ✅ done for A2/F1/F2/F3; serial missions route through `MissionService` | 2, 4 |
| 13 | Story mode (user library, guided reading on AI engine) | `ATELIER_MODES_INTEGRATION_PLAN.md` Part 2 | 🟡 backend + Notebook read→exercise→feedback runner done; richer dedicated reader polish remains | 2, 4 |
| 14 | Geometric forms (`AtelierForms`) | `ATELIER_FORMS_AND_REWARD_PLAN.md` | ✅ component built | 4 |
| 15 | Content quality gate (parallel, backend) | `ATELIER_CONTENT_QUALITY_GATE_PLAN.md` | ✅ done | 2 |
| 16 | Reward economy (tokens/seals/workshop/almanac) | `ATELIER_REWARD_ECONOMY_PLAN.md` | 🟡 backend + almanac + drill reward moment + printed summary done; story-seal crop remains | 2, 14 |
| 17 | Serial world adoption (A1–A5) | `ATELIER_SERIAL_WORLD_ADOPTION_PLAN.md` | 🟡 A5 done; A3 reader landed by agent | 4, 12 |

`ATELIER_FIRST_15_SECONDS_PLAN.md` is absorbed into #8 (kept as focused detail).

## Current focus → next actions

1. **#10 / #11 — Notebook archive + motion polish.** The main daily arc is now in place;
   next polish pass should focus on archive density, page-turn feel, and any remaining
   haptic coverage gaps.
2. **#13 — Story mode polish.** Backend ingestion and Notebook read→exercise→feedback are
   live; remaining work is a richer dedicated reader surface and deeper production-grade
   correction for book-episode answers.
3. **#16 / #17 — Serial reward art.** Story-seal crop metadata and almanac memory art
   remain the main unfinished serial/reward bridge.

## Notes on status

- #2 AI-first generation/correction is marked Done in `MASTER_CODEX.md` (per-session
  generation, AI critique/retry, LLM-primary correction, report-exercise signal,
  error-pattern context, background pre-generation).
- #4 E-0 is wired: `web-frontend/components/ui/{ExerciseShell,ProgressBar,FeedbackSheet}.tsx`,
  tokens in `web-frontend/styles/globals.css`, and a `/dev/styleguide` route.
- #5 is partial: `atelier.tsx` uses the `.atelier-do-mode` shell; the feedback sheet is
  not yet wired into the live drill flow (that's #6).
- #13 story mode: do **not** extend the interactive-fiction `StoryService`; reuse only
  the ingestion plumbing and rebuild on the AI engine with a user-owned library (see the
  audit table in the modes plan).
- Design source of truth for #16/#17 is vendored in `docs/design-reference/` (the Claude
  Design "Serial World" + "Press Run" exports). Reimplement on the real stack/tokens —
  never paste that JSX/CSS in.
- Built so far (type-clean): `web-frontend/pages/serial/index.tsx` (A5);
  `web-frontend/components/ui/AtelierForms.tsx`; and
  `web-frontend/components/ui/Seal.tsx` (`Seal`, `CoreForms`, `SealMini`, `LogoToken`,
  `ReactForm`, `Confetti`, `SEAL_NAMES`, `sealForEdition`) + their `globals.css` styles.
  The reward economy (#16) and the drill/almanac surfaces consume these — they should
  not be rebuilt.
- Almanac (#16 frontend) shipped: `web-frontend/pages/almanac.tsx` consuming
  `GET /atelier/almanac` + `POST /atelier/workshop/compose` (client methods +
  `AtelierAlmanac` types in `services/api.ts`), routed under Notebook (product-shell +
  a "Seal collection" link). The in-drill logo-token reward moment and printed session
  summary are also wired. Remaining: story-seal crop metadata/art.
- Missions (#12) was already largely built (interactive turns, in-character AI replies,
  per-turn corrections, serial-thread link, concept/errata/vocab selection). Added
  AI-first **personalized scenario generation** (`MissionGenerator._llm_scenario` in
  `app/services/missions.py`) so each life mission is a fresh, vivid situation at the
  learner's level instead of the canned "Camille at Gare de Lyon" template; canned
  templates remain the deterministic fallback. A2 "reply-not-grade" frontend is live
  and serial missions route through `MissionService`'s serial mission contract.
- Content quality (#15) shipped: word-bank `meaning_cue` is now required through the
  generation prompt, schema/validator, AI critique, audit helper, and Atelier rendering.
  Directed rewrites are also structurally rejected if they do not quote the source
  word/phrase and name the target form. The three seed concepts were regenerated; the
  LLM provider failed, so fallback sets were used, with 3 ok / 0 failed and 0 audit
  flags (`tests/fixtures/atelier_word_bank_audit_report.json`).
- Story/library mode (#13) now exposes uploaded books in Notebook as read mode followed
  by an interactive generated exercise runner using `ExerciseShell`, `ProgressBar`, and
  `FeedbackSheet`; completing the runner files the episode through the library endpoint.

## Decisions locked

- Generation is **AI-first**: generate fresh per session, AI critiques AI; the only
  non-AI guard is a thin renderability/solvability check.
- Visual identity: clean/minimal, with the **ink-block shadow as a sparing brand accent**
  (one hero element per screen).
- Missions are an **opt-in spine** (resolver-surfaced ~2–3×/week), not a daily fixture.
- The daily edition is a **playlist** assembled from spines: grammar path, Feuilleton,
  library, missions.
