# The red thread: diagnosis, 10 November 2026

*Deliverable 1 of the mandate «give La clé d'Odile its red thread back». The design that answers it is `red-thread-design-2026-11-10.md`. Nothing in the product was changed to write this.*

Vincent's complaint, in his words: «Das Thema heute war etwas random, zudem wurden die neuen Orte etc. nicht mit eingebaut oder waren nicht Teil der Story. Es fehlt auch so ein bisschen der rote Faden seit ein paar Tagen.»

## 1. The finding in one paragraph

The season plan is good and the engine knows it: every one of the 45 generated days has an authored `before`, `after`, `hook` and turn in `gaps.json`. What reaches the learner is something else. On **8 of the last 10 generated days the page that was served is one the story critic had refused**, and on Vincent's last four days (g3.2 to g3.5) it was every single one. The critic's most frequent complaint was the exact thing Vincent felt: the hook exists only in a checklist the learner never sees (7 of 10 days), and the planned change is set up but not reached (at least 4 of 10). After the page, a small live model writes the ending with no obligation to the plan, the settle step records the beat as done because a page was served, and the «À suivre…» line is drawn at random from old loose ends. So the engine's own books say the story moved on while the learner watched it stand still. That gap between "recorded as done" and "true on the page" is the missing red thread.

## 2. What was read, and what was not

**Read.**

- The code path of a generated day, end to end (section 4 lists the places).
- The season canon: `docs/story/season-1/00-season-bible.md`, `09-entre-les-episodes.md`, `10-lieux-et-images.md`, `app/data/season/s1/gaps.json`, `t4.json`, `stages.json`.
- The production logs of both services (`atelier-api`, `atelier-worker`) for the seven nights from 4 to 10 November. Log retention is about seven days, so nothing older exists. Two learners were active on generated days in that window: Vincent (gap 3) and the walk test account (gaps 3 and 4).
- The live walks of 31 October to 10 November (`docs/ops/live-walks/`) and `docs/ops/walks/TREND.md`.
- The earlier code diagnosis in the project files (`story-thread/diagnosis-2026-11-10.md`) and issue #145.

**Not read, and why it matters.**

- **The production database.** A read-only connection was refused by this session's permissions, and I did not work around it. So Vincent's stored pages (`script_payload["season_page"]`), his journey rows and the pilot events (`journey_story_critic_review`, the `missed` list behind `dropped_beats`) are not in this diagnosis. The text of the 10 November page is taken from Vincent's own report in the mandate; everything else about that day comes from the logs. Where a statement rests on this gap it says "not verified".
- **No paid replay was run.** The mandate asks for Vincent's go before any paid run; the replay of the g3 week is costed in the design and waits for him.

## 3. The numbers

### 3.1 Ten generated days, 4 to 10 November

| Written (UTC) | Day | Learner | Where it was written | Full drafts | Critic reads | What was served |
|---|---|---|---|---|---|---|
| 4 Nov 02:21 | g3.7 | walk | night, writer model | 2 | 2, both refused | **refused draft** |
| 5 Nov 02:21 | g3.1 | Vincent | night, writer model | 2 | 2, second accepted | accepted draft |
| 7 Nov 02:21 | g4.1 | walk | night, writer model | 2 | 2, both refused | **refused draft** |
| 7 Nov 14:21 | g3.2 | Vincent | worker, writer model | 3 | 2, both refused | **refused draft** |
| 8 Nov 02:21 | g3.3 | Vincent | night, writer model | 3 | 2, both refused | **refused draft** |
| 8 Nov 02:24 | g4.2 | walk | night, writer model | 2 | 2, both refused | **refused draft** |
| 9 Nov 02:21 | g3.4 | Vincent | night, writer model | 3 | 2, both refused | **refused draft** |
| 9 Nov 02:25 | g4.3 | walk | night, writer model | 2 | 2, second accepted | accepted draft |
| 10 Nov 02:21 | g4.4 | walk | night, writer model | 3 | 1, refused | **refused draft** |
| 10 Nov 07:55 | g3.5 | Vincent | **live, one call, small model** | 4 | 1, refused | **refused draft** |

