# Pilot packages · 17 Nov 2026

Twelve packages that turn the findings of the experience review (`docs/ops/walks/2026-11-17-experience-review.md`) into work before the ten-learner pilot. Read from `origin/main` at `d1486e6c`. Line numbers are from that commit; check them before editing.

These files are untracked. Nothing was committed.

## How this relates to what already exists

- **These are the pre-pilot slices, not new designs.** Where a structural package of 9 Nov covers the root (S1 one day brief, S3 learner text contract, S5 season rollover, V verdict ledger), the package here is the smallest change that removes the learner-visible fault, written so the structural package can replace it later.
- **Thirteen open pull requests already answer parts of the findings.** They are listed per package as «land first». I have read their titles, not their diffs: each needs a review and a rebase before it counts.
- **Rules for the implementing agent** are those of `docs/implementation/structural-2026-11-09/README.md`: Opus 5.5 at medium effort, one stage per pull request, own worktree cut from `origin/main`, draft PRs, the failing guard first, a full A1-de and B1-en day played before handing over, at most four agents at once, and one open PR at a time on `app/services/daily_journey.py`.

## Decisions needed from the owner before work starts

| # | Decision | My proposal | Blocks |
|---|---|---|---|
| 1 | New words a day on «Normal» | **Decided 17 Nov: 15** | P7 |
| 2 | Corrections shown per scene reply | 1 at A1–A2, up to 3 from B1 | P3 |
| 3 | B1 learners in the pilot | Yes, but only after P6 stage 3; otherwise recruit A1–A2 only | recruiting |
| 4 | Le Papier, La Radio, Le Correcteur | Off for the pilot (config) | P0 |
| 5 | Gold counter | Hidden for the pilot (config) | P0 |
| 6 | Story writer | **Decided 17 Nov: Sonnet 5.5.** Opus is too expensive and the app must run on a cheaper model long term | P0 |
| 7 | Listening day | Not before a learner's day 8 | P9 |
| 8 | The «Rappel» block around the scene | Only the learner's own past mistakes and due rules; no scene-line dictation or cloze | P6 |

## Order

| Slot | In parallel (own worktrees) | Notes |
|---|---|---|
| Day 1 | P0, P1, P2, P8 | No shared files. P0 is mostly the owner's Render step. |
| Day 2 | P5, P3, P7 stage 1, P9 stage 1 | P5 is the only one on `daily_journey.py`. |
| Day 3 | P6, P7 stage 2, P4, P10 | P6 stage 2 touches `daily_journey.py`: after P5 has merged. |
| Day 4 | P11, P6 stage 3, P9 stage 2, P12 stages 1–3 | P12 is frontend; no shared files with the others. |
| Day 5 | P12 stages 4–6 | Stage 4 after P3. |
| Day 6 | Walk a full A1-de and B1-en day on the pilot build, on a phone, with sound, once as pages and once in the Quartier | Handover step 8; P12 stage 7. |

After the pilot: the season's end page and consequences (S5 and review finding 6), typed vocabulary, B1 templates beyond the pilot week, a test of still cheaper writers (one draft, the live model).

**Le Quartier** is to be switched on and become a major part of the app (owner, 17 Nov). It gets its own package, P12, written after it has been played properly: the review could only read its menus.

---

## P0 · Switches, no code · an afternoon, mostly the owner's

**What.** Five values in `render.yaml` and the Render dashboard, on both services.

| Setting | Today | Pilot | Why |
|---|---|---|---|
| `MISSION_CHAT_TIMEOUT_SECONDS` | 2.0 (`app/config.py:78`) | 15 | Courrier replies timed out and fell back to the stock help-desk line (finding 7). |
| `REVUE_ENABLED`, `REVUE_RADIO_ENABLED`, `REVUE_CORRECTEUR_ENABLED`, `REVUE_COMPTOIR_ENABLED`, `REVUE_PLATE_GENERATION_ENABLED` | true | false | `REVUE_MIN_BAND` only stops the news day shape (`revue/policy.py:431`); the card and chips reach every level (finding 15). |
| `ATELIER_GOLD_UI` | all | off | Removes the pill and «vers la journée pleine» (finding 14). The ledger keeps running in shadow. |
| `NEXT_PUBLIC_LEGAL_CONTACT_EMAIL` (build) | unset | the legal address | Help prints «[contact e-mail]». |
| `STORY_WRITER_MODEL` | claude-opus-5-5 | claude-sonnet-5-5 | Owner decision of 17 Nov. Measured about US$0.19–0.33 a page against about US$0.37–0.54. |

