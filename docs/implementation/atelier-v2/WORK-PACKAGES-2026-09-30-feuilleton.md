# Work packages — 2026-09-30: Le Feuilleton, the heart of the product

Owner, after testing: *«The Feuilleton is not working, and it is not clear where
it lives and should belong. It should be a graphic novel you read through and
interact with: the screens show the characters playing out the story together,
they talk to each other, then the user has to do something, has to solve
something. It is not integrated, and there is no cohesive, engaging story. It is
benign and boring, not part of a bigger plot, deterministic and trivial.»*

This document diagnoses why, sets out what makes serial stories for language
learners work, proposes the redesign, and defines WP-108..114.

## 1. Diagnosis (checked 2026-09-29, B1 test learner)

### It is broken
- **The drawings never arrive.** Since WP-90, art for prefetched scenes goes
  to a background job queue. The local setup has a queue (Redis) but no worker, so
  **1,499 jobs are waiting in it**. The day's four panels have sat in the
  `rendering` state for hours, and the reader shows them «sous presse» forever,
  because nothing times the state out. In production a worker exists, but the
  failure mode is the same whenever it is down: a page that never finishes printing.

### It has three homes and none of them is the heart
- The day's episode lives inside **L'Atelier** (Home → the day → a scene step).
- The **Feuilleton** tab is an archive of past pages and the cast.
- The old composer is still reachable behind `?view=episode`.
- The learner therefore meets «the story» as one step of a lesson, and
  «the Feuilleton» as a library. Neither feels like the thing they came for.

### It is not a graphic novel
- A page is 4–6 panels showing the same location plate (drawings rarely
  arrive). Characters sit and talk; they rarely *do* anything.
- The learner's part leaves the comic: the reply is a chat screen, and the ending
  a third screen. The comic stops at the moment the learner enters it.

### The story is benign by construction
Today's B1 episode, «Un rendez-vous à décider», in full:

- *Panel 1.* «Le bruit, le café… c'est une soirée comme une autre.» Marin and Gus bicker about a playlist.
- *Panel 2.* Lila hides a letter: «Ce n'est rien, je gère.»
- *Panel 3.* Romy asks you to help her on Tuesday to record fifteen minutes.
- *Panel 4.* Gus: «Si tu dis oui, on t'appelle la star du plateau.»

The episode's task is to agree to a time. The mystery (Lila's letter) is decoration.
It is exactly what the owner describes, and it follows from the design:

1. **The director's contract is pedagogical first.** The contract is «write a scene that poses
   one learner objective at the band». The simplest scene that satisfies it is an
   errand: order, arrange a time, help someone. So every day is an errand.
2. **No dramatic question.** An episode has no goal–obstacle–turn–hook shape,
   no stakes, no reveal and no antagonist. Nothing *changes* by its end, so nothing
   pulls the reader to tomorrow.
3. **The plot lives in the world bible, not on the page.** The season arcs
   (Margaux's walls, Lila's Berlin letter, Gus's aristocratic family, Marin's
   proposal, the tentpole documents in `docs/serial-episode-tentpole-*.md`)
   advance by *stage claims* the learner never sees dramatised. The material is
   there; the delivery hides it.
4. **The learner is a helpful bystander.** They have no goal of their own in
   Paris, no secret and no side to take. They help others with small things.
5. **Deterministic.** Arc stages advance on a schedule and chapter shapes are dealt
   from a seed. The learner's choices move mood and trust numbers and margin
   notes, not *events*.

## 2. What makes a serial story for learners work

- **One central question carries the whole course.** *Destinos* (a 52-episode
  Spanish telenovela course) runs on a single mystery, a dying man's search for a
  lost son. Every episode ends on a question.
- **Characters you want to see again.** *French in Action* ran on a romance and
  running gags; people watched for the characters.
- **Short, with a twist.** Duolingo Stories are 2–3 minutes and funny, with a turn
  at the end, and comprehension is woven in as «what happens next?».
