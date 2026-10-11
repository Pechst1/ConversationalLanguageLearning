# Ideas — 2026-09-29: big product leaps

Brainstorm from the 2026-09-29 session, first framed as "what a frontier model
would enable". Owner's note: several may be achievable **without expensive
models** — the design matters more than the model. For each idea the cheap route
is noted beside the frontier one. None of this is scheduled; WP-88..102
(WORK-PACKAGES-2026-09-28.md) come first.

The pattern that makes any of it affordable: **a big model thinks rarely or
offline; a small model talks live.** Today's live path costs about US$0.004 per
request on mini models.

| # | Idea | What changes for the learner | Cheap route | Frontier route | First test |
|---|---|---|---|---|---|
| 1 | **Showrunner, not guards** | A story that plans a week or chapter per learner; fewer repeats, no drift | Weekly plan written by the current director with the full chronicle digest; guards stay | One long-context call plans the week from the whole chronicle; most drift guards retire | A/B the director on `scripts/review_living_story.py` (14 days, A2 + B1): acceptance, fallbacks, blind read |
| 2 | **Writers' room** | Authored-quality seasons, letters, rule cards, first days (incl. the day-1 line translations) | Draft with the current models + the existing critic + owner spot-check | Agent team with continuity checks against the world bible | Draft season 3 (WP-98) and the D-4 v2 review verdicts; owner rates a sample |
| 3 | **The teacher who knows you** | A weekly diagnosis («you avoid *être* in the passé composé»), sent as a character's letter; next week planned around it | Deterministic report from `concept_evidence` + errata + avoidance counts, phrased by a small model | One weekly call over the whole evidence trail | Generate for 3 harness learners; compare with what a teacher would say |
| 4 | **An examiner you can trust** | Placement and the épreuve (WP-94) graded like DELF, citing the learner's own words | Rubric + evidence quotes with the current grader, calibrated on human-rated samples | Holistic grading of writing and speech | 30 human-rated samples; agreement rate |
| 5 | **Synthetic learners** | (Indirect) every package measured on learning and boredom before real learners see it | Scripted personas with error profiles driving the real API on mini models | Agents that play plausible learners for 60–126 days | One German-A1 persona, 30 days, through backend-e2e |
| 6 | **Your life is the story** | Photograph a landlord's letter or a menu; Margaux helps, tomorrow's scene rehearses the call | Existing intake («Bring your own French») + a story hook in the director | Strong vision reading handwriting and forms | Three real documents through intake → scene |
| 7 | **Nightly QA walker** | (Indirect) regressions like the greeting-nudge bug caught before the owner sees them | Playwright script over backend-e2e with the fake provider; screenshot diff | Agent that walks and judges against the design contract | See the engineering ideas below (E-3) |

Recommendation at the time: #1's A/B first (it tells whether a leap is real for
this story), then #2 and #3 on the same provider work, with #5 as the measure.
#6 is the most distinctive product bet.
