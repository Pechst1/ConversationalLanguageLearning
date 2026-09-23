# Work packages — 2026-09-22: production-ready, Duolingo-grade

Owner brief: find everything that still stands between the app and production, measured
against Duolingo: it works smoothly, looks beautiful, is innovative and fun, and says only
what is needed. Then propose the packages.

Method: a hands-on walk as two new learners (German A1 and English A1, 375×812, dark
theme, real provider) plus four read-only code audits: backend/ops, engagement vs
Duolingo, frontend UX/copy/design, and native iOS/release. The live-walk evidence below is
first-hand. Code citations come from the audits; the P0s were checked in code.

## 1. Verdict

The content is ahead of Duolingo: a living story that remembers the learner, real replies
from characters, and a mistake loop built on the learner's own errors. The product around
it is not ready:

- **It is not reliable yet.** Days can be lost, one slow call blocks the server, spend is
  unbounded, and learners get signed out.
- **The first five minutes are the opposite of Duolingo.** There are two sign-up screens
  and a written French test before anything fun, and the first scene takes 20 s.
- **The daily loop feels flat.** One exercise on day 1, 12–17 s per answer, no sound, no
  haptics, no faces, and no reward at the end.
- **There is too much text,** in mixed languages, sometimes at B1 for an A1 learner.

Health: about 2,900 backend tests pass (5 skipped); tsc, lint and 21 node suites are green.
CI has not run on the last 99 commits of this branch.

## 2. What the walk showed (2026-09-22, first-hand)

| # | Moment | What happened | Where |
|---|---|---|---|
| L1 | Landing | «Se connecter» is the primary button and «Créer un compte» is secondary; nothing shows what the app is like | `pages/index.tsx` |
| L2 | Sign-up | Two steps, 11 inputs, all in French for an A1 learner. The chosen interface language offers Español/Italiano/Português | `pages/auth/signup.tsx:253-340` |
| L3 | Placement | The first task a self-declared A1 learner sees is free writing in French. **The same question was asked three times** (Q2 = Q3 = Q4, «Racontez… le week-end dernier»), because the bank has one prompt per band and the ladder holds on middle or second-chance scores | `app/services/placement.py:104-135, 225-247` |
| L4 | Result | «Niveau estimé : A2.1» plus four «2.0 / 4» rubric rows. No moment, and it lands on Home, not in a scene | `pages/placement.tsx` |
| L5 | First scene | «Commencer» → «Envoi…» for **40 s → 500**. A missing column in a best-effort Courrier lookup aborted the Postgres transaction. The lookup's own comment says «a letter is never worth the day», and it cost the day anyway | `app/services/story_correspondence.py:1009-1013`, `daily_journey.py:1858, 1983` |
| L6 | After L5 | The journey is stuck in `preparing` with no claim. The card says «Deine Szene wird gerade vorbereitet. Das dauert meist nur einen Moment.» indefinitely: «Vérifier à nouveau» only re-reads, it never calls `POST /retry` | `JourneyTodayCard.tsx:281`, `daily_journey.py:1312-1320` |
| L7 | Home during L6 | Two competing cards («Heute wird vorbereitet» + «Offene ältere Übung … Ouvrir cette séance»), German bodies with French buttons, a 22-minute legacy Séance against a 10-minute goal, and 11 blocks in total | `pages/atelier.tsx:1661`, `HomeScreen.tsx` |
| L8 | First scene (healthy path) | **20.6 s** cold, with only «Envoi…» on the button. The reader then looks beautiful (painted café, tappable words), but no character is ever seen | `StoryEpisodeReader.tsx` |
| L9 | Respond step | **The answer is printed above the task.** The headline under «Marin Lévêque» reads «Marin, tu vas demander à Lila ?», which is exactly the sentence the learner is asked to produce. The objective is printed twice | `journey_planner.py:1482` (`opening_line_fr`), `JourneySteps.tsx` |
| L10 | Grading | **12.6 s.** The timer jumped «3 min restant» → «45 s restant»: server waits are charged to the learner | `journey_conversation.py:2938` |
| L11 | Day 1 volume | Scene → one reply → resolution: **one exercise** in the whole day | `journey_contracts.py:411-421` |
| L12 | Recap | «Scene finished · 3 min», one line from Marin, «Optional. It does not reopen today's scene.» No streak, no goal, no words, no teaser | `JourneySession.tsx:486-596` |
| L13 | Home after the day | No streak or goal ring, and the Séance tile still reads like unfinished work | `HomeScreen.tsx` |
| L14 | Courrier (A1.1 learner) | A B1 letter («geste commercial», «ils minimisent la panne»), 169 words. **The sticky composer is 530 px tall on an 812 px screen**; with the tab bar it covers the letter | `components/courrier/Courrier.tsx:1013-1014` |
| L15 | Feuilleton | Five season threads as B1 French questions for an A1 learner, uppercase stamps, no faces | `SeasonPage.tsx` |
| L16 | Assets | Every character has a model sheet with three expressions (sly, delighted, cross) in `public/assets/serial/characters/*/model-sheet.webp`. No learner screen uses them | — |