- **Understanding is the gameplay.** In *Ace Attorney* the player wins by spotting
  the contradiction in what people said. Reading and listening *are* the
  investigation.
- **Few choices that visibly matter.** Telltale-style narratives offer a handful of
  big choices («Lila will remember that») with foldback branching: branches rejoin,
  but the state persists and pays off later.
- **Scene craft.** Every scene turns a value: something is different at the end.
  Stakes are personal and escalate. Dramatic irony (the reader knows what a character
  doesn't) and a mystery box keep people reading. Every episode ends on a hook.
- **The pedagogy agrees.** A plot creates the *need* to understand (listening as
  investigation) and to speak (persuade, confront, confess). That need is the
  strongest predictor of word retention we have (involvement load; see WP-104).

## 3. The redesign

### 3.1 One home: the Feuilleton *is* the day's story

- **La Une** (Home) is the front page. It shows today's episode as the headline
  («Épisode 12 — La lettre de Berlin»), the teaser, and the day's practice around it.
- **The Feuilleton** is where the episode is lived: today's page first, then «Les
  numéros précédents» (the archive, WP-96) and «Le trombinoscope».
- **The day's practice** (warm-ups, drills, La Forge, La trace) wraps around the
  episode as «L'atelier du jour», before and after it, never in the middle of the story.
- **The old composer is removed.**

### 3.2 A real graphic-novel page with the learner inside it

The episode becomes one continuous page, in six movements:

1. **Establishing panels.** The characters *act* and talk to each other, with at
   least two in frame on most panels (a door slammed, a letter snatched, a phone
   ringing).
2. **The turn.** A character turns to *you*: your panel appears, a blank balloon
   where you speak or type. Your line is printed *in the comic*, as your balloon.
3. **Reaction panels.** The scene answers you live, and the conversation continues
   inside the page (WP-89's thread, drawn as panels instead of chat bubbles).
4. **A moment to solve** (§3.4), where one exists.
5. **Resolution panels.** The ending is drawn, not summarised.
6. **The last panel, «À suivre…».** The hook, in the voice of the story.

Art: every panel is drawn with the characters acting, in the approved style and
under the WP-88 allowance. The page never waits for a drawing longer than a set
time; the plate is the fallback, never an endless «sous presse».

### 3.3 A story worth following

- **A season spine with a central question and real stakes for the learner.**
  Each season has one dramatic question, 6–8 authored **tentpole** episodes
  (reveals, a mid-season reversal, a finale) written by the writers' room and
  reviewed by the owner, and **three endings** that depend on the learner's
  choices. Generated episodes fill the days between tentpoles.
- **The learner is a protagonist.** They have their own reason to be in Paris, a
  secret or an inheritance, revealed across the season. They hold information
  others don't, and are asked to take sides.
- **Episode grammar, enforced.** Every episode has a goal, an obstacle, a turn and
  a hook, and ends with something changed (a value turn). The director refuses the
  errand episode: no «soirée comme une autre», no task that could happen on any day.
  Each generated episode must visibly advance a thread, a relationship or the
  mystery.
- **Wants in conflict.** The cast's wants collide: Margaux wants to keep the café,
  the landlord wants to sell to a developer, Lila wants to leave for Berlin and
  can't tell Marin, and Romy is investigating a story that touches the café.
  Friends disagree, and the learner is caught between them.
- **A tone palette, not one note.** Comedy (the Marin and Gus running gags),
  romance, rivalry, mystery and small danger (a break-in at the café, a missing
  painting). Adult stakes told in band-appropriate language. Never gratuitous.

### 3.4 Interaction that solves things

Language tasks become plot moves. Each episode carries one or two, inside the
page:

| Mechanic | What the learner does | Skill |
|---|---|---|
| **L'enquête** | Spot the contradiction between two lines (tap the line that lies); at A1, pick the picture that matches what was said | reading, listening |
| **Convaincre** | Persuade a character; they resist until the argument lands | speaking, writing |
| **Le choix** | Two options with a visible consequence («Lila s'en souviendra») | reading, judgement |
| **Déchiffrer** | Read the note, the text message, the poster: the clue is in it | reading |
| **Qui a dit ça ?** | Already exists; it becomes evidence | listening |

The grading reuses what exists: the objective grader, concept evidence and the can-do
stamps. A solved or failed moment changes the story, not only a score.

### 3.5 Less deterministic, more consequence

- Arc stages advance when the learner *acts* (solves, chooses, persuades), not on
  a day count.
- Choices are world flags the director must honour. Tentpoles have variants per
  flag, and the season has three endings.
- Complication cards (they already exist) have to matter: each one creates an
  obstacle in the next episode.
- Dramatic irony through «Précédemment» and margin notes: the reader remembers
  what the characters forgot.

### 3.6 How this relates to WP-104 «La rubrique du jour»

The rubrique serves the plot, not the other way round. The **dossier is the
plot's chapter**, and the day's situation is chosen among what the story needs next.
WP-111 defines the spine first; WP-104 then plugs the word ambition into its
episodes.

## 4. Work packages

| WP | Title | Model · effort |
|---|---|---|
| WP-108 | Le Feuilleton répare: the art pipeline and dead ends | Sonnet 5.5 · medium |
| WP-109 | Une seule maison: the story's home | Opus 5.5 · medium (IA), Sonnet 5.5 · high (build) |
| WP-110 | La planche vivante: the page with the learner inside | Opus 5.5 · high (design), Sonnet 5.5 · high (build) |
| WP-111 | La bible de saison: a story worth following | Opus 5.5 · xhigh (writing), owner review |
| WP-112 | Résoudre: mechanics that are plot moves | Opus 5.5 · high |
| WP-113 | Conséquences: choices that change events | Opus 5.5 · high |
| WP-114 | La qualité du récit: a quality loop for the story | Opus 5.5 · high |

#### WP-108 · Le Feuilleton répare
- **Art never hangs:**
  - a queued drawing with no worker to take it falls back to the in-process
    pool; the worker is checked through the existing `/health/worker`;
  - any panel still `rendering` after 3 minutes is served as its plate
    (`failed`, with a reason);
  - the local launch configuration runs a worker (or `CELERY_TASK_ALWAYS_EAGER`
    for dev);
  - the stale queue is purged.
- **Dead ends:** the legacy composer (`?view=episode`) and every route that shows
  «Your first scene opens in the session»-style emptiness while a scene exists.
- **Done when:** a fresh engine day shows drawn panels (or plates) within
  3 minutes with the worker stopped, and the E-3 walk has no `rendering` panel older
  than that.

#### WP-109 · Une seule maison
- **The tabs:** «La Une» (Home + the day's practice) · «Feuilleton» (today's episode,
  then the archive and the cast) · «Courrier» · «Cahier».
- **One way into the story:** the day's episode step opens the Feuilleton reader;
  the practice steps («L'atelier du jour») sit before and after it in the day's mark.
- **Home headlines the episode:** number, title, teaser and cast faces.
- **Done when:** in an owner walk, «where is the story?» has one answer, and the E-3
  walk reaches today's episode from Home and from the Feuilleton tab in one tap.

#### WP-110 · La planche vivante
- **The six-movement page (§3.2):**
  - the learner's balloon is inside the comic;
  - reaction panels are generated per exchange (the WP-89 thread, drawn);
  - the ending is drawn as panels;
  - «À suivre…» is the last panel.
- **Art direction:** at least two characters in frame, and actions rather than tableaux.
  Prompts come from the director's `visual_direction`, with a verb required per panel.
- **Captions or balloons:** owner decision F-2.
- **Done when:** a whole episode reads as one page on a phone, with the learner's
  lines in it. The E-3 walk screenshots show it.

#### WP-111 · La bible de saison
- **Rewrite season 1** as a spine around one central question with learner stakes
  (owner decision F-1): 6–8 tentpole episodes as authored pages with art, a
  mid-season reversal, three endings, and the learner's backstory revealed across
  the season. Reuse the existing tentpole material.
- **Director rules:** the episode grammar (goal, obstacle, turn, hook, value change),
  the no-errand rule, a visible advance per episode, conflicts between wants, and
  the tone palette.
- **Seasons 2 and 3** are re-cut to the same shape (season 3 «Les clés du Mistral»
  already has the stakes; it gains its question and endings).
- **Done when:** the owner reads the season-1 bible and the first 10 days of a
  fake-provider life, and would read on.

#### WP-112 · Résoudre
- **The mechanics (§3.4):**
  - L'enquête (contradiction), Convaincre, Le choix, Déchiffrer and Qui a dit ça ?
    as evidence;
  - each is posed inside the page, graded with the existing graders;
  - each has an effect on the story.
- **A per-band design:** A1 recognises (pictures, taps), A2 selects and completes,
  B1+ argues and deduces.
- **Done when:** at least 70 % of episodes in a 30-day harness carry a solve or a
  choice, and each outcome visibly changes the next episode.

#### WP-113 · Conséquences
- **Events, not counters:** stages advance on learner actions, and choice flags are
  enforced in the director.
- **Variants:** tentpole variants per flag, and three season endings.
- **Complications:** complication cards must create an obstacle.
- **Done when:** two harness learners making opposite choices at the first
  tentpole read visibly different episodes afterwards and reach different endings.

#### WP-114 · La qualité du récit
- **A story critic** scores every generated episode on a rubric: hook, stakes,
  value turn, not an errand, advances a thread, in character. It gets one retry,
  then acceptance is logged.
- **An offline A/B of director models** (ideas doc #1) on 14-day lives; the
  owner does a blind read.
- **Metrics:** next-day return, «À suivre» tap-through, choice distribution,
  and the share of errand episodes.
- **Done when:** the errand share falls below 10 % in the harness, and the owner's
  blind read prefers the new director.

## 5. Order

1. **WP-108** now: the story cannot be judged while its pages never finish printing.
2. **WP-107** (the owner's second test: session refresh, harder B1 drills, less text,
   the E-3 findings).
3. **WP-111** (the spine), together with **WP-109** (one home) and **WP-110** (the page).
4. **WP-112** and **WP-113**, then **WP-104** plugged into the episodes, then **WP-105/106**.
5. **WP-114** runs alongside from WP-111 on.

## 6. Owner decisions

| # | Decision | Options | Recommendation |
|---|---|---|---|
| F-1 | Season 1's central question | (a) **«Le Mistral va fermer»**: who is behind the sale, and why Margaux is lying; (b) **«La lettre de Berlin»**: Lila's hidden past and a missing painting; (c) **«L'héritage»**: the learner came to Paris because of a key and a letter from a grandmother who lived above Le Mistral | **(c) fused with (a):** the learner's inheritance turns out to be tied to the café's walls. Personal stakes and the group's home at once. (b) stays as the season's B-plot |
| F-2 | Captions under the art (the 2026-09-17 choice) or balloons in the art | Balloons read as a comic; captions read better on a phone and translate better | Keep captions for character lines, but draw **the learner's line as a balloon** in its panel: the moment they enter the comic |
| F-3 | The tabs | See WP-109 | «La Une · Feuilleton · Courrier · Cahier» |
| F-4 | Branching depth | Foldback with flags, 3 endings per season | Yes. Full branching is unaffordable, and foldback is how the good ones do it |
| F-5 | Tone boundaries | Comedy, romance, rivalry, mystery, small danger | Yes. No violence beyond a break-in, no politics, and romance stays PG |
