# Work packages, 11 October 2026: variety in the story, the pictures and the news

Inputs:
- Three read-only assessments made on 11 October: the story arcs, the image-model art and the news feature.
- `WORK-PACKAGES-2026-10-06-next.md` (the Papier packages WP-138 to WP-142) and `WORK-PACKAGES-2026-10-08-next.md` (WP-150 to WP-163).
- The code on `origin/land/followup-2026-10-08` at 9ee9305, the newest landed stack. `main` was not checked.

New numbers start at WP-164.

## 0. What the assessment found, corrected against the newest code

| Area | Creativity | Versatility | What a learner sees today |
|---|---|---|---|
| Story arcs | 3.5 / 5 | 2 / 5 | One world (a Paris café dramedy), one cast, mostly two rooms. |
| Image-model art | 3 / 5 | 1.5 / 5 | Fixed location plates with the drawn cast on them. No generated picture is shown. |
| News | 3 / 5 | 2 / 5 | Nothing. The Revue is off, and the season engine takes no news. |

**Two findings of the first pass were stale. They are not packages here.**
- **Story-day loss.** The 29–64 % figure is from `LOSS-RATE-2026-10-06.md`. WP-136 then lost 0 of 19 generated days on merit, and WP-149 lost 1 of 12. Loss at A2, B2 and C1 is WP-161.
- **Repeated fallback letters.** «Plus de pain blanc» six times in a month was fixed by WP-125B: band reach, plus no canned reprint within `CANNED_REUSE_DAYS` (`app/services/missions.py:70-90`).

**Three facts checked on 9ee9305 that change the image plan.**
1. **The drawn art set never shows a generated panel.** `artSet` is `"drawn"` (`web-frontend/launch-flags.json`, WP-157). The readers draw the location plate with the SVG cast on it: `FeuilletonReader.tsx:934-937` («a painted drawing (people included) is not shown») and `VerticalPanel.tsx:151-152`. Setting up S3 storage would switch `panel_art` on, but in the default art set nobody would see what it paid for.
2. **12 of the 22 season places borrow another place's plate** (`app/services/season/world.py:20-60`, `"own": False`):
   - Odile's flat (65 uses in the season files, the second most used place) and the stairwell show the learner's own studio.
   - The quai de Valmy, an outdoor place (31 uses), shows the café counter.
   - The mairie, the gérance Marchand and the notaire share one office plate.
   - The gare de l'Est shows a metro platform; the roof of the building shows a park.
   - The rest: Mme Diallo's bakery and the rue de Lancry show the canal market, Lila's classroom shows the NGO office, and the Mistral's back room uses the café booth plate.
3. **A pipeline for painting plates already exists.** `app/services/revue/plates.py` makes one image call per place, palette-locks the result, checks it with `looks_wrong`, stores it where `panel_art` stores durable art, and never repaints. It is gated by `REVUE_PLATE_GENERATION_ENABLED` and `panel_art.durable_storage()`.

**Where story variety comes from today.**
- **The serial** (`app/services/living_story.py`): a 6-card shape deck with «standard» twice (`:229-250`), 14 complication cards (`:98-114`), `PAIR_REPEAT_LIMIT = 3` (`:116`), and seeded picks per learner.
- **Season 1** (`app/data/season/s1/gaps.json`): each gap has 3–5 premises, 5–6 small moments and 2–4 complications. The season files name `le_mistral` 172 times; the next place has 65.
- **The writer for later seasons** (`app/services/season_writer.py`) is off. When on, it may only grow arcs from the learner's own material: «a season that invents its premise from nothing is refused».
- **News:** the most inventive mechanism, the headline mechanic, exists only in the feuilleton (`app/services/graphic_novel.py:4547`) and rarely runs now.

## 1. The work packages

**WP-164 Measure what a learner sees twice** (offline, US$0)
- Add a repetition report to the experience walk (`tests/test_experience_walk.py`). It covers the five 30-day lives and the paid evidence records of WP-136, WP-149 and, when it exists, WP-161.
- **Per learner over 30 days, count:**
  - the share of scenes per place, and how many scenes showed a borrowed plate;
  - the longest run of days in the same room, and repeated (character, place) pairs;
  - repeated scene openings (the first narration sentence, normalised);
  - repeated complications and premises, and authored or fallback text seen twice.
- **Across learners:** the share of day-N text that two lives have in common. Tentpole days are the same on purpose; gap days should not be.
- **Output:**
  - a table in `docs/implementation/atelier-v2/VARIETY-BASELINE-2026-10.md`;
  - a `repetition_budget` check in the walk, with thresholds the owner sets after reading the table. The check logs and does not fail until then.