Local-environment note: the dev database `language_learning` is one migration behind
(`3759e1c7098c`; head `a1c4e7b90d33`, WP-64). That is what triggered L5 locally. The
production lesson is that **a single optional lookup can take the whole day down, and the
server boots against a schema it cannot serve.**

## 3. Packages

Waves: **A** = cannot launch without it · **B** = the Duolingo moment · **C** = fun and
feel · **D** = simple and beautiful · **E** = hygiene. Each package has a "done when"
line so an agent can prove it.

### Wave A — launch blockers

#### WP-69 · Never lose a day
- Put every best-effort lookup on the journey path inside a SAVEPOINT (`db.begin_nested()`),
  or give it its own session. This covers `story_correspondence.awaiting_letter`,
  `missions._sweep_correspondence` and the other `except Exception: log; return None`
  sites that share the request session.
- Server: a `preparing` journey whose claim is dead or missing is re-generated on
  `GET /today` (self-healing). Client: the preparing card's button calls `retryGeneration`,
  not `refresh`.
- Add an authored fallback scene per band (A1–C1) when both attempts fail. The learner
  always gets a day; the fallback is labelled internally, not to the learner.
- Client deadline above the server budget (`journey-requests.ts:240`, 60 s vs 75 s), and
  make retries idempotent.
- The API refuses to start, and the deploy fails, if `alembic current` ≠ head. Render
  runs `alembic upgrade head` as a pre-deploy step.
- Placement: 3 prompts per band, never repeat a prompt within a session.
- **Done when:** a test that raises inside the Courrier lookup still yields a playable
  journey; a killed generation recovers on the next `/today`; the WP-68 paid run (A2 + B1,
  14 days) loses 0 days; placement never shows the same prompt twice.

#### WP-70 · One slow call must not stop the server, and spend has a ceiling
- Move blocking OpenAI/HTTP calls out of `async def` handlers (`/audio/speak`,
  `/audio/transcribe`, mission creation, intake, graphic-novel script), using `def` or
  `run_in_threadpool`. Run ≥2 uvicorn workers (`docker/entrypoint.sh:20`).
- Per-user rate limits (auth, every paid endpoint) and a per-user daily spend cap enforced
  at request time, not only for prefetch (`journey_latency.py:314`). Complete the price
  table (`llm_service.py:100-107`).
- The LLM wrapper retries only retryable errors, under one total deadline, with a circuit
  breaker (placement included). Read `LLM_MAX_RETRIES`.
- **Done when:** a 60 s stalled provider call does not delay `/ready` or another learner's
  request; a scripted abuse loop hits 429 and the cap; the cost ledger has no $0 rows for
  priced models.

#### WP-71 · Accounts that stay signed in and can be recovered
- Native: single-flight token refresh; clear the keychain only on a real 401, never on a
  network error; give the server a short grace window for a just-rotated refresh token
  (`services/api.ts:1815`, `lib/native-auth.ts:149-159`, `app/services/auth.py:300`).
- Reject or pre-hash passwords over 72 bytes (bcrypt 5 raises). Normalise email case.
- Password reset that works on a phone: a 6-digit code entered in the app (no web host
  or universal link needed). Configure SMTP. `render.yaml`: `APP_ENV=production`.
- Pin backend dependencies (lock file).
- **Done when:** 10 parallel requests after token expiry keep the learner signed in;
  offline launch after an hour keeps the session; a reset completes on the simulator.

#### WP-72 · App Store–ready
- Privacy policy and terms pages, linked from sign-up and Réglages; a one-line consent at
  sign-up naming the AI provider.
- `NSCameraUsageDescription` (Courrier «Photographier» crashes without it), photos + name
  in the privacy manifest, `ITSAppUsesNonExemptEncryption=false`, iPhone-only
  (`TARGETED_DEVICE_FAMILY=1`, portrait).