**Stage 2 (code, small).** With a 15-second timeout the Courrier needs a visible «is writing…» state, one retry, and the help-desk fallback (`missions.py:7535`, `:6805`) must never be shown in a character's thread: use `_unassessed_acknowledgement` in the character's register instead.

**Guard.** A test that a timed-out character reply never returns either fallback string and keeps the letter's register.

**Land first.** #788 (a character keeps its letter's tu), #569 (reply follows the learner's choice; rebase or close in favour of #788).

---

## P1 · A stored fault never stamps a correct reply · half a day

**Finding 1.** «→ leur · On dit « leur », pas « lui »» on about eight correct replies.

**Mechanism.** `feedback_decision` (`app/services/journey_conversation.py:3441`) scans the learner's last 24 stored faults (`_scan_errata`, `:3094`) and matches them against the new reply by word alone (`_contains_phrase`, `:3016`). The only gate, `_wrong_here` (`:3134`), calls `verify_edit`, which proves the swapped sentence is acceptable French, not that the learner's word was wrong here. On season days (`in_margin`, `:3300`, `:3500`) the bounds that limit this to once per scene are skipped, and `apply_feedback_policy` (`:3678`) lets the stale pair displace the model's own correction.

**Change.**
1. A stored fault is shown only when the reply is also wrong without it: the tutor lane's verdict (or the model-free rules) must flag the same span. Otherwise it is dropped.
2. Season days get the same bounds as other days: at most one stored-fault note per scene.
3. The model's correction outranks a stored one.

**Guard (fails on main).** Stored fault `lui → leur`; reply «Je vais lui poser des questions.» → no correction. Reply «Je le leur donne» with stored `leur → lui` → no correction. Three replies containing «lui» in one season scene → at most one note.

**Files.** `journey_conversation.py`, tests. No overlap with other packages.

---

## P2 · A declared level is never lowered automatically · half a day

**Finding 2.** B1.1 stored as A1.1 after the 40th checked answer; interface language and rule level changed with no message.

**Mechanism.** `_estimate_with_declaration` (`app/services/cefr_progress.py:580–627`): from `DECLARED_LEVEL_EVIDENCE_ATTEMPTS = 40` (`:129`) the measured level replaces the declared one outright. Measured is one band above the highest closed checkpoint (`_computed_level`, `:498`), so a learner who closed none is A1.1. The no-downgrade guard exists only in `achievement_recap._measure_up` (`:372`); the persisting callers (`atelier_session_complete`, `mission_complete`, `feuilleton_complete`, `lazy`) have none.

**Change.** The stored level never moves below the declared or placed level without a settled placement. A measured level below it is recorded in the payload (for `/pilot-ops`) and changes nothing the learner sees. Moving down becomes an offer («check your level»), which already exists.

**Guard.** A declared B1.1 learner with 40 checked attempts at 50 % errors and no closed checkpoint stays B1.1 through every persisting source; `user_chrome_language` is unchanged.

**Files.** `cefr_progress.py`, tests.

---

## P3 · The scene corrects what the day teaches · 1–2 days · decision 2

**Finding 1.** One flag per reply, often an apostrophe while a missing subjunctive stands on the subjunctive's own day.

**Mechanism.** The tutor lane (`app/services/story_lanes.py`, prompt `:205–226`, `validate_tutor` `:623–682`) is asked for «at most one correction… the most structural one» and is not told the day's rule. `first_valid_edit` (`correction_contract.py:3340`) then keeps one.

