# Calibration run — 2026-09-17

Owner-approved bounded paid run of the judgement half of the 2026-09-10 packages.
Script: `scripts/calibrate_new_packages.py` (throwaway database only, call cap 40,
cost cap US$1.00). Reports: `var/reviews/calibration-2026-09-17.json`,
`calibration-2026-09-17-register.json`, `coverage-calibration-2026-09-17.json`,
audio under `var/reviews/calibration-2026-09-17/audio/`.

Spend: 20 + 1 + 12 provider calls. Known cost US$0.04 (the coverage run's own
estimate) plus the placement/intake gradings, which record their cost in the
pilot ledger rather than on the return value — read `pilot_digest` for those.
Order of magnitude: under US$0.15 in total.

## Placement (WP-25) — mechanism works, ladder under-places a strong learner

| Persona | Estimate | Confidence | Turns | Grading latency |
|---|---|---|---|---|
| A1.1 beginner | A1.2 | 0.71 | 4 | 3.5–6.5 s |
| A2 | A2.2 | 0.73 | 5 | 4.0–6.5 s |
| B1 | **A2.2** | 0.71 | 5 | 5.3–7.4 s |

The A1 and A2 personas land where they should. The B1 persona is placed one
band low: its B1.1 answer scored 1/4 because the scripted answers are keyed by
band, not by the prompt's actual question (the persona answered a different
B1 prompt than the one it was asked). So this is a script limitation before it
is a grader finding — but it also shows the ladder's real weakness: **one low
turn at a higher band ends the climb**, and a learner who misreads one prompt
is placed under their level. Recommendation: require two consecutive low turns
above the current estimate before descending, and a follow-up run with
prompt-specific answers.

## Register (WP-33) — detector right on 5/6, model gap now answers

Deterministic verdicts: `tu` to the landlord → slipped; `vous` to a friend →
slipped; both polite forms → respected; «Un café.» to the barmaid →
not evaluated (no address, no marker). The model gap for that case first
**failed on every call**: `MODEL_MAX_TOKENS = 200` starved gpt-5-mini into an
empty response (the known reasoning-model trap). Fixed in the same day
(1,200 tokens, `reasoning_effort="low"`); the rerun answers «respected», which
is defensible for a two-word order at a counter. The fallback path is now live.

## Radio (WP-32) — three lines spoken, nothing judged by a machine

| Line | Voice | Size | Latency |
|---|---|---|---|
| Augustin | alloy | 51 KB | 2.6 s |
| Lila | nova | 62 KB | 2.1 s |
| Narrator | fable | 84 KB | 2.3 s |

The mp3s are in `var/reviews/calibration-2026-09-17/audio/`. **Owner's ear:**
is the French intelligible at A1 speed, and do the three voices read as three
people? Nothing automated can answer that; this run exists so that question has
material.

## Intake (WP-34) — both fixtures read

The landlord letter (text, 2.8 s) became a *reply* task addressed to
M. Marchand in `vous`, «Confirme ta présence avant le 12 septembre»; the café
menu rendered to a PNG (vision path, 6.9 s) became a *decide* task, «Choisis un
plat du menu». Both honest, both bounded. One thing to look at: the task's
instruction addresses the learner in *tu* while the counterpart register is
*vous* — correct in itself (the app speaks to the learner, the learner speaks
to the landlord) but worth checking against the learner's address preference.

## Coverage (WP-29) — not yet observable

`longitudinal_story_review.py --live --level A1 --days 3 --max-requests 12`:
1/3 days accepted. The two failures are pre-existing guards
(`objective_too_complex` day 1, `inclusive_dot_form` day 2), not the coverage
guard, and the report carries no `lexical_coverage` metadata for the accepted
day — the review script's synthetic learner has no vocabulary state, so the
guard has no known-word set to measure against and reports `not_assessed`.
Coverage calibration needs a real learner thread; it is the first thing the
pilot digest will show once the cohort is on.

## Follow-ups

1. Placement: two-low-turns rule before descending; a prompt-specific answer set.
2. Owner: listen to the three mp3s.
3. Coverage: read `coverage_report.py` after the owner's first pilot week.
4. The A1 `objective_too_complex` guard still fires on day one of a fresh run.