- A real icon and a branded launch screen (the current set is Capacitor's placeholder).
  One name everywhere (the Info.plist says «Feuilleton»).
- The fastlane archive lane builds the production web bundle itself and asserts the API
  host and push flags; APNs production environment for TestFlight.
- Leave dev/QA pages out of the native export (`/mobile-visual-qa`, `/atelier-v2-gallery`,
  `/dev/*`, `/bibliotheque/*`).
- **Done when:** an archive from a clean checkout passes an App Store Connect validation
  upload with no warnings.

#### WP-73 · See production
- Sentry (or equivalent) in the API, the worker, web and native; the crash endpoint works
  before sign-in. JSON logs, so the 69 calls passing extra fields stop dropping them;
  request IDs; a worker liveness check; a documented backup and restore.
- **Done when:** a thrown test error in each tier appears in the dashboard with a request
  ID; a restore drill is written down.

#### WP-74 · Honest data
- Missions must not write placeholder English or uncorrected learner text into
  `VocabularyWord` as "correct" (`missions.py:3057-3151`). The Courrier fallback grader
  returns `unassessed`, never `accepted` (`missions.py:2536`).
- «Mots acquis» counts a real state (the scheduler never writes `mastered`).
- The GDPR export includes journal, missions, intake, rehearsals and story state.
- **Done when:** a grader outage produces `unassessed`; the Relevé and Dossier show the
  same word count.

### Wave B — the first five minutes

#### WP-75 · A win before an account
- **Taste first:** one authored, pre-rendered 60-second scene before sign-up. Romy greets
  the learner, who answers with two tile taps: instant, local, no model call, portrait
  reacting. Then «Gardez votre histoire» → an account with email + password only.
- Onboarding copy in the learner's language up to A2. Everything else on sign-up step 2
  gets a default and moves to Réglages. Keep one question: «Nouveau / Quelques bases /
  À l'aise».
- «Nouveau» skips placement entirely. Placement is offered after day 3 and uses journey
  evidence, never as the first task for an A1 learner.
- The day-1 scene is ready before it is asked for: generated at sign-up, or authored per
  band. After sign-up the learner lands in the scene, not on Home.
- Day 1 introduces the cast (three faces, one line each) before dropping the learner
  into Marin's proposal arc.
- **Done when:** from install to the first correct answer takes ≤ 60 s and ≤ 6 taps on
  the simulator; no waiting screen longer than 2 s on day 1.

### Wave C — fun and feel

#### WP-76 · Instant, physical feedback
- Choice, tiles and word bank are graded on the device against a hashed key, so the
  answer is not revealed. The server confirms in the background. Tiles turn green or
  red, answers shake or pop.
- Haptics in the V2 journey (success, error, finish). A small optional sound set
  (correct, wrong, day complete), with a toggle in Réglages. Respect Reduce Motion.
- Stream the character's reply to the respond step: the portrait "types" while the model
  writes. Perceived wait under 2 s even when p50 stays 12 s. The timer counts only the
  learner's time.
- Fix the duplicate word bank (`JourneySteps.tsx:403/416`) and the wrong-answer title
  contrast in dark mode (`atelier-v2.css:244,1021`). Set `autocorrect="off"` on every
  French input.
- **Done when:** a recall answer is coloured within 100 ms of the tap; the respond step
  shows the first words of the reply within 2 s; every state has a haptic.

#### WP-77 · The cast has faces (the mascot the owner already has)
- Crop the existing model sheets into three expression portraits per character (neutral,
  delighted, cross) and add a mood → expression map.
- Use them for: dialogue lines in the reader, the respond step's speaker, the verdict
  (the character reacts to *your* answer), the recap mood chip («Lila vous sourit ↑»),
  the Courrier sender, and the push notification image.
- Engine: the respond step's `opening_line_fr` must be the character speaking **to** the
  learner. Add a guard that refuses an opening line that fuzzy-matches the expected
  utterance or restates the objective (the same no-spoil principle as the Atelier's three
  gates). The character's reply renders as their speech, not inside the grading card.
- **Done when:** every character line on every surface has a face; the L9 spoiler
  reproduces as a refused draft in a unit test.

#### WP-78 · A real day's worth of practice
- 6–10 quick interactions per day before and around the one open reply: recall, matching
  pairs, listen-and-tap (turn `ATELIER_EPISODE_AUDIO_ENABLED` on so the listening day can
  be dealt), unscramble. Day 1 = warm-up tiles → scene → reply → one recall of the new
  word.
- Tap-to-keep: a tapped word joins the Lexique with its scene sentence and returns in a
  later scene.
- **Done when:** the median day has ≥ 6 graded interactions and still fits the stated
  minutes; the 126-day evidence harness reports the new mix.

#### WP-79 · End of day feels like a reward
- The recap as one screen: the streak «Jour N» (a checked, honest streak; shown as seals,
  WP-D5, not a flame), the completed mark (WP-D1; owner 2026-09-22: no goal ring),
  «+3 mots» with the words, the character's mood change with their portrait,
  the day's keepsake vignette (already minted, never shown), and «La suite demain», a
  one-line teaser written by the engine.
- An honest streak: check the date on read (today, stale-after-a-miss is a bug:
  `atelier.py:1847`), plus one «jour de relâche» freeze earned per full week.
- Achievements: either write the fields they need (`current_streak`, `total_xp`, a real
  mastered state) or cut the list to the ones that can be earned; show a level-up moment
  when the CEFR band moves. Delete «La durée n'est pas encore mesurée».
- **Done when:** a day finishes on a screen with streak, goal, words, a face and a teaser,
  and every achievement shown is reachable by a test learner.

#### WP-80 · A reason to come back tomorrow
- Push is on by default in the native build. Ask for permission after the first finished
  scene, with a one-line pre-prompt («Marin vous prévient quand la suite arrive»).
- The morning push is the recap's teaser, in the character's voice with their portrait,
  deep-linked into the scene, at the learner's reminder time **in the learner's
  timezone** (today it is hard-coded to Paris).
- Fix the streak-at-risk push (`User.current_streak` is never written) and schedule the
  review reminder; move its copy to «vous», no emoji.
- The story notices an absence: a returning learner is greeted by a character, and the
  short day is labelled «Reprise en douceur · 3 min».
- **Done when:** a simulator learner who finishes day 1 receives the teaser push at their
  local reminder time and lands in the scene from it.

### Wave D — simple and beautiful

#### WP-81 · Home does one thing
- The hero is the day's scene: art, title, one red 3D-press button (`.av2-btn`, owner
  2026-09-22). The header carries the streak and the mark as the day's progress (WP-D1; no
  goal ring). At most two quiet chips below it (Lexique due, a letter waiting).
