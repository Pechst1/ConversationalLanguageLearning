---
name: explore-walk
description: Play Atelier as a brand-new learner in a real browser, write free-text answers, judge every screen against the learner rubric and file ranked findings. Use for the nightly improvement loop or whenever asked to "walk the app", "test it like a user" or "find where it still breaks".
---

# Explore walk

The scripted walk (`npm run walk`, CI nightly) proves the app still *works*: no 500s,
a way forward on every screen, one verdict. It cannot tell whether the app *makes
sense*. This walk does that: an agent plays the app as a stranger, one action at a
time, answers in its own words and writes down every moment it would be lost, bored
or misunderstood.

## 1 · Start the stack

From `web-frontend/` (Postgres must be running; in a cloud container:
`service postgresql start` and set the `postgres` password):

```
WALK_PG_ADMIN_URL=postgresql://postgres:postgres@localhost:5432/postgres \
WALK_CHROMIUM=/opt/pw-browsers/chromium-1194/chrome-linux/chrome \
SECRET_KEY=walk-secret NEXT_TELEMETRY_DISABLED=1 \
  nohup node e2e/explore.mjs --fresh --native de --out e2e/out/explore-<date>-<persona> &
```

`WALK_CHROMIUM` only when Playwright's own browser is missing. Wait for
`[explore] ready`. Then drive it with `curl -s localhost:7777/<command> -d '<json>'`
(commands are listed at the top of `e2e/explore.mjs`). Look at the screenshot `/snap`
returns whenever layout, pictures or emphasis matter; the text alone hides half the
problems.

The stack uses the **fake story provider**: replies are classified by keyword
matching, not by the model. Judge story *reactivity* only in a live run (§5); in a
fake run, record what the authored beats do with an off-script answer and mark the
finding `fake-provider`.

## 2 · Personas (one run each)

| id | who | how they play |
|---|---|---|
| `a1-de-fresh` | German speaker, never learned French, signs up through the UI (`--fresh`) | answers short, makes real beginner mistakes, asks «c'est qui ?» when lost |
| `a2-en` | English speaker with school French | answers off-script on purpose: tells their own story, contradicts the scene, asks questions back |
| `b1-fr-chrome` | B1 learner with French chrome (`--native fr --level B1.1`) | checks that nothing falls back to English or German |

Play day 1 completely (teaser → sign-up → day → recap → Home), then
`/clock {"days":1}` and day 2, then day 7 if time allows. Open Feuilleton, Courrier
and Cahier once each.

## 3 · The rubric

The questions are in `docs/ops/walk-rubric.md` (22, chosen by the owner; the app walk
on the Mac scores the same ones). Ask the *pro Bildschirm* questions (1–11, 16–19) on
every screen; ask the *pro Tag* questions (12–15, 20–22) at the end of each day.
In this cloud walk question 19 is `n/a`, and question 4 is «fake» on the fake provider.

Write a finding the moment you notice it, with `/note` (it ties the finding to the
last screenshot):

```
curl -s localhost:7777/note -d '{"severity":"high","area":"onboarding","title":"…","detail":"what I did, what I saw, what I expected"}'
```

Severity: `blocker` (cannot go on) · `high` (a new learner is lost or misread) ·
`medium` (friction, wrong tone) · `low` (polish). `area`: onboarding, story-engine,
drills, copy, layout, flow.

## 4 · Report and file

1. Rank: severity first, then how early it hits (day 1 before day 7), then how small
   the fix is.
2. Write `docs/ops/walks/<date>.md`: personas, the score table (each rubric question
   1–5 per played day, the worst screen for per-screen questions, beside the last
   walk's scores; every 1 or 2 has a finding), one section per finding (what, where,
   screenshot, expected, suspected cause with `file:line` when found), and the
   scripted walk's result.
3. For each finding, search open issues labelled `walk-finding` for the same title
   or screen. Comment on a match ("seen again <date>"); otherwise open an issue with
   labels `walk-finding` + `area:<area>` + `sev:<severity>`.
4. Triage every finding you filed or commented on: one state (`queue:ready`,
   `queue:owner`), one lane (`lane:code`, `lane:story`), one size (`size:S`, `size:M`)
   and a comment starting **Done when:** with the check a fix must pass
   (`docs/ops/improvement-loop.md`, "The queue"). The night shift fixes what you mark
   ready; this walk does not fix anything itself.
5. Re-test every open `walk-finding` issue whose fix has merged: walk to that screen;
   close the issue with the screenshot if it is fixed, comment and set it back to
   `queue:ready` if not.
6. `curl -s localhost:7777/stop` tears down the stack and the throwaway database.

## 5 · Live runs (real model)

Story reactivity, reply classification and corrections need the real provider. A
live run is the same walk against a stack with `OPENAI_API_KEY` set (or against
production with a test account, once the environment may send requests to
onrender.com). It costs model calls, so it runs only when the owner has turned it on
for the loop (`docs/ops/improvement-loop.md`); a fake run never pretends to judge it.