- **18 critic reads, 16 refusals (89%).** The first draft the critic read was accepted on 0 of 10 days.
- **8 of 10 days were served over the critic's refusal** (`journey_story_critic_override`). The log line reads «story critic refused g3.5 twice; accepted and logged».
- **"Refused twice" overstates the scrutiny.** The deterministic guards and the critic share one attempt budget (`ATELIER_STORY_MAX_ATTEMPTS`, default 2, plus one bonus attempt). On g3.5 and g4.4 the guards spent two attempts, the critic read exactly one draft, refused it, and that draft was served.
- **The critic is reachable.** It answered on every one of the ten days, so the old HTTP 400 failure (fixed in PR #649) has not returned. A review that fails silently would not show in these logs; the pilot events that would show it are in the database I could not read. Not verified.

### 3.2 What the critic said, in its own words

| Complaint | Days | Example |
|---|---|---|
| The hook is only in the checklist, not on the page | 7 of 10 (g4.1, g3.3, g4.2, g3.4, g4.3, g4.4, g3.5) | «Stage Marin's need for a taster as a concrete reason to return tomorrow rather than leaving it only in the checklist.» (g3.4) |
| The planned change is set up, not reached | at least 4 of 10 (g3.7, g4.2, g3.4, g3.5) | «Show a thread advancing to the day's planned change, not merely setting up the choice.» (g3.5) |
| A character hunts for a word in a contrived way | 2 of 10 (g3.3, g3.4) | «Replace Lila's artificial search for the word for a paper bag…» (g3.3) |
| A promised callback to the learner's own words is not staged | 2 of 10 (g3.2, g3.3) | «Stage Lila's callback to the learner's « C'est ne pas dur! » and show how that earlier agreement changes what happens today.» |
| An established fact was silently replaced | 1 of 10 (g3.1) | «Preserve the learner's established ticket date, « mercredi 18 novembre », rather than silently replacing it with « mercredi 2 décembre ».» |

The critic is right nearly every time, and it is ignored nearly every time. It names the fault, one whole new page is drawn from scratch, the new page has a different fault, and the budget is gone.

Two of these complaints are caused by the engine's own rules working against each other:

- **The hook cannot appear on the page.** In the planner, author and aids path `hook_fr` is written into `season_checklist` and nowhere else (`story_split.assemble`); no panel is asked to carry it. The critic asks for something the pipeline has no place for.
- **The word hunt is a mechanic, not bad writing.** The story-words rule tells the writer that a character must search for a word and describe it without saying it. On g3.3 the rewrite that fixed the critic's complaint was then refused by the guard `story_word_printed`, because it printed «sachet».

### 3.3 The plan's own turn is refused by the level guard

On three of Vincent's last four days the A1 task guard refused the task line the plan asks for:

| Day | Task line the writer produced from the plan's `turn` | Guard |
|---|---|---|
| g3.2 | «Lila fragt, bis wann du bleibst und warum.» | `objective_too_complex` |
| g3.4 | «Marin will wissen, ob und was du am Samstag sagst.» | `objective_too_complex` |
| g3.5 | «Sag Marin freundlich, welches Häppchen bleiben soll und warum.» | `objective_too_complex` |

The guard is right for A1 (one ask, twelve words). The plan is what is wrong for A1: 33 of the 45 authored `turn`s chain more than one ask by the guard's own separator rule. Each such refusal burns one of the two or three attempts before the critic has read anything.

### 3.4 What it costs today

| Item | Measured |
|---|---|
| One clean night draft (planner about $0.13, author about $0.09, aids about $0.04) | about $0.27 |
| One critic read | about $0.02 |
| g3.4, night of 9 November: three full drafts, two reads, served on override | about $0.79 |
| g3.2, 7 November: three full drafts, served on override | about $0.76 |
| g4.3, night of 9 November: two drafts, accepted | about $0.58 |
| g3.5, 10 November, live path: four small-model drafts and one read | about $0.02 |
| One live reply turn (about three calls) | under $0.002 |

A typical night day costs $0.55 to $0.80 and, four times out of five, pays for a page its own critic rejected. Each retry redraws the entire page from a fresh plan; nothing is repaired.

### 3.5 What the learner saw at the end of the day

On the 9 generated-day walks between 31 October and 10 November, **0 showed the planned hook**. The «Tomorrow» line was a stock opener or a fragment («Au fait…», «Dis, j'y repense…», «J'ai rien entendu», «Règle numéro un de La Méthode : on n'oublie rien») or it quoted a "promise" the learner never made (#445, #466, #620). The rubric agrees: «Would come back» has been 3 for nine nights and «Characters consistent» 2 on the last four (`docs/ops/walks/TREND.md`).

## 4. The 10 November day, from brief to teaser

Vincent, A1, German interface, gap 3 day 5, premise `les_canapes`. In the story it is Wednesday 2 December; the party is Saturday 5 December. All times UTC; Berlin is one hour later.

**The plan (`gaps.json`, g3, day 5).** Before: «Marin has six recipes and no menu.» After: «There is a menu, and one canapé has a name the learner gave it.» Also: Marchand's reply card «J'y serai. M.», if he was invited. Hook: «Lila needs the photo for the centre of the wall.» Turn: «Tell Marin which canapé to keep, and why, kindly.»

1. **02:20, the night run skips him.** The prefetch task reports `candidates: 2, skipped_open_journey: 1, prefetched: 1`. Vincent's journey of the day before was still open, and `journey_latency` does not write tomorrow's page while a journey is open. The walk account's g4.4 was written; his page was not. This corrects the earlier diagnosis, which assumed his page was written at night.
2. **07:51 to 07:54, he opens the app.** A deploy is restarting the services. He finishes yesterday's day at 07:54:34 and asks for the new one at 07:54:53.
3. **07:54:53, the brief.** `director.gap_brief` builds the day's brief. It carries the beat (`today.beat` with before, after, also, hook, turn), the number of days left in the gap (`gap.days_left_after_today`) and the next tentpole's title. It does not carry what days 1 to 4 made true, and no prompt tells the writer to use the countdown or to name Saturday.
4. **The page is written live, by the wrong writer.** The planner, author and aids path on the writer model only runs ahead of time (`story_split.applies`). A page requested live goes to the older one-call `DIRECTOR` prompt, and `story_route()` hands every call, critic included, to the small live model. So the day that mattered was written by the cheapest path the engine has.
5. **07:55:16, attempt 0, refused by a guard.** Two drafts put Marin in `marin_lila_flat` and in `ngo_office`. The first is the canonical place for this beat (Marin's kitchen), and it is not one of the eight built places, so `unknown_character_or_location` refuses it. The beat is pushed to a built room. Which room the served page used is not verified.
6. **07:55:31, attempt 1, refused by a guard.** `objective_too_complex` on «Sag Marin freundlich, welches Häppchen bleiben soll und warum.», which is the plan's own turn in German.
7. **07:55:57, attempt 2, refused by the critic, then served.** The critic (also the small model here) read one draft and refused it: «Make the learner's planned choice create the menu and give one canapé the name the learner supplies. | Show a thread advancing to the day's planned change, not merely setting up the choice. | End on Lila needing the photo for the centre of the wall, grounded in the scene.» The next log line: «the retry the story critic bought failed; serving the refused draft». 62 seconds, about two cents. The critic had named all three faults Vincent reported twenty minutes later.
8. **07:57 to 07:59, three replies.** Vincent asked what «canapé» means. The live `ACTOR` prompt tells the model to answer a learner's question first and to write an honest ending from what actually happened. It receives the page's checklist inside the stored scene, but no rule binds it to `change_after`, and `story.season_turn` carries only `may_set`, `gate`, `must_not`, register and heading. So the model did what it was told. The last panel: «Ah, tu voulais savoir ce que veut dire « canapé ». Pour samedi, je ne choisis pas encore ; je garde mes six idées avec moi.» The planned change was not merely missed, it was denied aloud.
9. **08:09, the day settles.** `runtime._settle_gap` records the premise `les_canapes` as done because «a planned beat is staged once its page is served, taken up or not». The engine now believes there is a menu.
10. **The teaser.** Tomorrow is not a tentpole, so `season_teaser()` returns nothing and `next_teaser()` draws a seeded pick from the open commitments, unpaid plants and season threads, wraps it in the speaker's stock opener and a stock frame, and prints: «Dis, j'y repense… C'est peut-être un signe. Je repense à ce détail. Une carte tombée de la poche de Marin porte l'écriture de Gus.» Marin speaks of «la poche de Marin» in the third person, because the plant row is narration pasted into his mouth. The authored hook (Lila and the photo) was in the checklist and was never read again.
11. **Tomorrow.** Day 6 (`au_milieu_du_mur`) will be briefed as if day 5 had landed. Nothing downstream holds the menu or the name: Saturday's tentpole (`t4.json`) reads three flags and has no menu. Even on a perfect day the learner's canapé name would have gone nowhere.
12. **08:14, Vincent writes the complaint.**

## 5. The hypotheses

### The five causes the mandate marks as confirmed by the code

| # | Claim | Verdict |
|---|---|---|
| 1 | The ending undoes the beat | **Confirmed**, with one correction: the page's checklist does reach the actor inside the stored scene, but nothing binds the ending to it, and two explicit rules (answer the question first; honest ending, no invented success) pull the other way. |
| 2 | The hook is not the plan's | **Confirmed.** 0 of 9 walked gap days showed the planned hook. |
| 3 | The writer never sees the week's line | **Mostly confirmed.** Correction: the brief already carries `gap.days_left_after_today` and the next tentpole's title (`director.py:630`). No prompt uses either, and no surface shows them. What is truly missing is the record of what this gap has made true so far. |
| 4 | Nothing checks the page against the plan | **Half right, and the truth is worse.** The critic does check it (its prompt says the page plus the planned exchange must reach the beat's `after`), it does catch it, and the override serves the page anyway. There is no check at all on the ending the live model writes. |
| 5 | New places are allowed, never wanted | **Confirmed**, with three corrections in H6 below. |

### The seven hypotheses to verify

**H1. The plan is advice, not a contract. Holds.** `before`, `after`, `turn` and `hook` travel as English prose through up to four models. `PagePlan.change` and `PagePlan.hook` are free text; `plan_issue` checks cast, place, premise id, task length and repetition, never the change or the hook. "Done" means "a page with this premise id was served" (`runtime._settle_gap`).

**H2. The critic's override publishes failures. Holds strongly.** 8 of 10 days (section 3.1). The critic is reachable and accurate; the loop around it is what fails: a shared attempt budget, a full redraw instead of a repair, and an override at the end.

**H3. The live model owns the ending. Holds.** See step 8 of the trace. There is also no check after the fact: the resolution is not read against the plan by anything.

**H4. There is no story ledger. Holds in a specific way.** There is not too little state, there is too much of it in too many places. About nine partial records live in `thread.state["living_story"]` (events, commitments, consequences, plants, teasers, `memory` with said/facts/open, the chronicle, the season state with flags and premises, world marks) plus a per-scene ledger. None of them records *what this gap has made true, day by day*, and each lane reads its own subset. The evidence in the logs is the critic catching the engine contradicting itself: the ticket date replaced on g3.1, the learner's «C'est ne pas dur !» callback demanded and not staged on g3.2 and g3.3.

**H5. The arc is invisible to the learner. Holds.** No surface names the destination or counts down to it: not the page, not the Done screen, not the Home card (`story_headline.py` shows the edition number, a title and the teaser). On 10 November the word «samedi» appeared once, in the line that cancelled the beat.

**H6. World and story are two pipelines. Holds, less starkly than the mandate's map says.**

- The forge does read the learners' frontier (`GET /api/v1/story-engine/season-frontier`), but only at the level of a whole gap, and it reads tentpole pages and each gap's bridge page only. The 45 planned beats carry no place at all, so the forge cannot know that Wednesday needs Marin's kitchen.
- The roof was built on 9 November. Vincent's roof page (g3.3) was written on 8 November at 02:21. One place a night, ordered by segment, will always arrive a day late for the learner at the front.
- Generated days can already be played in the quarter: any page whose place is built «plays its lines where it is» (`journey-story.ts`, `todayOf`). But the door to the quarter exists only in the owner build (`NEXT_PUBLIC_QUARTIER_VISIBLE`), only two authored days have blocking (`STAGED_DAYS`), and the default day is the 2D page. So "the 3D world does not play gap days at all" is true for learners and false for the code.
- 8 of the season's 23 places are built. The guard that restricts pages to built places (`on_built_stage`) is what moved the canapés out of Marin's kitchen (trace, step 5). The guard is doing what the owner's rule of 8 November asks, «Erst erwähnen, dann betreten»: a page may name an unbuilt place, never be set in it. The rule is sound. What is missing is the other half: nothing told the forge a week earlier that Wednesday would need the kitchen, and the plan offers no canon-safe second place, so the writer guesses.

**H7. Fallbacks and dropped beats replace planned days with filler. Not confirmed, and a different substitution found.** The logs of seven nights show no authored fallback *page* and no dropped beat; the `missed` list is in the database and is not verified. One authored fallback *turn* was logged (4 November, after a fabricated quote). What the logs do show is the substitution in the trace: when the night run is skipped, the day is written live by the one-call prompt on the small model. That is the real "quiet stand-in", and it hits exactly the learner who plays every day and finishes late.

## 6. What this means for the design

1. **"Done" has to mean "true in the story".** The beat is recorded when its change is on the page and in the ending, not when a page was served.
2. **The ending cannot be left to a model that has just been told to be honest about a conversation that went elsewhere.** Either the ending is bound, or it is written before the conversation and the conversation picks how it lands.
3. **The critic is not the problem; the loop is.** Repair the fault that was named, do not redraw the page, and never serve a page that failed the plan.
4. **The plan needs the fields the engine keeps tripping over:** a place, a one-ask turn per level, a hook that is a line and not a note, the fact that becomes true, and where the learner's mark comes back.
5. **The hook, the destination and the countdown are authored content.** They should be shown, by code, the same way everywhere.
6. **Marks need somewhere to go.** A name the learner gives a canapé is worth nothing if Saturday has no menu.
7. **The world has to hear the plan a week ahead, at day level.**
8. **The learner who finishes late must not get the cheap path.** Pages have to be writable before yesterday is played, which only works when yesterday's outcome is guaranteed by contract.

The design document takes these eight in order.