**Change.**
- Stage 1: pass the day's rule (and rules introduced in the last 7 days) to the tutor payload (`tutor_payload`, `:495`); an error against one of them is chosen first. Explanations must state the rule, never «the correct form is X».
- Stage 2 (after decision 2): from B1 the lane may return up to three corrections; `RespondThread.tsx:118–135` lists them, the first open.

**Guard.** Fixture replies from the walk (B1 day 4, three missing subjunctives with the subjunctive as the day's rule) → the flagged span is a subjunctive. An explanation that only repeats the corrected form is refused.

**Files.** `story_lanes.py`, `living_story.py` (the non-lane path, `:10940`), `RespondThread.tsx`.

---

## P4 · Wrong corrections found in the walk become the judge's test cases · 1–2 days

**Finding 1.** «beaucoup → beaucoup et», «pas avec de lait», «elle me le rend» accepted for «la clé», «le valise» accepted, «je le remercie» refused, «Ils vont dans le métro» refused, «la notaire» corrected to «le notaire».

**Mechanism.**
- Journal: `sentence_gaps` (`correction_contract.py:3547`, insertion branch `~3578`) turns a word the model added into a «wrong → wrong + word» fix that passes `_refused_change` (`:3648`).
- Scene: only `first_valid_edit` runs; the full-line fixpoint check of #860 (`verify_correction`, `:3692`) is not applied.
- La Forge: free answers are judged by key, memo, then model (`atelier.py:5896`, `forge_grading.py:547`, `:1155`); nothing re-checks gender or number of a pronoun against its antecedent, and a correct answer outside the accept-list depends on the model.

**Change.** Each of the seven cases becomes a row in the negative corpus the verdict stack already uses, with the surface it came from. Then fix by mechanism: a derived insertion is shown only as an insertion («il manque « et » après…»), never as a replacement of a correct word; the scene's printed edit passes the same fixpoint check; the Forge's «right» for a free sentence requires the rule pass to be silent on it.

**Guard.** The seven cases, red on main.

**Land first.** #705 (Journal retell checked against the scene), #789, #834, #606. This package belongs to the verdict stack; do not open it while that stack has unmerged PRs on `correction_contract.py`.

---

## P5 · No solution before the retry in the scene's drill · 1 day

**Finding 3, owner rule of 13 Nov.** In «Rappel» / «Avant la scène» one wrong tap shows the answer, then the same item returns.

**Mechanism.** `_attempt_recall` (`app/services/daily_journey.py:5522`) returns `corrected_fr` with the miss (`:5594`); `JourneyFeedbackView` (`JourneySteps.tsx:1812`) prints it, and the device-side key highlights the right card before the server answers (`:560–601`). `solution_gate.py` (#767) is wired only into La Forge.

**Change.** On a miss whose re-ask is queued (`_queue_retry`, `:5609`), the response withholds `corrected_fr` and the highlight; it says where and why. The solution is shown after the retry or when no retry follows. Two-option items are exempt (the miss is the answer).

**Guard.** A missed three-option pick with a queued retry: the payload has no corrected line and no correct option; after the retry it has both.

**Files.** `daily_journey.py` (one PR at a time), `journey_learning.py`, `JourneySteps.tsx`, `lib/answer-key.ts`.

---

## P6 · One grammar step a day, and a rule that is learned leaves · 2–3 days · decision 8

**Finding 3.** être three times on day 1 and again on days 2 and 5; one B1 rule for four days with five sentences; La Forge 9–13 items against «five minutes».

**Mechanism.**
- A rule stays the daily Forge anchor until `held_at` is set, which needs two free uses seven days apart (`concept_life.py:50–60`); `_anchor` step 5 (`forge_picker.py:~362`) ignores that the rule is already at the top rung.
- Session length is `budget / seconds per item`, clamped 6–24 (`app/core/forge.py:112–155`): 300 s gives 12.
- The drill around the scene is sized by `RHYTHM_CAPS` (`journey_contracts.py:155`): 12 recall items at the 10-minute rhythm.
- Only 4 B1 rules have templates (`app/data/grammar_templates/units_b1.json`; 38 at A1, 36 at A2); the rest fall back to a fixed set of about 15 items (`atelier.py:249–254`).

**Change.**
- Stage 1: a rule at the top rung with no miss in its last session is not the anchor again until its spaced review is due. The Forge is capped at 8 items for the pilot paces.
- Stage 2 (decision 8): the scene's drill keeps the learner's own mistakes and one due rule; scene-line dictation and cloze go. The rule card's own wrong/right pair is never the next item.
- Stage 3: templates for the B1 rules a pilot learner can meet in week one (the first eight of the B1 order), or decision 3 excludes B1.

**Guard.** A learner at level 6 on a rule after a clean session: tomorrow's anchor is another rule. A planned A1 day at «Normal»: at most 8 Forge items and at most 4 drill items. No Forge session serves one sentence twice within 7 days for a B1 rule in the week-one list.

**Land first.** #587 (Forge and Home open on the rule the pre-scene card teaches), #476.

**Later.** S1 (one day brief) replaces the choosers this patches.

---

## P7 · A word deck made of the story and the learner · 2 days · decision 1

**Finding 4.** 1–5 of about 20 words from the scene; «valise» saved and never served; 100 cards after an absence; the «25 words a day» banner.

**Mechanism.**
- Scene words are capped at a third of the new slots (`SCENE_SHARE_OF_NEW_WORDS`, `app/services/deck_order.py:48`); the rest is the core list by frequency (`progress.py:652`).
- A kept word is stored as a review due now (`kept_words.py:203`), but the day's review list is frozen at first read and cut by due date and priority (`day_words.py:205`, `progress.py:578–638`), so it can fall out.
- Reviews are bounded only by the 100-card deck limit (`daily_session.py:86`, `:223`).
- The banner and «5 more words» have no switch (`web-frontend/lib/more-words.ts`, `fertig.tsx:212`, `review.tsx:235`).

**Change.**
- Stage 1: order of the day's new words is kept words, then words the learner tapped or missed, then all of the scene's words, then the core list up to the quota. A kept word is always in the next deck. After two or more missed days, reviews are capped at 20 until the backlog is cleared. «Normal» deals 15 (decision 1; `PACES` in `daily_session.py:63` and the duplicate `PACE_WORDS` in `settings.tsx:241`).
- Stage 2: remove the banner and the endless «5 more» from the end screen and the deck's end; keep the offer in Settings.

**Guard.** A learner keeps «valise» on day 1 → it is in day 2's deck. A day with 6 scene words and a quota of 15 → all 6 are dealt. A return after 4 days with 80 due → 20 reviews. No end screen renders the banner.

**Land first.** #741 (a card front in English or German says the French is asked).

**Later.** Typed and in-sentence answers for half the deck.

---

## P8 · Today's page answers yesterday's hook · 1–2 days

**Finding 5.** Hooks dropped the next day; «Précédemment» still titled day 1 on day 6; three days titled «Le Mistral».

**Mechanism.**
- The hook (`live["next_teaser"]`, written in `settle_resolution`, `living_story.py:11813–11862`) is read by Home, the push and the recap only. The planner payload (`story_split.py:~672`) and `recent_days` (`:~608`) carry no hook, and the critic's `moves_on` (`season/director.py:767`) refuses the same question as the last three days.
- `previously_lines` (`living_story.py:3957`) prints the newest closed chapter's title; generated days close no chapter until the next tentpole.
- The title guard is exact-match only (`unique_scene_title`, `living_story.py:7159`).

**Change.**
1. Yesterday's hook goes into the planner payload as `yesterday_hook`; the plan must name the panel that answers it (or the line that refuses it). A critic item `takes_up_hook` joins the acceptance condition, and `moves_on` exempts it.
2. «Précédemment» is built from the last two days' end summaries, with the last played day's title.
3. A title that is a place name or equals one of the last 15 is refused.

**Guard.** A generated day after a hook «Que décideras-tu pour ton vol ?»: the plan references the hook; a page that never mentions the flight is refused by the critic fixture. Day 6's `previously_fr` does not start with «Le mauvais accueil». A draft titled «Le Mistral» is refused.

**Land first.** #633 (one title per episode), #549 (close in its favour), #455 (tomorrow's hook tells what you promised), #764.

**Files.** `story_split.py`, `season/director.py`, `living_story.py` (previously, title). Not `daily_journey.py`.

---

## P9 · Fewer rooms, and the Journal on Home · 1–2 days · decision 7

**Findings 8, 10, 13.**

**Change.**
- Stage 1 (frontend):
  - Home gets a Journal chip when yesterday's retell is waiting (`/notebook?mode=journal`; today Home links only `releve`, `grammar`, `library`: `HomeScreen.tsx`, `lib/atelier-next.ts`).
  - The «Check your level» chip (`PlacementOfferChip.tsx:19`) waits until day 8.
  - The walkthrough drops «Les quatre formes» and «Où tu en es» (`Walkthrough.tsx:36–95`).
  - The try-first scene accepts «Un café, merci» (`lib/onboarding-taste.ts:104–157`).
  - «Revoir» opens the episode in the archive reader, not only the end card (`JourneyTodayCard.tsx:512`).
- Stage 2 (backend):
  - No listening day before a learner's day 8, and never when the learner's setting is off (`journey_day_shapes.py:309–325`; the setting is device-local today and has to reach the server).
  - The return card gains two lines of what happened (`journey_absence.py`).
  - A push to an A-level learner carries a gloss in their language (`serial_notifications.py:540`).

**Guard.** Static tests in the style of `home.test.js` for each Home change; a planner test that day 3 is not a listening day.

**Land first.** #675 (an unfinished day closes overnight), #672, #791, #800.

---

## P10 · The strings that are in the wrong language · 1 day

**Finding 9.** The pre-pilot slice of S3.

| String | Where | Change |
|---|---|---|
| «Express a complete sentence in French using …; use every target chip once.» | `app/services/atelier.py:1159`, `:1130`, `:3948` | Never shown: a build card without a real meaning cue shows the task line only. |
| English gloss for German learners («at the newsroom», «ring») | grader prompt `atelier.py:8284` («a short English gloss») | Ask for the gloss in the learner's mother tongue. |
| «… heard what you said. The rest stays open.» | `living_story.py:11302–11306` | Use the interface language, not the mother tongue. |
| Nav «Settings» on French pages | `EditorialMasthead.tsx:62–70` | Use the level-aware language. |
| «Check your level» | `PlacementOfferChip.tsx` | Same. |
| «Mode POV», «a threshold still on trial» | `feuilleton-copy.ts:241`, `band-check-copy.ts:149` | Plain wording. |

**Guard.** The S3 source guards, extended to these files; a test that no `meaning_cue` starting with «Express» reaches a response.

**Land first.** #707 (done screen and Forge end card in the learner's language), #608.

---

## P11 · Waiting and failing without losing the learner · 1–2 days

**Findings 6, 12.**

**Mechanism and change.**
- **The last panel with no button.** `FeuilletonReader.tsx:715–719` renders nothing while `finale.waiting`; there is no timeout. After 30 s show «Continue» and let the server's authored ending heal it.
- **A lost day served as «Relecture».** `_serve_season_reprise` (`daily_journey.py:4547`) after `generate_scene` fails. For a tentpole day (authored), a re-read should be impossible: find why T8 day A could not be served and make an authored day never fall to the re-read. Touches `daily_journey.py`: after P5 and P6 stage 2.
- **Word grades given offline.** `review.tsx:831` shows a toast and drops the grade. Queue it and send on reconnect, as the journey does (`lib/journey-recovery.ts`).
- **«Erneut versuchen» after a failed «Weiter»** returns to the previous step and restarts the panels: reproduce with the harness's `offline` command, then fix.
- **The night run.** Log the refusal reason of every «unavailable» (`journey_latency.py:394`) to `/pilot-ops`, so the pilot shows how often and why.

**Guard.** A reader test for the 30-second escape; a planner test that an authored day cannot be served as `season_reprise`; a review test that an offline grade is sent after reconnect.

**Land first.** #641 (copy the correction takes the whole line), #632, #818.

---

## P12 · Le Quartier switched on, and one with the day · 3–4 days, then a device test

**Owner, 17 Nov:** the Quartier is switched on and is a major part of the app. Review finding 17 (played on 17 Nov; `docs/ops/walks/2026-11-17-experience-review/logs/quartier.md`).

**Where it stands.** `/quartier` stages the day's own journey through the journey's endpoints (`web-frontend/lib/quartier/journey-story.ts`), so a scene played there is the day's scene. It is hidden by `quartierVisible: false` in `web-frontend/launch-flags.json`; the Home chip «Le Quartier 3D» sits behind it (`HomeScreen.tsx:468–476`), a production build answers `notFound` (`pages/quartier.tsx:44–49`), and a release build refuses the env override (`scripts/native-export-policy.mjs:129–177`). Tests pin the door closed (`quartier-door.test.js`, `home.test.js:128`).

**Stages**

1. **Open the door (half a day).** `quartierVisible: true`; the tests that pin it closed are turned round. Home's start button offers the scene both ways once («Im Quartier spielen» / «Als Seite lesen») and remembers the choice; the chip stays. Owner decision 9 below.
2. **One day, one state (1 day).** After a scene played in 3D, Home's tracker shows the scene done, the Feuilleton archive holds the page with the learner's answers, and the episode has one number everywhere («Épisode 8» and «Épisode 2» today).
3. **A beginner can read it (half a day).** The mother-tongue line under each card is on by default below B1 and the «DE» chip says what it does the first time. «Un exemple» (the full sentence) is offered only after one attempt.
4. **Free talk is corrected (1 day).** A line typed to a person outside the scene's script goes through the tutor lane of P3: one correction at A1–A2, up to three from B1.
5. **The notebook reads the story (1 day).** «Ton carnet» lists the people the learner has met and what they know of them, the places of played days and the learner's choices, from the same record the trombinoscope and the end card use. Today it lists places from Le Papier.
6. **A place is finished or it is not served (1–2 days).** A check per staged day: every mark has a floor, walls and a camera that frames the speaker; no English stage direction reaches a card; map labels do not overlap. The stairwell of «Là-haut» and the betting counter fail it today. A day whose place fails falls back to the flat page. This is the owner's rule of 13 Nov made testable (every place walkable, on the map only if far enough).
7. **On a phone (owner + one session).** Load time, frame rate, heat and battery on the owner's iPhone and on the oldest model a tester may have; sound. Nothing in this review says how it runs on a device.

**Guards.** A walk test (the harness now has `tap`, `drag` and `hold`) that plays episode 1 in 3D and then asserts Home, the archive and the step counter agree. A static test that a learner below B1 gets `gloss` lines by default. The place check of stage 6 runs over `STAGED_DAYS` in CI.

**Files.** `web-frontend/pages/quartier.tsx`, `lib/quartier/*`, `HomeScreen.tsx`, `launch-flags.json`, `scripts/native-export-policy.mjs`; server side only for stage 2 (the journey's scene acknowledgement) and stage 5.

**After the pilot.** Roaming with a purpose (things to find that carry the day's words), more streets than the quai, the Papier's places decided with decision 4.

**Owner decision 9.** For the pilot, is the Quartier (a) the default way to play the scene, with the page as the fallback, or (b) a choice beside the page? My proposal: (b) until stage 7 has been done on a phone, then (a) if it runs well.

---

## Open pull requests not named above

- **#845** (grammar pilot behind a flag): new, unreviewed, not needed for the pilot. Leave.
- **#582, #72:** older drafts; decide to close.
- **#649:** the season-end walk; its findings are S5.
