# Handover for Codex — 2026-09-30

You are joining **L'Atelier**, a French-learning app built around a daily
graphic-novel serial («Le Feuilleton»). Backend: FastAPI in `app/` (Python 3.14
venv in `venv/`, tests in `tests/`). Frontend: Next.js pages router + Capacitor
in `web-frontend/`. You share this working tree with Claude Code sessions and
their agents, which are editing files right now. Read this whole document before
touching anything.

## 1. Rules of the shared checkout (non-negotiable)

- **Never** run `git checkout`, `git stash`, `git reset`, `git restore`,
  `git rebase` or `git clean` on the working tree, and never `git add -A` or a
  bare `git commit`. Commit only the paths you changed:
  `git add <new files>` then `git commit -m "…" -- <path> <path>`.
- **Files you must not edit** until told otherwise (another agent owns them this
  round):
  - `app/services/panel_art.py`, `app/celery_app.py`, `app/tasks/journey_prefetch.py`
  - `app/api/v1/endpoints/story_engine.py`
  - `web-frontend/pages/graphic-novel.tsx`
  - `.claude/**`, `tests/conftest.py`
  - `docs/story/**` (the season's scenes are being written there)
  - `app/services/living_story.py` and `app/services/story_lanes.py`: the story
    engine is about to be redesigned (§4). Leave it alone.
- **Servers:** the owner tests live on ports **3000** (frontend) and **8011**
  (backend, database `atelier_e2e_0926`). Port 8000 belongs to another project.
  Never stop, restart or `pkill` Node, Next or uvicorn processes. Never touch the
  owner's database `language_learning`. For your own runs, use the walk
  harness (§3) or other ports with a throwaway database.
- **No paid API calls** (OpenAI text, speech or images) without the owner's
  explicit OK. Tests use fakes.
- **No pushes, PRs or deploys.** Commit locally; the owner decides the rest.

## 2. How work is judged here

- **A package is done only when it has been used, not when tests pass.** Run the
  E-3 walk harness (`cd web-frontend && npm run walk`, about 5 minutes, own
  database and ports; see the README) and look at the screenshots of the screens
  you changed. Every screen must answer three questions: *does the learner know
  what to do, whether they were right, and how to go on?*
- **Suites:**
  - backend: `venv/bin/pytest -q -p no:cacheprovider tests` (about 13 min; the
    last full run passed 4,177);
  - frontend: `cd web-frontend && npx tsc --noEmit && npm run lint && npm test`
    (637 passing).
- **Design contract:**
  - av2 system only (EB Garamond + Instrument Sans, existing tokens; no new
    fonts or colours);
  - the Bauhaus mark is the only gauge (no rings or percentage bars);
  - one primary button per screen;
  - language rule `web-frontend/lib/language-rule.ts`: up to A2, chrome in the
    learner's language; from B1, French.

  See `docs/implementation/atelier-v2/WORK-PACKAGES-2026-09-28.md` §4.
- **Commit messages:** follow `git log -10`.

## 3. Your packages, in order

### 1 · WP-107 «Retour d'essai 2»: the owner's second test (start here)

From the owner's B1 test on 2026-09-29 (learner `qa-b1-0929@example.com`) and the
first E-3 walk:

| # | What the owner saw | Cause | Fix | Done when |
|---|---|---|---|---|
| U1 | Sending an answer failed and the day could not continue: «Le serveur n'a pas reçu cela» | Access tokens live 60 min (`ACCESS_TOKEN_EXPIRE_MINUTES`). The web client kept using an expired token, every send got **401**, and the UI reported it as a transport error | On a 401 from the API client: refresh the NextAuth session once (`getSession()` runs the jwt refresh in `web-frontend/lib/auth.ts`) and retry the same request with the same mutation id. If the refresh fails, show «Votre session a expiré — reconnectez-vous» with a sign-in action (chrome language), never the transport error. Covers the journey requests (`components/atelier-v2/journey/journey-requests.ts`), La Forge and the Courrier | A node test simulates an expired token and sees one refresh plus one successful retry; the walk harness can run a day longer than the token lifetime (give the harness a way to issue a short-lived token) |
| U2 | B1 drill «Which sentence follows today's rule?» is trivial: only one option even contains «si» | Recognition items take distractors from unrelated scene lines | Distractors must be **near-misses of the same form** (for si + présent → futur: «Si je finirai…», «Si je finirais…», «Si je finis tôt, je t'appelais»). From B1, prefer production items (transform, short answer) over recognition; recognition at B1 only as a warm-up. Files: `app/services/grammar_items.py`, `item_bank.py`, `journey_planner.py` (recall format choice per band) | A test pins that no B1 recognition item has a distractor without the rule's form, and the B1 recall mix in the rhythm harness is at least 60 % production |
| U3 | «Too much text everywhere, noisy and crowded» on the reply screen | The objective appears twice (header label and body), in English with grammar notation; «Romane « Romy » Tremblay» appears twice in full; rule chips in jargon; the cue line + exchange count; three help chips + «Arrêter ici» | The reply screen is: the character's face and line, **one** short task line in the chrome language without notation («Proposez une heure — avec *si*»), the field, Send. The header shows the place only. Use the character's short name (Romy). Rule and word chips and Traduction/Proposer move behind one «Indice» control. Keep the exchange tokens; drop the text count. Files: `JourneySteps.tsx` (RespondStepView), `RespondThread.tsx`, `JourneySession.tsx` (header), `journey-copy.ts` | Walk screenshots of the reply screen at A1 and B1 show at most one sentence of instruction and at most one visible help control |
| U4 | A B1.1 learner is dealt an **A2** scene, and the screens fall back to English («This scene is written at A2, below your current level», «Step 6 of 11») | Scenario selection falls back to a lower band when no scene exists at B1, and the chrome language follows the *scene's* band | Chrome language follows the **learner's** level, always. Authored fallbacks and first days need a B1 variant (write them in the existing authored format, at B1), or the engine scene is used. The note «below your current level» is removed from learner-facing copy | Walk: the B1 learner sees French chrome on every screen and no «below your level» note |
| U5 | In the reader, «Next» moves on the last panel: it becomes a slightly bigger «Continue» (y 752/h 48 → y 744/h 56) | The final button is styled differently | Same position and size for Next/Continue on every panel (`components/feuilleton/reader/**` except `graphic-novel.tsx`: the style lives in `reader-styles.tsx` / `FeuilletonReader.tsx`) | The walk's «Next never moves» check passes in en/de/fr |