- The journey card goes into `HomeScreen`'s hero slot, with a safe-area inset (not above
  the masthead). Dossier, «Vos documents», «Plus de pratique» and the legacy séance move
  to Cahier or Réglages. The «Offene ältere Übung» card goes.
- **Done when:** Home at 375×812 shows ≤ 5 elements above the tab bar and ≤ 25 words.

#### WP-82 · The text diet and one language rule
- Apply the "cut this text" table from the frontend audit (appendix A). Target: ≤ 15
  words of chrome per screen; objectives printed once; icons in place of explanations.
- One language rule per learner level: up to A2, instructions and status in the
  learner's language, with story content and nav labels in French. From B1, French
  chrome. Never two languages inside one card (L6/L7/L12).
- Chrome French is written at the learner's level: season threads, Courrier headers.
- **Done when:** a scripted word count per screen passes the target; no card mixes
  languages in the EN/DE/FR walkthrough.

#### WP-83 · Layout and polish
- Courrier: the composer is collapsed by default (a «Répondre» pill expands it) and
  never sticky over the letter (`Courrier.tsx:1013`). One-line header.
- Key the page transition on pathname, not the full URL (shallow query changes remount
  whole tabs, `Layout.tsx:109`).
- One loader: the skeleton during session load, instead of an unlabeled spinner then a
  skeleton. One `useSession`.
- Toasts become inline notices on av2 tokens, clear of the Dynamic Island.
- Dynamic Type (`html{font:-apple-system-body}`, drop the fixed px root). `<Html lang>`
  follows the chrome language. Favicon, `theme-color` per theme, Home hero image eager.
- One name per place: the tab is «Courrier» (not «Missions»), and there is one «Retour».
- **Done when:** a full browser + simulator walk at 375 px in both themes finds no
  overlap, no double loader, and no clipped header.

#### WP-84 · Content at the learner's level
- Courrier letters, season thread copy and story objectives are generated and validated
  against the learner's band (the A1.1 learner got «geste commercial»). Objectives are
  always in the learner's language (WP-68 §8).
- Backfill noun gender and show le/la in the Lexique and the word sheet. Fix the POS
  heuristic («frère», «hiver», «notre» tagged as verbs).
- **Done when:** a lexical-level check on 50 generated A1 letters passes; every Lexique
  noun shows its article.

### Wave E — hygiene

#### WP-85 · CI, dead weight, release path
- Open the PR to main so CI runs on the 99 unchecked commits. Add a Postgres job for the
  row-lock tests (SQLite hides them).
- Delete `mobile/` (the dead Expo app), the 28 unimported frontend files, unused
  dependencies (chart.js, recharts, socket.io-client, zustand, …) and the dead half of
  `pages/atelier.tsx` (7,092 lines, ~250 unmatched selectors).
