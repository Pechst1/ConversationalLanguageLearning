# S5 · The next season is written by a job, and its rules are checked against its own data

Written 9 Nov 2026 from `origin/main` at `ec60ae44` and the season-end walk (draft PR #649, `docs/ops/walks/2026-11-09-season-end.md`).
Implementation: Opus 5.5, medium effort, own worktree cut from `origin/main`, draft PR, nothing merges without the owner.

## The structural flaw

Three things are wrong with how a season ends, and each produces a family of findings.

1. **The writer runs inside the learner's request.** `settle_resolution` (`app/services/living_story.py:10764`) calls `roll_over_season` (`:4729`), which calls `draft_next_season` (`app/services/season_writer.py:277`) while the user and resolution rows are locked. Measured: 40–66 s from the last answer to the ending, locks held 23–30 s, Home blocked for 27 s, one run 0.67 s under the client's 90 s timeout. The writer can also run inside a polling `GET` (`story_lanes.py:1687`, `:1755`), against that module's own rule.
2. **The writer gets one attempt.** 6 of 14 reviewed drafts were accepted. One refusal costs the learner the written season and two weeks.
3. **The guards and the data they guard are not checked against each other.** Nothing fails when a guard and its data drift apart, so each drift is found by a learner:
   - the critic prompt lacks the word «JSON» while `_json_call` (`living_story.py:1468`) always sends `response_format=json_object`; OpenAI answers 400 on every review;
   - `_SLUG` (`season_writer.py:39`) refuses a hyphen the prompt never forbids;
   - 5 of 8 interlude beats name places that `app/data/season/s1/stages.json` has not allowed since `3e8e19f3`;
   - `_TASK_VOUS` (`living_story.py:6631`) matches the word, so a plural «vous» is refused;
   - the interlude beat is dealt from `chapters_total` (`living_story.py:5429`), which has already moved on, so one beat repeats;
   - `reaction_lines` (`app/services/season/turns.py:549`) drops an authored SMS reply, so the season's biggest choice is answered with «…»;
   - season 1's threads stay `open` in `threads_archive` after the finale, so the reprise reopens a decided question.

The fake provider cannot see any of the first four. That is why green tests hid them.

## Target structure

**A. The ending is released at once; the season is written afterwards.**
- `settle_resolution` closes the season and returns. It makes no model call and holds no lock across one.
- A Celery task (next to `app/tasks/journey_prefetch.py`) writes the next season. It retries until a draft is accepted or a budget is spent (attempts and US$ both capped, each attempt logged with its refusal reason).
- The life has one stored rollover state: `pending`, `written`, `interlude`, `reprise`. Home, the premiere card and the named interlude read that state. No screen infers it.
- No `GET` may reach the writer or the critic. A test asserts it by making the fake provider raise when called from a read path.
- If the task has not finished by the next morning, the learner gets the named interlude with a date the task is bound to: the retry fires on that date whether or not a chapter closes.

**B. One contract test per guard, run against the shipped data.**
A guard that refuses model output must be proven satisfiable by the data and the prompt that feed it. Add `tests/test_season_contracts.py`:
- every place named by an interlude beat, an arc or a closing hook is in `stages.json`, or is marked «to be built» and the page is not set there;
- every prompt whose call uses `response_format=json_object` contains the word «JSON» (scan all `_json_call` callers, not only the critic);
- every identifier pattern (`_SLUG` in `season_writer.py` and `season/agency.py`) is stated in the prompt that produces the identifier, and the writer normalises `-` to `_` before validating;
- `task_says_vous` is decided by addressee (a task that addresses the learner in the formal singular), with the three walk sentences as accepted cases;
- every authored reply in the season data survives `reaction_lines` for its own turn (SMS included);
- after a finale, no thread the ending decided is `open`.

**C. A real-provider smoke for the paths the fake cannot see.**
One small nightly job with a hard spend cap (US$0.25) sends each structured prompt (writer, critic, turn, correction) once to the configured provider and asserts a parsed answer. It reuses the season-end harness (`scripts/season_end_walk_server.py`). It does not score quality; it only proves the call shape is accepted.

## Stages (each its own PR)

1. Contract tests of part B, with the data and guard fixes they force. This unblocks written seasons on the `render.yaml` values and is the smallest change.
2. Rollover state on the life, plus `settle_resolution` without the writer; the interlude date bound to the retry.
3. The writer task with retries and caps; read paths proven model-free.
4. The provider smoke job in `.github/workflows/`.

## Done when

- `tests/test_season_contracts.py` fails on `ec60ae44` for each of the seven drifts above and passes after stage 1.
- A test drives a finale with a writer delayed 60 s: `POST /advance` returns in under 2 s and `GET /today` is not blocked.
- The season-end harness, rerun with the real model and no harness interventions (`critic_json_word` off, no `install_written`), reaches a written season on at least one of two lives.
- The interlude's promised date and the first season 2 day are the same day in that rerun.

## Not in this package

- The quality of generated days after the rollover (endings lost to `reply_repeats_thread`, instructions spoken by characters). Those belong to the story-truth stack (#635–#653).
- Building Rue de Lancry. The contract test only forbids promising a place no page can enter.

## Owner decisions needed

1. Attempt and spend cap for one rollover (proposal: 4 attempts, US$0.05).
2. Whether the smoke job may spend on production keys nightly (proposal: yes, capped at US$0.25).
