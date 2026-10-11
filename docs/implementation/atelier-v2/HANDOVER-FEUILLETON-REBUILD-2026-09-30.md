# Handover — the Feuilleton rebuild (2026-09-30)

You own the **Feuilleton rebuild**: turning the owner-approved season-1 bible into
the product's living heart. This is the most important work in the repo. Read this
whole document, then the files in §5, before writing any code.

## 1. The product in one paragraph

**L'Atelier** is a French-learning app built around a daily graphic-novel serial.

- **Stack:** backend FastAPI in `app/` (Python 3.14, `venv/`, tests in `tests/`);
  frontend Next.js pages router + Capacitor in `web-frontend/`.
- **The day:** a learner's day is a *journey*: warm-ups, a comic page from the
  story engine (`app/services/living_story.py`), a conversation with a character,
  drills, an ending and a recap.
- **The problem:** the owner's verdict after testing is that the story is the
  heart, and today it fails. Episodes are benign errands, the art rarely arrives,
  the learner leaves the comic when they enter it, and the season's real material
  never reaches the page. The diagnosis is in
  `docs/implementation/atelier-v2/WORK-PACKAGES-2026-09-30-feuilleton.md` §1.

## 2. Rules of the shared checkout (non-negotiable)

- **Git:**
  - Never `git checkout`, `stash`, `reset`, `restore`, `rebase` or `clean` the
    working tree.
  - Never `git add -A` or a bare `git commit`.
  - Commit only your own paths: `git add <new>` then `git commit -m "…" -- <paths>`.
- **Other people are working in this tree:**
  - **Codex** runs E-5 (generated frontend types), the E-6 flag inventory, then E-2
    (test isolation, `tests/conftest.py`).
  - **A Claude session** handles the owner's test findings and E-1 (landing the
    branch).
  - Before you edit a file, check `git status`: if it has uncommitted changes you
    didn't make, coordinate through the owner instead.
- **Servers:** the owner tests live on ports **3000/8011** (database
  `atelier_e2e_0926`), and port 8000 belongs to another project. Never stop,
  restart or `pkill` Node, Next or uvicorn. Never touch the owner's database
  `language_learning`.
- **Cost and publishing:**
  - Paid API calls (OpenAI text, speech or images) only with the owner's explicit
    OK and a stated cap. Tests use fakes.
  - No pushes, PRs or deploys.

## 3. What you own

**Files:**
- `app/services/living_story.py`, `story_lanes.py`, `coulisses.py`, `season_writer.py`
- the season world bibles (`app/prompts/serial/world_bible*.json`)
- `app/services/story_archive.py`, `serial.py` (story parts)
- `app/api/v1/endpoints/story_engine.py`
- the reader (`web-frontend/components/feuilleton/**`, `StoryEpisodeReader.tsx`,
  `StoryEpisodeStep.tsx`, `story-episode-model.ts`)
- `pages/graphic-novel.tsx`
- the story's place in the day (`daily_journey.py` and `journey_planner.py`, story
  and scene parts only)

**You do not own the story itself.** `docs/story/season-1/` is the owner-approved
bible. Implement it faithfully; any change to a plot point, a character or an
ending goes to the owner first.

## 4. The packages, in order

The source of truth is `WORK-PACKAGES-2026-09-30-feuilleton.md` (§3 design, §4
packages, §6–7 owner direction, decisions F-1..F-5 and S-1..S-13). WP-108 is done
(`7bb07a3`, `8380912`: art never hangs, dispatch after the real commit).

### 1 · WP-111 · La bible de saison: from prose to a runnable season

- **A season format the engine reads:** tentpoles as authored two-day pages
  (Day A / Day B with the mid-point hook), with:
  - panels (actions, at least two characters in frame, silences);
  - the turn to the learner and what they must *want* to say;
  - likely replies, including the clumsy but sincere one, and how the scene answers;
  - the solve mechanic, the resolution and the «À suivre…»;
  - A2 lines, with B1 lines where they differ.
- **The flag table** (`00-season-bible.md`): set where, read where, and the effect
  of each flag.
- **The learner's own calendar** (decision S-12): the season runs on the learner's
  day count. Tentpoles land on the learner's weekend where possible, and date-bound
  scenes get neutral variants.
- **The days between tentpoles:** the director follows
  `09-entre-les-episodes.md`, meaning what may advance, what must not yet, the
  small moments, and **«episodes without meaningful change are refused»**. That
  rule is enforced by a critic with one retry, then logged. Generated days must
  never spoil the next tentpole.