- Prefetch in the learner's real input mode, one task per learner (today it is text-only,
  so the voice-default app never hits it).
- **Done when:** CI is green on main with the Postgres job; `_app` bundle ≤ 250 KB; the
  prefetch hit rate is logged and above 80 % for active learners.

## 4. Order

1. **A: WP-69 → WP-70 → WP-71, then WP-72/73/74 in parallel.** These gate everything;
   WP-69 is the one learners would feel first.
2. **B: WP-75** (depends on WP-69's authored fallback, which provides the day-1 scene).
3. **C: WP-77 first** (faces are cheap and lift everything after), then WP-76, WP-79,
   WP-80, WP-78.
4. **D: WP-81 + WP-82 together** (same screens), then WP-83, WP-84.
5. **E: WP-85**, starting now for the PR/CI part.
6. **Design: WP-D1..D8** (the mark as the day's plan, faces, the Seal, gender by shape) are
   in `WORK-PACKAGES-2026-09-22-design.md` and slot into Waves C/D.
7. **Learning: WP-L1..L9** (2026-09-23: the 8–10-minute day, rhythms, grammar lifecycle,
   one memory model, level = syllabus coverage + checkpoint) are in
   `WORK-PACKAGES-2026-09-23-learning.md`; WP-L1 goes first.

Each wave ends with a walk on the simulator (not only the browser pane, whose hidden-tab
hydration hides real behaviour) in both themes and three learner languages.

## 5. Owner-only

- Apple Developer Program, distribution certificate, App ID with Push, an APNs `.p8`
  key, and an App Store Connect record (privacy label, age rating incl. AI content, demo
  account, screenshots).
- Render: deploy with `APP_ENV=production`, SMTP credentials, and the cohort decision
  (`ATELIER_DAILY_JOURNEY_COHORT='*'`, or the journey is off for everyone in production).
- Host the privacy policy; decide the final name and icon.
- Consent for the paid WP-69 verification run (≈ US$0.30 at the WP-68 price).
- Local: `alembic upgrade head` on `language_learning` (one additive migration, WP-64).

## Appendix A — cut this text (from the frontend audit)

| Screen | Now | Proposal |
|---|---|---|
| Feuilleton | «Votre histoire se joue avant de se lire… Cette page garde les archives.» (`graphic-novel.tsx:1179`) | delete |
| Feuilleton | «C'est l'épisode annoncé à La Une… il n'en ouvre pas une autre.» (`:1188`) | delete |
| Respond | «Say your answer out loud. We turn it into text — nothing here judges your pronunciation.» (`journey-copy.ts:500`) | delete; the mic says it |
| Every step | kicker + «Ce que vous devez faire : …» (`JourneySteps.tsx:259,291`) | objective once, in the header |
| Recap | «La durée n'est pas encore mesurée.» / «Optional. It does not reopen today's scene.» (`journey-copy.ts:555-557`) | delete |
| Home | «Ce que nous croyons savoir de vous, et d'où vient chaque chiffre.» | move the row to Réglages |
| Home | «Plus long que les N minutes demandées — …» (`HomeScreen.tsx:243`) | delete |
| Home tiles | «1 règle · exercices» + «Plus de pratique»; «3 mots à revoir · 1 mot du jour» | one number per tile |
| Courrier (done) | credit rows, debrief rows, objectives, last message repeated (`missions.tsx:1110-1184`) | one seal: verdict, one sentence, ≤ 3 numbers |
| Mots | the due count ×5 (`vocabulary.tsx:1244-1291`) | «Réviser · N mots» |
| Grammar | «gabarit vérifié · qualité 4/5» (`grammar.tsx:480`) | delete |
| Réglages | ~490 words, 320 of them hints (`settings-copy.ts`) | hints ≤ 6 words |
| Sign-up | «Ces réponses composent la séance de demain» (false: it's today) | delete |
| Placement | 47-word lead with «cinq minutes» (`placement.tsx:216`) | «4 à 6 questions.» |

## Appendix B — keep (already excellent)

The av2 system (rem scale, 44 px floor, focus ring, Reduce Motion, the 16 px 3D-press primary); the
reader's art direction; keyboard handling in `journey-lifecycle.ts`; the cached edition on
Home; the honest server streak source; pending states on actions (no double submits); auth
design (hashed rotating refresh tokens, token versioning, hashed single-use reset tokens,
Keychain storage); per-learner data scoping; account deletion; single migration head
with CI round-trip; the story engine's publish-time concurrency checks and honest
"unassessed" paths; WebP art and self-hosted fonts.
