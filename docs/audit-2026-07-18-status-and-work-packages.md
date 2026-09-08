# App status audit — 2026-07-18 · open work packages

Audited on branch `codex/serial-season-engine-production` (working tree ~5.7k inserted
lines beyond last commit). Each WP below is self-contained for an implementation agent.

## Verified green (baseline health)

- **Backend test suite:** 384 tests pass (`pytest tests/` minus the 4 legacy files in
  WP-10). Covers atelier learning loop incl. the new épreuve learning moments
  (`tests/test_atelier_epreuve_learning_moments.py`), missions, serial, graphic-novel,
  and all `test_frontend_*` static-markup suites.
- **Frontend:** `npx tsc --noEmit`, `next lint`, `npm run build` all green (all routes
  compile, including `/serial/*`, `/graphic-novel`, `/atelier`, `/missions`).
- **Live API smoke:** backend boots; `/api/v1/atelier/today`, `/missions/today`,
  `/serial/today`, `/graphic-novel/today` return real data. The unauthenticated demo
  fallback is correctly gated: `app/main.py:67` raises at startup if
  `AUTO_CREATE_USERS_ON_LOGIN=true` in production.
- **Journal overhaul progress is further along than the docs say.** The "deeper second
  stage" that `docs/overhaul-session.md` §5b lists as NOT yet wired is now fully wired in
  `web-frontend/pages/atelier.tsx`: movable-type exercise body (`EpOpts`/`EpSlug`/
  `EpSetLine`/`EpCases` ~:4007–4053), proofreader's-marks feedback (`EpGalley`/`EpFix`/
  `EpIns` ~:3664, `EpRelecture` ~:3632), the épreuve recap (`EpRecapHead`/`EpTally`/
  `EpProof`/`EpSeal`/`EpMint`/`EpPhrase`/`EpStreak`/`EpBatStage` ~:4675–4694), plus the
  engine moments previously deferred: **adaptive early lock** (backend
  `app/api/v1/endpoints/atelier.py:309` `_maybe_apply_adaptive_lock`, UI `EpLock` :3503),
  **typed micro-repair + same-session re-test** (`app/services/atelier.py:3164`
  `record_micro_repair`, retest validation `endpoints/atelier.py:1041–1051`),
  **confidence tap** (`EpConfidence` :3577, persisted `services/atelier.py:3108`),
  **provenance margin note** (`EpProvenance` :3399 from `due_errata`), **model audio /
  shadowing** (`EpListen` :4347, `EpRecord` :4472).
- Missions "Le Courrier" and Feuilleton "Le Feuilleton" reskins are shipped and the
  reader's panel machinery now uses `FePanel` (graphic-novel.tsx:1362, :2032) — beyond
  what the docs record.

---

## A. Broken or half-wired learning loops (highest value)

### WP-1 — "La phrase du jour" is promised but never printed on La Une
**Problem.** The session recap stamps the learner's best sentence "À paraître demain"
(`web-frontend/components/epreuve/Epreuve.tsx:464`, rendered `pages/atelier.tsx:4684`;
built server-side at `app/services/atelier.py:5475` as `recap.phrase_of_day`). But the
phrase exists **only inside the recap payload**: nothing persists it for the next day,
`/atelier/today` doesn't serve it, and `components/laune/LaUne.tsx` has no slot (zero
`phrase` references). The fiction makes a promise the home page never keeps.
**Task.** (a) Persist `phrase_of_day` (text, byline, session date) when the recap is
built; (b) expose yesterday's phrase in the `/atelier/today` home payload; (c) add the
La Une boxed-quote slot (serif quote + byline + "paru" flag), tokens-only, light+dark,
with an empty variant (no phrase yesterday → slot absent). French copy inside fiction.
**Acceptance.** Complete a session that produced a sentence → next day's La Une payload
carries it and LaUne renders it; static frontend test + backend test for persistence and
day rollover; tsc/lint/build green.

