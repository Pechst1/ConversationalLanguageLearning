# WP-127 — the vocabulary check's pass rule (a candidate)

**Status:** candidate policy `band-check-v2-topdown-21of24`, shipped with the basic
top-down check. To be validated in the learner pilot (WP-133b) before it is
tightened, loosened or treated as settled.

## The rule

A check shows 24 core words of one sub-band, each a four-way meaning choice plus
«je ne sais pas». **21 of 24 correct (87.5 %) passes** (`band_check.PASS_CORRECT`).
Before WP-127 it was 90 %, i.e. 22 of 24.

A pass credits the band: the sampled words answered right as *sampled
recognition* (`provenance = band_check`), the band's other words and every lower
sub-band as *inferred* (`provenance = band_check_inferred`). Neither is a claim
of productive use or of CEFR competence. Words with any card already, words missed
in any check and lower sub-bands that were missed are never credited. Every credit
keeps the light-check schedule (`credit_schedule`), so a word the learner does not
know comes back into the ordinary supply.

## The trade-off

Under a simple model where each item is an independent trial with the learner's
per-item accuracy *p* (package doc §2 "Limits"):

| Learner's true accuracy | Outcome | 22 / 24 (old) | 21 / 24 (candidate) |
|---|---|---|---|
| 92 % — knows the band | **false fail** (P[X ≤ threshold − 1]) | ≈ 30.1 % | ≈ 12.1 % |
| 80 % — does not know it well enough | **false pass** (P[X ≥ threshold]) | ≈ 11.5 % | ≈ 26.4 % |

`tests/test_wp127_top_down_check.py::test_the_threshold_is_a_documented_candidate`
recomputes these four numbers.

These are mathematical illustrations, not calibrated estimates. Items are not
independent (shared distractors, cognates, frequency), recognition overstates
recall, and a guessing learner gets 25 % of a four-way choice free.

## Why 21 / 24 for now

The old rule failed a learner who knows a band about one time in three, and the
top-down ladder makes a false fail expensive: it sends the learner down a band and
spends half the visit. A false pass is cheaper here than it looks, because

* a missed word is never credited, even on a pass;
* inferred words are marked as inferred and come back for a light check
  (20–365 days, by distance below the learner's band), where a miss returns the
  word to the ordinary supply;
* inference never overwrites a card or a recorded weakness.

So the candidate accepts more false passes (≈ 26 % at 80 % accuracy) to halve false
fails, and relies on the light checks to recover them.

## What the pilot measures (WP-133b)

Each graded attempt writes one `band_check_attempt` row to the pilot ledger
(`pilot_events`, `entity_id` = the attempt's persistent id) with:

* `policy_version` — `band-check-v2-topdown-21of24`;
* `sub_band`, `attempt` (number at that sub-band), `sampled` (the 24 lemmas),
  `missed`, `dont_know`, `correct`, `total`, `pass_correct`, `passed`;
* `credited_sampled`, `credited_inferred`, `inferred_bands`.

The pilot can then compare, per policy version: the light-check miss rate of
inferred versus sampled words, by distance below the learner's band (a high miss
rate on inferred words means false passes); how often a learner fails a band and
passes the one below (a false fail costs a visit); and visits per learner.
Tighten to 22 / 24 if inferred words fail their light checks far more often than
sampled ones; loosen only with evidence that false fails dominate.

## Bounds that are not candidates

* The ladder starts at the highest eligible sub-band below the learner's own; a
  pass stops it, a miss steps down one sub-band.
* A visit is at most two checks — 48 items — within 12 hours; the ladder pauses
  and resumes at the next visit.
* The sample is keyed by learner, sub-band and attempt number, never by the day:
  reload, midnight and a retried submit see the same answer key, and a replayed
  submit returns the stored result without crediting twice.