Done when: the baseline table exists for the five lives, and WP-165 to WP-168 each name the number they intend to move.

**WP-165 The image model paints places, not people** (the drawn set's art)

The image model's job under the drawn art set is the room the cast stands in.

- **Step 1, the borrowed plates.** Paint the 12 borrowed plates with the `revue/plates.py` pipeline, at about US$0.06 an image.
  - Write one brief per place in `app/services/season/world.py`. Each brief gives the name, three landmarks and the light, which is the `brief_for` rule.
  - Use the owner's `PLATE_STYLE`, which says «No people», not the Revue's people clause.
  - Store the result and switch `plate` to `"own": True`. The existing plates stay the fallback.
  - Order: Odile's flat, quai de Valmy, the stairwell, the gérance Marchand, the mairie, the gare de l'Est, the roof, the notaire, then the rest.
- **Step 2, light and weather.** Add `time_of_day` (morning, day, evening, night) and `weather` (dry, rain) to the scene payload.
  - The director already writes a `visual_direction`. These become two closed fields, and the gap rules can set them.
  - Paint the variants that are used, lazily. At most 22 places × 8 is about US$10, all once; a variant is painted the first time a scene asks for it.
  - `plate_for_place` picks the variant and falls back to the base plate.
- **Step 3, the style check.** Add a palette and flatness check after `palette_lock`. It re-rolls once if the plate has strong gradients, the drift seen in the live panels.
- **Not in scope:** `panel_art` for the painted set stays as it is, switchable and not deleted. One fix that costs nothing goes in anyway: change «same face, hair and clothes» (`panel_art.py:476`) to «same face and hair; clothes as described». Outfits can then change by day once a scene names them.

Prerequisite (owner): the S3 bucket and keys (`GRAPHIC_NOVEL_IMAGE_STORAGE=s3`) in Render. Locally the pipeline writes to `var/`.
Done when:
- every season place shows its own plate in a day-1 to day-20 walk, read in light and dark mode at phone size;
- the WP-164 «borrowed plate» count is 0;
- the owner has approved a contact sheet of the 12 new plates against the 10 originals.

**WP-166 Wider decks for the days between tentpoles** (authored content, no new mechanism)
- **Season 1 gaps** (`gaps.json`): raise every gap to at least 6 premises, 10 small moments and 6 complications, written inside each gap's existing `must_not`, `required` and `by_flag` rules.
- **Place spread:** a new gap rule caps the share of `le_mistral` per gap, at most 2 days in 5 unless a premise requires it. Each gap gets premises that use the places WP-165 painted.
- **The serial:** grow `COMPLICATION_CARDS` from 14 to about 36, and add a second «letter» and «two_hander» card to `SHAPE_DECK`, so «standard» is a third of the deck, not half.
- **Check:** the existing gap validators and critic on 3 seeds × 3 bands with the fake provider. Then one paid read of 6 gap days, about US$0.30, with the WP-149 digest.
- **Owner decision first:** day 1 is the same for everyone. A season learner opens on the authored T1, and the journey's first café scene opens on «Il pleut sur le canal…» (`app/data/journey_scenarios/journey-content-v1/order_at_cafe.json:44`). Does that stay a shared opening on purpose, or should T1 get 2–3 authored openings picked by seed?

Done when: the WP-164 numbers for gap days (place share, repeated premises, cross-learner overlap) have moved to the owner's thresholds, and the paid read loses no more than WP-149's bar.

**WP-167 A news day inside the season** (depends on WP-138 for real dossiers, and on WP-139 before production)
- **The premise:** at most one gap day a week can take the week's top Revue dossier as its premise. It is a new premise kind `news` in the gap rules, with Romy carrying it in, as the feuilleton already does.
- **The prompt:** reuse the headline-mechanic step (`graphic_novel.py:4547`, «If it could fit any headline, it is wrong»). The day enacts the mechanic of the news inside the season's world and its open threads. It does not report the article.
- **Same guards as any gap day:** `must_not`, tentpole spoilers, the departed-cast guard, the register guard (WP-163), and the dossier's own claims check, so no invented facts about real events.
- **Topic policy:** use the Revue's spread (food and culture, city, sport and nature), and keep politics off news days by default. The old ranker favoured ministers (`docs/feuilleton-audit-2026-07-23.md:34-43`).
- **Before WP-138's real intake:** build against the 12 evergreen dossiers, which also tests the WP-138 «out of season» rule.
- Flag `ATELIER_SEASON_NEWS_DAY_ENABLED`, off, on for the owner only.
- **Check:** a paid read of 5 news days at A2 and B1, about US$0.30. Each day must name its headline mechanic, keep the season's threads moving, and pass the claims check.

Done when: the owner has read 5 news days and judges at least 3 «a story that could only have happened this week».

**WP-168 Dry-run the season writer, and decide how far a season may move**
- **The writer only runs when season 1 has ended**, after about 59 days and the epilogue, so the owner will not see it in the pilot. Dry-run it instead:
  - call `living_story.roll_over_season` with the writer on, for 3 synthetic lives that finished season 1 with different flags (garder, partager, laisser partir);
  - take the lives from the experience walk past day 66.
- **Output:** a contact sheet of the 3 drafted seasons (logline, 5 arcs, the material row each arc grows from) and the critic's verdicts, at about US$0.30.
- **Measure:** do the three drafts differ from each other and from season 1 in premise, places and the cast's goals? Or does «grow only from the learner's material» keep every season at the Mistral?
- **Owner decision, the real versatility question:** may a later season change the city, the genre or the protagonist's situation? Examples: season 2 in Marseille while the learner works a summer job, or a mystery instead of a dramedy. If yes, a follow-up package lets the writer propose a new setting from a short list. It reuses WP-165 to paint the new places, and keeps the cast that travels.

Done when: the contact sheet is in `docs/implementation/atelier-v2/evidence/wp168-season-writer/`, and the owner has answered the decision.

## 2. Order

| When | Packages | Notes |
|---|---|---|
| Any time, no cost | WP-164 | the baseline; it decides the thresholds for the rest |
| After WP-150 lands | WP-165 step 1, WP-166 | they touch different files: `season/world.py` and plate assets, against `gaps.json` and `living_story.py` decks |
| After S3 is set | WP-165 steps 2–3 | |
| After WP-138 | WP-167 | WP-139 before it reaches anyone but the owner |
| Any time | WP-168 | a dry run, independent of the pilot |

Track A of the 8 October doc (land, deploy, the owner's first week) still comes first. These packages move up only if the WP-152 friction list names sameness.

## 3. Owner decisions this doc needs

1. Repetition thresholds for the `repetition_budget` check, after reading the WP-164 table.
2. Set S3 storage in Render (it was already needed for any durable art).
3. Day 1 shared on purpose, or 2–3 authored openings of T1 (WP-166).
4. News days without politics by default (WP-167).
5. May a later season change city, genre or situation (WP-168)?
6. Paid runs: about US$10 one-off for plates and variants (WP-165), and about US$0.90 for the WP-166, WP-167 and WP-168 reads.

## 4. Owner decisions, 11 October (evening)

Standing rule: when in doubt, the more creative, ambitious, non-deterministic variant. Locally only focused tests; CI runs the full suite.

1. **Storage.** The 12 borrowed plates are painted once and committed as static WebP next to the other plates, so they need no storage. Everything painted per day (variants, news-day plates, new seasons' places) needs durable storage in production. Choice: Cloudflare R2 through the existing S3 code (`GRAPHIC_NOVEL_IMAGE_STORAGE=s3`, `GRAPHIC_NOVEL_IMAGE_S3_BUCKET`, `GRAPHIC_NOVEL_IMAGE_S3_ENDPOINT_URL`, the two keys). The owner enters the keys in Render.
2. **Day 1 varies.** The opening is generated per learner around the authored spine (T1's beats still happen); the authored opening is the fallback.
3. **No topic guardrails on news.** Any topic, politics included. Tone follows the news.
4. **A later season may move:** city, genre, the learner's situation, anywhere French is spoken.
5. **News day every second generated day**, each with its own freshly prompted plate. One plate costs about US$0.05, so the 12 missing plates cost about US$0.65 once. The earlier US$10 was the ceiling for every variant of every place, painted lazily and only when a scene asks.

All new behaviour defaults on behind a kill switch: `ATELIER_SEASON_PLATES_ENABLED`, `ATELIER_NEWS_DAY_ENABLED` and `ATELIER_NEWS_DAY_EVERY=2`, `ATELIER_VARIED_FIRST_DAY_ENABLED`, `ATELIER_SEASON_WRITER_MAY_MOVE`. The shared interface is `app/services/season/plates.py` (base branch `wp/variety-base`).