### WP-2 — Confidence calibration is captured but never feeds the SRS
**Problem.** The confidence tap persists `confidence` + `calibration`
(`app/services/atelier.py:3108–3113`) and the recap summarizes confident vs hesitant
misses (:5402–5417), but nothing in the scheduling layer consumes it — zero references
in `app/services/unified_srs.py` or `app/core/srs/`. The signal dead-ends
(overhaul-session §2 #3 intended it as an SRS calibration input).
**Task.** Weight scheduling by calibration: a *confident miss* (thought sure, was wrong)
should shorten the interval / raise priority more than a hesitant miss; a *confident hit*
can accelerate mastery slightly. Wire into `UserGrammarProgress.score` updates /
`unified_srs` interval selection where atelier attempts are graded.
**Acceptance.** Unit tests showing divergent scheduling for confident-miss vs
hesitant-miss vs no-signal on otherwise identical attempts; existing 384 tests stay green.

### WP-3 — Quality flywheel: bad exercises are reported but never retired
**Problem.** `AtelierGenerationEvent` rows are logged (`app/services/atelier.py:1843`)
and the UI has report-exercise, but nothing aggregates error/report rates to auto-retire
and regenerate bad items (overhaul-session §2 #6). Bad generated content lives forever.
**Task.** Backend-only job: aggregate per-exercise report counts + wrong-rates from
attempts/generation events; above threshold, mark the item retired (excluded from future
session assembly) and enqueue regeneration through the existing generation path (respect
the three no-spoil gates — generation prompt, structural validator, AI critic — that keep
transform items from leaking answers). Add an audit log of retirements.
**Acceptance.** Test: an item crossing the report/error threshold no longer appears in
newly assembled sessions and a replacement is generated; no UI change required.

### WP-4 — Final conversation round doesn't use the serial cast
**Problem.** The output-ladder `conversation` round uses static generic prompts
("Message received: « Qu'est-ce qui se passe ? » …", `app/services/atelier.py:1282–1298`)
— overhaul-session §2 #7 calls for the flagship connective move: the final round is two
real turns **with a serial character**, reusing the Missions turn engine (in-character
replies + quiet corrections). No cast/serial reference exists anywhere in
`app/services/atelier.py`.
**Task.** When the user has an active serial thread, source the conversation round from a
cast member (nearest relationship / character in the current beat): character opener
themed to the concept, learner replies, one in-character world reply via the missions
turn engine, corrections filed quietly to errata as usual. Fall back to today's generic
prompts with no thread. Frontend: character byline/name on the conversation exercise
(reuse Courrier/feuilleton character presentation, register tu/vous respected).
**Acceptance.** Backend test with a stub LLM: conversation round carries
`character` metadata and a real second turn; no-thread fallback test; frontend static
test for the byline; suite green.

## B. Concrete frontend bugs / polish

### WP-5 — Feuilleton reader still shows the legacy English continuation card
**Problem.** `FeuilletonContinuationCard` (`web-frontend/pages/graphic-novel.tsx:2961–
3010`, rendered :749) still uses English copy inside the fiction ("Next episode",
"Use in mission", "Finish edition", "Review words") — violating the journal language rule
— and its primary-action logic is confusing: label is `next_beat_kind === 'mission' ?
'Next episode' : 'Use in mission'` while the href **always** targets `/missions`
(:2995), even when the next beat is a read. It sits alongside the already-reskinned
`FeCliff`/`FeFiled`, so the completion area speaks two visual languages.
**Task.** Replace it with the `FeContinuation`/`FeFiled` primitives from
`components/feuilleton/Feuilleton.tsx`, French fiction copy, and route by beat kind:
mission beat → `/missions` (with the existing seed params in `missionPairs`), read beat →
next episode/reader. Keep the vocabulary/concept seed handoff intact.
**Acceptance.** Static tests updated (`test_frontend_continuation_card.py`); routing
verified for both beat kinds; tsc/lint/build green.

### WP-6 — Missions: quick replies + "the world is typing" (deferred minors)
**Problem.** Quick replies append into the textarea (`pages/missions.tsx:898`) instead
of acting as one-tap starter slips, and there is no typing indicator while the character
reply generates (only a button spinner) — overhaul-missions §2 #7.
**Task.** (a) Quick-reply chips become one-tap starters: tap → fills composer → focus
(or directly sends, owner's call — default: fill+focus). (b) While `POST /{id}/turns` is
in flight, show a small in-fiction indicator on the thread ("… rédige sa réponse" with
the character name), press style, reduced-motion safe.
**Acceptance.** Static mission tests updated; tsc/lint/build green.

### WP-7 — Prune dead styling: `.s-*` leftovers and the `.ph` parcours palette
**Problem.** After the FePanel adoption, `FeuilletonStyles` in `graphic-novel.tsx` keeps
dead `.s-*` masthead/cliffhanger rules (the file still has ~42 `.s-` references — some
live for tasks, some dead); `pages/atelier.tsx` still carries the hardcoded `.ph`
parcours palette flagged as dead in overhaul-session §3.
**Task.** Identify and delete only the genuinely unreferenced rules/markup (grep class
usage before removing each); no visual change intended.
**Acceptance.** tsc/lint/build green; static tests green; spot-check reader + session
render (both themes) unchanged.

## C. Journal-overhaul surfaces not started

### WP-8 — Notebook cluster reskin (`/notebook`, `/grammar`, `/vocabulary`) — surface #3
**Problem.** The "reference layer" is the last big off-system cluster:
`pages/grammar.tsx` has **51 hardcoded hex colours and zero `--app-*` tokens**
(dark-blind), `vocabulary.tsx` 26 hex / zero tokens, `notebook.tsx` 12 hex. Status table
in `docs/JOURNAL_SYSTEM_OVERHAUL.md` marks surface #3 "not started".
**Task.** Follow the per-surface method in `docs/JOURNAL_SYSTEM_OVERHAUL.md` §2 exactly:
(1) code-grounded audit → `docs/overhaul-notebook.md` (works today / missing / drift with
file:line evidence); (2) Claude Design brief at the bottom of that file (the owner runs
it through Claude Design — do **not** invent visuals yourself); (3) after the package
arrives, port to `components/notebook/` on `--app-*` tokens, light+dark, phone-first.
The audit + brief can start now; implementation waits on the design package.
**Acceptance (audit step).** `docs/overhaul-notebook.md` exists in the house format with
a self-contained brief; status table updated.

### WP-9 — Settings reskin (`/settings`) — surface #5, do last
`pages/settings.tsx` already uses tokens (no hardcoded hex) but has no journal
("administration layer") treatment. Smallest surface; keep for after WP-8.

## D. Health / infrastructure

### WP-10 — 4 legacy test files break collection on Python 3.14
**Problem.** `pytest tests/` aborts at collection: `test_error_detection_rules.py`,
`test_error_detector.py`, `test_sessions_ws.py`, `test_spontaneous_words.py` fail with
`pydantic.v1.errors.ConfigError` (spacy/confection pulling pydantic v1, incompatible
with Python ≥3.14). The suite is only green with manual `--ignore`s.
**Task.** Either pin/upgrade the offending dependency chain or add module-level
`pytest.importorskip`/skip markers with a tracking note, so a bare `pytest tests/` is
green again.
**Acceptance.** `python -m pytest tests/ -q` runs to completion with no collection
errors; skipped files clearly reported.

### WP-11 — Root Jest suite cannot run (legacy RN/expo app)
**Problem.** Root `package.json` (`"test": "jest"`, expo/react-native deps) fails —
jest isn't resolvable and the config's deps are missing. This is the legacy RN app
(`src/`); the shipping mobile path is web-frontend + Capacitor (`cap:sync:ios`).
**Task.** Decide with the owner: retire the legacy RN tree (remove root jest script +
`src/`, or move under `legacy/`) **or** repair its toolchain. Default recommendation:
retire; it's untested dead weight that confuses agents and CI.
**Acceptance.** Either `npm test` at root is green, or the legacy tree/scripts are
removed and docs note the Capacitor path as canonical.

### WP-12 — Docs lag the code (update before more agents read them)
**Problem.** `docs/overhaul-session.md` §2/§5b still say the movable-type body,
proofreader's marks, épreuve recap, adaptive gate, micro-repair, confidence, and
provenance are deferred/unwired — all are now implemented (see "Verified green" above).
The `docs/JOURNAL_SYSTEM_OVERHAUL.md` status table row #4 is likewise stale; the
Feuilleton doc doesn't record the FePanel adoption.
**Task.** Update the three docs (+ `MASTER_CODEX.md` if it tracks this) to the actual
state, marking exactly what remains (the WPs in this file). This prevents future agents
re-implementing shipped work.
**Acceptance.** Docs match code with file:line references; remaining-work lists point at
this audit file.

### WP-13 — Commit the working tree; ignore the build artifact
**Problem.** ~5.7k lines of shipped work (épreuve stage-2 wiring, learning moments,
FePanel adoption, new tests) sit uncommitted on `codex/serial-season-engine-production`.
`web-frontend/tsconfig.tsbuildinfo` is tracked and churns on every build.
**Task.** Add `tsconfig.tsbuildinfo` to `.gitignore` (and `git rm --cached` it), then
commit the working tree in reviewable chunks (backend engine / atelier UI / feuilleton +
missions / tests + docs). Owner review before push.

### WP-14 — Fix the dev-preview auth flow so live verification is possible
**Problem.** Multiple passes (feuilleton, cast) note "live check blocked by the
preview's auth gate": the API login works but the web NextAuth flow doesn't complete in
the dev preview, so no agent can visually verify authed routes (`/serial`,
`/graphic-novel`, `/atelier`) in both themes — verification has degraded to
tsc/build/static tests only.
**Task.** Diagnose the NextAuth (credentials) flow against the local backend in the dev
preview (callback URL/port, cookie settings, CSRF, `NEXTAUTH_URL`), or add a
dev-only bypass consistent with `AUTO_CREATE_USERS_ON_LOGIN` (must stay prod-gated like
`app/main.py:67`). Document the login recipe for agents.
**Acceptance.** From a fresh dev server, an agent can sign in and load `/atelier`,
`/serial`, `/graphic-novel`, `/missions` in light and dark; recipe recorded in docs.

---

## Suggested order / parallelization

| Wave | Packages | Notes |
|---|---|---|
| 0 | WP-13, WP-12 | Land + record what exists before anything else touches these files |
| 1 | WP-1, WP-2, WP-3 (parallel) | Backend-leaning, independent of each other |
| 1 | WP-5, WP-6, WP-7 (parallel) | Frontend-only, independent |
| 2 | WP-4 | Touches missions turn engine + atelier; do after wave 1 lands |
| 2 | WP-8 audit+brief | Can start anytime; implementation waits on design package |
| any | WP-10, WP-11, WP-14 | Infra, independent |
| last | WP-9 | Smallest surface |
