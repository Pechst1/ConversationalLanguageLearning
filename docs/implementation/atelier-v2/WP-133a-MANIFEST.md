# WP-133a — run manifest (2026-10-04)

**Approval.** The owner approved this run on 2026-10-04, with a cap of US$3 in all. No media generation was included.

**Code.** Commit `cab1fb5`, plus the wrapper `tests/test_wp133a_live_read.py`. The wrapper changes no product code.

**Configuration.** As in production:
- the real model for the director, critic and reply lanes, with two drafts;
- the grammar catalogue at v2;
- the practice day on, so `grammar_plan.introduce` is set;
- correction LLM, panel art and episode audio off.

**Matrix.** Each band is a fresh learner reading 10 consecutive days from season day 1. At A1.1, B1.1 and C1.1 that is 3 tentpole days and 7 generated days per band, so **21 generated days in all**.

**Cap and stop conditions.**
- Each band is capped at US$1.00, enforced across every `LLMService.generate_chat_completion` call, retries included (`_live_model`).
- The bands run in sequence.
- When a cap is reached the band stops, and the report says it is incomplete. Nothing is retried beyond the cap.
- The previous read cost US$0.32 for 10 days at A2.

**Recorded per band.**
- The transcript (`SEASON_REPORT`).
- Lost days, with the guard reason taken from the fallback log.
- For each draft: the unit to introduce, how often the cast says it, whether the question invites it, and compliance (`grammar_weave_gap is None`).
- The cost and the number of calls.

**Rubric for the prose read.**
- Continuity with the season: no strangers, «tu» kept.
- The premise is not repeated.
- No teacher-like character voice.
- The day's events move the story forward.
- The level fits.
- Reactions to the learner's answers are natural.