- **The romance and friendship paths with Lila:**
  - they advance on what the learner chooses to express, **never on grammatical
    accuracy**;
  - affection is never a visible score;
  - Camille's gender arises in the story (S-9).
- **Seasons 2 and 3** re-cut later to follow from the new season 1 («L.» opens
  season 2). Not now.
- **Done when:** a fake-provider life of 59 days plays tentpoles 1–8 on their days,
  with generated days obeying the gap rules, and the owner reads the first 10 days
  and would read on.

### 2 · WP-109 · Une seule maison, and WP-110 · La planche vivante

- **Tabs:** «La Une · Feuilleton · Courrier · Cahier».
  - The day's episode lives in the Feuilleton.
  - Home headlines it.
  - Practice wraps before and after it, never in the middle.
- **The six-movement page:**
  1. characters acting together;
  2. the turn to *you*, with **your line drawn as a balloon in its panel** (S-2 /
     F-2: characters keep captions);
  3. reaction panels live, the WP-89 conversation drawn;
  4. the solve moment;
  5. the ending drawn;
  6. «À suivre…».
- **Art:** per panel, at least two characters acting, the approved style, the cast
  references. The art pipeline is WP-88/108 (allowance US$0.25/day, fallback to
  the plate after 4 minutes).
- **Done when:** a whole episode reads as one page on a phone with the learner's
  lines in it, and the walk screenshots show it.

### 3 · WP-112 · Résoudre, and WP-113 · Conséquences

- **Mechanics as plot moves:** L'enquête (contradiction; at A1, a picture tap),
  Convaincre, Le choix, Déchiffrer, and Qui a dit ça ? as evidence. Each is posed
  inside the page, graded with the existing graders, and changes the story.
- **Consequences:**
  - stages advance on learner actions, not on day counts;
  - flags are enforced by the director;
  - tentpole variants per flag;
  - three endings;
  - complication cards create real obstacles.
- **Done when:** two harness learners making opposite choices at tentpole 1 read
  visibly different episodes and reach different endings.

### 4 · WP-114 · La qualité du récit (runs alongside from WP-111)

- **A story critic** with a rubric: hook, stakes, a value turn, meaningful change,
  advances a thread, in character.
- **Metrics:** the share of episodes without meaningful change (target under 10 %),
  «À suivre» tap-through, next-day return.
- **Director model A/B** (`docs/implementation/atelier-v2/IDEAS-2026-09-29-big-leaps.md`
  #1) only with the owner's consent and cap.

### Later, not yours to start

- WP-104..106: themes, L'Imagier, La trace. The day's theme should come from the
  episode, so these plug into your spine afterwards.
- A La Forge redesign.

## 5. Read first

1. `docs/story/season-1/00-season-bible.md`, then `01`, `04`, `05`, `08` and `09`.
2. `docs/implementation/atelier-v2/WORK-PACKAGES-2026-09-30-feuilleton.md` (all of it).
3. `docs/implementation/atelier-v2/WORK-PACKAGES-2026-09-29-test-1.md` (top): the
   process rule. **A package is done only when it has been used.**
4. `docs/implementation/atelier-v2/WORK-PACKAGES-2026-09-28.md` §4 (the design
   system), §8 (decisions O-1..O-7).
5. The current engine: `app/services/living_story.py` (director, actor, validators,
   the ledger: chronicle, consequences, plants, secrets, moods/trust, tutoiement,
   chapters, seasons, teasers, absence), `app/services/story_lanes.py`, and
   `app/services/panel_art.py`.
6. `README.md` «Walk harness» and `.claude/launch.json`.

## 6. How you prove each step

- **Tests:**
  - backend: `venv/bin/pytest -q -p no:cacheprovider tests` (about 13 min; one run
    order-dependent flake family is known, see E-2);
  - frontend: `cd web-frontend && npx tsc --noEmit && npm run lint && npm test`.
- **The walk harness:** `cd web-frontend && npm run walk` (own database and ports,
  fake provider, test clock, about 5 min). Extend it to play the season's
  tentpoles and check the screenshots. Every screen must answer: *does the
  learner know what to do, whether they were right, and how to go on?*
- **The owner's eyes:** after each package, the owner plays it on the test copy.
  Ask the main Claude session to reset a test learner to the right story day, or
  add a harness command that does it.
- **Model use:** Opus for design, the season format and the critic; Sonnet for bulk
  implementation. The owner watches the weekly usage limit.

## 7. Report after each package

Report:
- files changed (path:line) and commits;
- test counts before and after;
- the walk screenshots you checked (paths);
- what the owner should play and where;
- anything deferred;
- every decision you need from the owner, especially any place where the bible
  couldn't be implemented as written.