Only U4's authored B1 variants need content writing; keep them short and
natural.

### 2 · E-5 · Generate the frontend types from the backend

Brief: `.claude/agents/e-5-generated-types.md` (also
`docs/implementation/atelier-v2/WORK-PACKAGES-2026-09-29-engineering.md` §3 E-5).
OpenAPI from `app.main.create_app().openapi()` goes to `openapi-typescript`, into
`web-frontend/types/generated/`; `types/daily-journey.ts` re-exports it; a CI
freshness check. Coordinate with WP-107: do it after WP-107 so you migrate the
final shapes.

### 3 · E-6 · Flag and legacy inventory (inventory only, then stop)

Brief: `.claude/agents/e-6-flag-cleanup.md`. Produce
`docs/implementation/atelier-v2/E6-FLAG-INVENTORY.md` (every setting in
`app/config.py` plus module constants and `web-frontend/launch-flags.json`, each
classified as product switch / permanent / dead / owner call, with callers
checked). **Delete nothing:** the owner reviews the list first. Include the
decided removals already known: `closeness` (O-2), `SeasonPage.tsx` (O-5), the
legacy Séance paths.

### Later, only when the owner or Claude says so

- **E-2** (test isolation, Postgres in CI, parallel runs) needs `tests/conftest.py`,
  which WP-108 is editing now.
- **E-1** (landing the branch) is owner-approved step by step.

## 4. What NOT to take on (Claude is doing it)

- **The Feuilleton redesign WP-108..114**
  (`docs/implementation/atelier-v2/WORK-PACKAGES-2026-09-30-feuilleton.md`):
  - WP-108, the art pipeline, is in progress;
  - the season-1 story (three arcs, eight tentpoles) is being written in `docs/story/season-1/`;
  - the story engine will be rebuilt around it. Do not change `living_story.py`,
    the director prompts or the season world bibles.
- **The theme packages WP-104..106** (`WORK-PACKAGES-2026-09-29-test-1.md`) wait for
  the story.

## 5. Context to read first

- `docs/implementation/atelier-v2/WORK-PACKAGES-2026-09-29-test-1.md`: the first
  owner test (WP-103, done) and the process rule.
- `docs/implementation/atelier-v2/WORK-PACKAGES-2026-09-28.md` §4 (design rules),
  §6 and §8 (owner decisions).
- `README.md` («Walk harness» section) and `.claude/launch.json` (how the e2e
  servers run).

## 6. Report back

After each package: files changed (path:line), commits, exact test counts before
and after, the walk screenshots you checked (paths under `web-frontend/e2e/out/`),
anything deferred, and every decision you need from the owner.
