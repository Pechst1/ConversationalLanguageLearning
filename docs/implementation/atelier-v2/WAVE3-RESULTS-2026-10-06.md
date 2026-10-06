# Wave 3: results (2026-10-06)

**Branch.** `exp/wave3-integration`, local and not pushed, built on Wave 2 (`dab9d98`). It holds, in order:
- WP-124b: recovery that cannot stall the season;
- WP-132B: the season's ending, with its hooks;
- the three owner-approved proposals, applied on 2026-10-05 (`2a78e57`):
  - the 4 bridges;
  - the epilogue week «La semaine d'après»;
  - the 22 WP-125B letters;
- WP-133b: the capped live read (see [WP-133b-RESULTS.md](WP-133b-RESULTS.md)).

## Checks (`2a78e57`, before the two fixes below)

| Check | Result |
|---|---|
| Life walk | 15 of 15 lives |
| Learner walk `-m walk` | 5 of 5 |
| Full suite | 6,465 passed, 15 failed |
| Forced total outage (`WALK_FAIL_RATE=1`) | 2 of 3 lives pass |

**The full suite's 15 failures:**
- 10 are the baseline.
- 4 depend on test order and pass alone.
- 1 was real and is fixed (`e35a48e`): the bridges' French task lines said «tu» where the chrome says «vous».

**The forced-outage failure.** The A1 life fails on three content findings in pages that 30-day lives had never reached:
- «adieu» on T5 B is above A1.1 and is used for practice. This is an owner call.
- The walk check misread «Odiles». Fixed in `e35a48e`.
- The `setup_native` of T8 B falls back to French. A translation is needed.

## Found and fixed during integration
- **Letter reach.** With the model available, a letter's subject was drawn from the whole catalogue. An A1 learner could then be dealt a B1 letter, and its authored text was printed whenever the draft was refused twice. The reach filter now always applies, with a regression test.
- **The paid-read harness.** It crashed on a bridge page after the paid calls, losing the results and the spend total. Fixed in `c108b76`.

## Before and after (15 lives × 30 days, Wave 2 → Wave 3)
- **Letters.** C1 learners get letters again: 0.7–1.1 min a day, against 0.1.
- **Everything else is unchanged within noise:** season reach, rules, new words, minutes and units held. The bridges and the epilogue act only after repeated losses or after T8.
- **Total outage, with the bridges:** lives reach T8 on day 27. Without them, a life re-reads T1 B indefinitely.

## Live read (WP-133b, US$1.63)
- **Losses:** 19 of 42 generated days were lost. Days 1–10 lost 29 %; the seeded later runs lost 67 %, possibly partly an artefact of `jump_to_day`.
- **Recovery:** all 19 losses recovered honestly: 11 re-reads, 3 bridges and 5 jumps.
- **Four blocking prose findings** stand in the way of a cohort:
  1. Lila present after she has left.
  2. The A1 rule-card example woven in verbatim.
  3. Gender agreement in the reaction and resolution lanes.
  4. Reply lanes that echo the learner.
- **Recommendation:** no cohort until those are fixed and re-read.

## Open for the owner
1. **The «adieu» line on T5 B.** Change the A1 line, or stop practice items from using words above the learner's band.
2. **The German setup of T8 B.** A one-line translation is to be drafted.
3. **The four WP-133b findings.** Fixing them is engineering work; the A1 rule-card example is the owner's.
4. **Older decisions still open:**
   - optional A1/A2 reply exchanges;
   - B1 rule days;
   - the copied rule-card example in a story reply;
   - the WP-134A wording;
   - the test-out and «tenue».
5. **Push and PRs** for the three wave branches.
6. **WP-134B**, the external calibration study, is a separate research track; nothing has started.
