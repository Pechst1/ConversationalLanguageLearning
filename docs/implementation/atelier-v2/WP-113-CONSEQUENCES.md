# WP-113 · Conséquences: choices that change events

*Started 2026-10-02. The spec is in `WORK-PACKAGES-2026-09-30-feuilleton.md` §3.5 and §4. The story is `docs/story/season-1/` (owner-approved); nothing here changes a plot point.*

## 1. What the audit found

The season already carries consequences in its data:
- 50 world flags (bible §6);
- tentpole variants conditioned on them;
- three endings (`s1.ending`).

But **every decisive choice of the season is a solve, and no solve was posed**:
- the letter (T1 B);
- the key (T2 B);
- the photo (T4 B);
- the evidence (T6 B);
- the flat (T7 B);
- the persuasions (T7 A).

The engine took each solve's default, so every learner read the same story and reached the same ending («Laisser partir»). Two endings were unreachable: «Garder» needs Margaux persuaded and «Partager» needs Gus persuaded, both in T7 A's «Convaincre».

## 2. Slice 1: the choices are asked (2026-10-02)

- **«Le choix» is a question answered with cards.**
  - Each `choix` solve becomes a turn of the day's conversation.
  - The character's lead-in asks the question, and the solve's options are tap cards (`RespondPrompt.choices`).
  - The instruction line becomes the solve's own task («Choose who reads the notary's letter.»).
  - The tapped card routes exactly, with no model call (`card_choice`). It plays that option's beats and sets its flags.
- **«Convaincre» is a short argument.**
  - The first objection is the question.
  - Each reply either lands (the solve's `lands` beats, `sets_on_land`) or is met by the next objection.
  - After the last objection, or a give-up, it fails (`fails`, `sets_on_fail`).
  - The interlude (Gus's confession) always plays once before the outcome, as the bible's note says.
- **Never cut.**
  - The rhythm planner may shorten a conversation, but never below the day's last posed solve or Lila's gate (`ResponseTask.min_turns`).
  - A «Convaincre» counts one exchange per objection.
- **Settled.**
  - A choice or argument the learner made is settled with the day's turns.
  - Only the solves still unposed (enquête, déchiffrer, the S-9 balloon; that is WP-112) keep their default.
- **Done-when test:** `test_opposite_choices_read_different_episodes_and_reach_different_endings`.
  - Two learners tap opposite cards at the first tentpole and after it: the keeper trusts Margaux, keeps the evidence for Marchand and persuades Margaux; the sharer trusts Gus, makes the evidence public and persuades Gus.
  - They read different tentpole pages from T4 B on, and reach «Garder» and «Partager».
- **Walk:**
  - the season learner taps the letter card on T1 B (`season-choice-asked-as-cards`);
  - screenshot `d2-19-respond-choice`.

**Files:**
- `app/services/season/page.py`: `posed_choice`, `posed_as_turn`, `convince_as_turn`, `convince_outcome`, `choice_cards`, `exchanges_for`;
- `app/services/season/runtime.py`: projection, settling, `card_choice`, `min_turns`, next choices and task;
- `journey_contracts.py`, `journey_planner.py`, `daily_journey.py`, `schemas/daily_journey.py` (`RespondChoice`);
- `web-frontend/components/atelier-v2/journey/JourneySteps.tsx`: the cards;
- the walk harness.

## 3. Slice 2: the days in between answer to you (2026-10-02)

1. **Generated days honour the learner's choices.**
   - The story critic has a new rubric item, `honours_choices`: the page must agree with `gap.facts` and the flags (who saw the letter, who kept the key). It now reads the flags (`critic_payload`), and a page that contradicts one is refused (`review_verdict`).
   - A deterministic guard backs it: `price_secret` in `gaps.json` `global_must_not`. Until the price is public (`s1.price_public`, Gus reading the letter out in T1 B), no generated day may say «trois cent dix mille» or «310 000».
2. **A complication card is tomorrow's obstacle.**
   - The director writes the card it drew as `season_checklist.complication`: the obstacle it leaves for tomorrow.
   - Settling keeps it (`state.obstacle`). The next generated day of the same gap reads it as `today.open_obstacle` and must face it. The critic checks this (`obstacle_faced`). A tentpole in between does not carry it into another gap.
3. **The in-between story moves on engagement** (owner OK 2026-10-02).
   - A scheduled moment counts as staged only when the learner took the day up: the turn ended «met» or «partially_met».
   - A «not_yet» day leaves its moment owed, and the next generated day stages it again (the same path as a moment the draft skipped).
   - Tentpoles stay calendar-bound (S-12).
4. **The owner's face decision.** The `toi_face` guard and the season's writing rule no longer say «never shown face-on». The face is the learner's own (WP-118); generated text never describes it. `10-lieux-et-images.md` carries a dated note. Lila's portrait still never gains a face; that payoff is the open WP-118 question.

**Tests:** `tests/test_wp113_consequences.py` (5).

**Files:**
- `app/services/season/director.py`: `SeasonChecklist.complication`, `StoryReview.honours_choices`/`obstacle_faced`, `open_obstacle`, brief, payload, verdict;
- `app/services/season/runtime.py`: `_settle_gap`;
- `app/services/living_story.py`: the director prompt, and the turn outcome passed to settling;
- `app/data/season/s1/gaps.json`, `season.json`.

## 4. Still open in WP-113

- **Dramatic irony:** «Précédemment» and the margin notes recall what the characters forgot (§3.5).
- **Further flag guards:** `price_secret` is the one contradiction a pattern can catch. Others (who holds the key, who saw the photo) are left to the critic's `honours_choices`.

## 5. Left for WP-112

These mechanics still default:
- **L'enquête:** tap the contradicting line or picture.
- **Déchiffrer:** read the document.
- **The S-9 balloon:** Camille's gender, seeded until posed.

Their data is authored like the choices; they need their own on-page interactions.
