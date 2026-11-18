# Overnight run · 17–18 Nov 2026

Twenty-four draft pull requests against the pilot plan (`README.md` in this folder). Implemented by Opus 5.5 at medium effort, each in its own worktree, guards first. Nothing is merged. Nothing from the overnight run has been played on real model output; the day-1 packages were (see the review's `logs/check*.md`).

## Pull requests, in a landing order that avoids conflicts

| Order | PR | Package | CI | Left unverified / to know |
|---|---|---|---|---|
| 1 | 892 | CI: PostgreSQL restore check (runner image changed) | its own run is the proof | Production's PostgreSQL major is not pinned; run `SELECT version();` |
| 2 | 898 | La Forge dead end on build/dictation cards (product bug on main) + season walk waits out the rate limit | — | A local 4-day walk did not hit the stall, so it neither confirms nor refutes the fix |
| 3 | 869 | P2 declared level never lowered automatically | green | The 40-answer path was not reached in real play |
| 4 | 870 | P1 stored fault never stamps a correct reply | green | The «you made this before» note did not fire once in ten real days |
| 5 | 874 → 887 | Night run lands a page → first draft can pass | PostgreSQL only / + walk stall | 874 confirmed in real play (4 of 5 nights). 887 unproven: baseline 3 attempts every night, US$0.31–0.37 |
| 6 | 873 | P8 one hook line, hook as the day's subject, «Précédemment», Home title | PostgreSQL only | Real play: one line everywhere; hook taken up early on 1–3 of 4 days |
| 7 | 871 | P0 switches (Sonnet, Revue off, gold UI off, Courrier timeout 15 s) | PostgreSQL only | **Changes production on merge.** Carries commit `e92c0e79`, which changes what the gold gate watches — owner decision |
| 8 | 872 → 886 | P0 Courrier never answers with the help-desk line → second-draft hint | gold gate (courrier) | 872 confirmed in real play (13 of 14 real replies). 886 not played |
| 9 | 875 → 882 → 889 | P5 no solution before the retry → P6 drill = own mistakes → P11 waiting, failing, day state | PostgreSQL only / + walk stall | Decision 8 means no drill around the scene on most days (105 of 126 simulated) |
| 10 | 878 | P6 a learned rule leaves; La Forge capped at 8 | PostgreSQL only | — |
| 11 | 877 | P7 word deck (Normal = 15, kept words first, all scene words, 20 reviews after absence, offer removed) | PostgreSQL only | Looked-up words are not tracked, so not prioritised |
| 12 | 876 | P9 stage 1 Home: Journal chip, level check after day 8, onboarding, «Revoir» | PostgreSQL only | Overlaps 889 (take 889's skip) and 880 (same chip change) |
| 13 | 885 | P9 stage 2 listening day after day 8, return card lines, push | walk stall + rate limit | No hook is stored with a translation yet, so every push below B1 is the authored line |
| 14 | 879 | P3 scene corrects the day's rule; up to three corrections from B1 | gold gate (scene) | Not played. Conflicts with 875 in one schema (both fields stay) |
| 15 | 880 | P10 strings in the right language | gold gate (forge) + a timing test re-run | English meaning on build cards for B1 German learners kept (owner rule of 16 Oct) |
| 16 | 884 | P4 the walk's wrong corrections as test cases | PostgreSQL only | Two cases documented as expected failures (pronoun antecedent; repair accepts one fix) |
| 17 | 891 | P6 stage 3 six B1 template units | PostgreSQL only | **No one has read the French.** Also changes the 7-day variety window for every unit |
| 18 | 881 → 888 | P12 Quartier: door open, Home's second action, readable for beginners → free talk corrected, notebook, place check | walk stall + rate limit | Nothing seen in a browser or on a phone. The stairwell is marked unfinished, so T1 b, T2, and days in T4–T6 fall back to pages |
| — | 890 | Integration: all of the above in one branch (never merged) | gold gate | For CI on the combination and one build for the phone walk |

Stacked PRs are written «lower → upper».

## Decisions built on the owner's behalf (each stated at the top of its PR)

- **2** one correction per reply at A1–A2, up to three from B1 (879).
- **3** B1 learners join once the week-one templates exist (891).
- **4, 5** Le Papier, La Radio, Le Correcteur off; gold counter hidden (871).
- **7** no listening day before day 8 (885).
- **8** the drill around the scene keeps only own mistakes and one due rule (882).
- **9** the Quartier is a choice beside the page, not the default (881).
- Settled by the owner: 15 new words on «Normal» (877), Sonnet as writer (871), the Quartier on (881).

## Owner's steps

1. **`e92c0e79` on PR 871.** An agent changed the gold-transcript gate so it ignores timeouts and retry settings, and re-recorded its fingerprints without a paid run. Keep it (it also clears 872 and 886) or revert it and pay for the courrier gate.
2. **Gold gate.** On the combined tree the scene, forge and courrier sets are stale: `python scripts/gold_transcripts.py gate --max-usd 1.5` per surface, then commit `gate.json`. Until then shard 1 of the backend suite does not run on 872, 879, 880, 886, 890.
3. **Render:** the legal contact build variable; check that no dashboard value overrides the keys 871 changes; production's PostgreSQL version.
4. **Read the French** of the six B1 units (891).
5. **A phone:** the Quartier (load, frame rate, heat, the second action on Home), and Home without an invented title.

## Real-model checks worth running (need a go-ahead; session spend stands at US$14.64 of 15)

| Check | Why | About |
|---|---|---|
| Integration branch, A1-de and B1-en, days 1–6, pages | The handover's «walk a full day» on what would ship | US$3 |
| Night run with 887 | Does the first draft pass now (baseline: never) | included above |
| The Quartier on the integration branch, day 1 and a later day | Free talk correction, notebook, Home's second action | under US$0.50 |
| Corrections at B1 with 879 | Is the day's rule now corrected first; do three corrections read well | included above |

## What the night showed about the product, beyond the plan

- **Most nights the writer's page was being thrown away** (task line one word over a limit); with 874 the page lands, but every night still spends all three attempts. 887 targets that.
- **A La Forge dead end exists on main** (898): after a top-up, a card can be graded against sentences the learner never saw. A real learner is stuck there.
- **The «Relecture» day can happen to a real learner** (a generated weekend day fails and the previous big scene is re-read), not only after a test jump.
- **CI on main was already red** (the walk), which is why per-PR walk failures say little until 898 lands.

## Real-model walk of the integration branch (18 Nov, US$2.87)

A1-de and B1-en, six days each, Sonnet as writer; day 1 at A1 played in the Quartier. Logs: `docs/ops/walks/2026-11-17-experience-review/logs/walk-integration-a1.md` and `-b1.md`.

**Held:** level stays B1.1 past 40 answers (869); no wrong correction in twelve learner-days (870, 884); the day's rule corrected first (879); every night run landed, «start» to first screen 1–3 s (874); kept word opens the next deck at B1, banner and offer gone (877); «skip to the scene» (889); Courrier never the help-desk line (872); switches (871); no listening day (885); played scene counts on Home and in the archive, one «Nº» (889, 881); German line by default in the Quartier (881).

**Did not hold or new:**
- **Home never offered «play in the Quartier»** on any day at either level; only the chip (881).
- **La Forge cards that cannot be solved** (B1 days 2 and 5: grammatical answers refused for an intent the card does not state, no solution; A1: «J'ai trente ans» against a five-word minimum).
- **Repetition remains:** the same rule three times on A1 day 1 and 2; a mastered rule back on days 5–6; «Oui, je lui les montre avant midi» on four days; vocatives still in build items.
- **Hook take-up (873):** per-page log — early 1, late 1, not at all 5 of 7 generated days; one page again stated the learner's decision.
- **First draft at night (887):** still 2–3 attempts every night; refusals now come from the critic and `story_word_printed`.
- **Scene-end wait** of 15–30 s with no button on days 3–6 (A1); B1 5–32 s with a way on.
- **Courrier** reopens one thread all week; at A1 one reply came 13 minutes late after a holding line.
- **Journal chip** disappears once the day is finished; «Behalten» was not offered in the word-help sheet at A1; the replay's «Weiter» is hidden by the tab bar.
- **Corrections** still miss about half the errors at B1 (collapsed extra corrections could not be opened by the harness); the learner's gender is ignored («arrivé»); Courrier notes in English.
- **Deck** grows to 26–27 cards by day 6; 1–5 scene words a day.
- **Day length** still 25–30 minutes against 13–16 quoted.

## Second round (18 Nov, after the walk) — not yet played on real models

| PR | What | Stacked on |
|---|---|---|
| 873 (4th commit) | The hook is derived from tomorrow's planned beat; a learner's «demain …» plan enters tomorrow's brief like a tapped pick; undecided choices reach the writer as open; every hook records its source | main |
| 908 | La Forge: free cards judged only on what they state, a model answer after refusals, minimum length never above the model answer, no vocative in any item format, a first miss says what is wrong | main |
| 907 | Quartier: the Home button (the day's offer carried no place; the headline now says where a planned day plays), hint start of three words, end card only from understood replies, notebook choices from page days, camera off walls, map markers | 888 |
| 909 | A rule taught once a day; a passed exam retires the rule; «Continuer» after 8 s; reader inset; keeping a word by its dictionary form; Home's minutes from measured pace | 889 |
| 910 | The Journal chip on a finished day | 876 |

Integration branch `claude/pilot-integration` at `9afe590b` holds both rounds: 1,596 server tests and 1,441 client tests pass; «Normal» is 15 words everywhere and a new learner's Home quotes 20 minutes. Gold gate: scene and forge stale (unchanged by round 2), courrier and correction current. CI on the five PRs: only the known PostgreSQL failure; browser walks pending.

Owner calls built in round 2: no vocative in any item format (908); a refused free card shows a model answer and ends (908); content a card never stated is not judged (908); hooks are now statements or titles, not questions (873); a day's rule is practised only in La Forge (909).

Known limits found: free talk in the Quartier exists only on days with a scripted conversation; generated days give the notebook nothing; the gold gate does not see prompt changes on retries or in the planner.

## Second real-model walk (18 Nov, integration at `9afe590b`, US$2.91)

A1-de (day 1 in the Quartier) and B1-en, six days each. Logs: `logs/walk2-integration-a1.md`, `-b1.md`.

**Confirmed fixed:** the Quartier button on Home (day 1); hints give a start, never the sentence; talk opens and corrects; notebook holds page-day choices; one rule a day (card + La Forge only); a passed exam retires the rule; no vocatives in built or judged items; free cards accept own content, a twice-refused card ends with a model answer; scene end card within 1–3 s; the hook is one line everywhere and a learner's «Demain, je veux parler à Gus» became the hook and day 4 opened with Gus; hook taken up early on 6 of 8 generated days (app's own log; 1 of 7 before); kept word opens the next deck; Journal chip on a finished day; level stays B1.1.

**Still wrong, by weight:**
1. Scene corrections are unreliable at B1: one day with no correction at all (three plus-que-parfait errors on its own day), a wrong correction («je lui dirai» → «je lui ai dit»), about half the errors missed, collapsed corrections cannot be opened, gender misses on day 1.
2. The app states things the learner did not do: the Quartier end card and notebook («Tu as dit que tu viens pour vendre»); «tu pars mercredi» / the flight moved to 2 Dec before the learner chose.
3. Home's minutes are now far too low (deck «1 min» for 15–30 cards; grammar 2 min for about 9).
4. Hooks from the beat are sometimes unreadable: «Le billet», «Romy enquête», «La même chose ?».
5. The drill around the scene serves garbled items built from earlier edit states; typed drill items show the solution at once.
6. Night runs at A1: four of six ended «unavailable» (two with a provider failure during a network outage on the test machine, two on the task-length rule plus the critic); B1: all landed. Still 2–3 attempts every night.
7. The Quartier is offered on day 1 only.
8. Deck: 30 cards on day 6; near-synonym runs; 1–4 scene words a day.
9. Courrier: no new letter after day 1; replies drift off-story; explanations in English; one silent turn at B1.
10. La Forge: a correct answer refused («Elles sont à la pharmacie»); repeats across days; an exam failed on a lost edit; hints that leak the answer.

## Third round (18 Nov, after the second walk) — not yet played on real models

Further commits on existing PRs; integration branch at `361eed01` (3,129 server tests pass, 1,549 client tests pass).

| PR | What |
|---|---|
| 879 | Two guards that dropped valid subjunctive corrections fixed (a subjunctive ending read as a gender change; a rule note rejected as an invented quote); a tense or mood change needs evidence in the learner's sentence; «1 autre correction» is a button; the Courrier's corrector gets the day's rules |
| 873 (5th commit) | Season facts stated as facts, an open choice asked for in the scene, endings may not turn a hedge into a decision; beat hooks are whole readable lines, never naming an unmet person, with a mother-tongue version where the data has one |
| 907 | The Quartier's end card and notebook say «Tu as dit…» only for a tapped card; Home offers the Quartier on days whose scene was written overnight; resume mid-scene; measured map labels |
| 909 | Measured pace needs 20 items over two days, median, clamped; 13 of 21 stored La Forge faults at B1 were editing artefacts and are now refused; a missed last drill item comes back once; reviews capped at the new-word count |

**Open for the owner**
- **Contradiction on the combined tree:** PR 877 allows 20 reviews on a return after an absence; PR 909 caps every day's reviews at the new-word count (15 at «Normal»). One test is left failing on purpose until one rule is chosen.
- **Explanation language at B1:** the Courrier explains in the mother tongue (the app's rule), the scene in French. One of them should change.
- **The ticket moves to 2 December when the learner gives no date** (owner decisions of 16 and 24 Oct) — the last place the story acts for the learner.
- **The review cap builds a backlog** after week 8 (the app's simulation expects about 43 reviews a day).
- **Gold gate:** scene, forge and correction sets are stale; courrier is current.
