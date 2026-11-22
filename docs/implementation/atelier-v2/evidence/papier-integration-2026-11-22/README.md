# «Le Papier» — the cut and the integration (night of 22 November 2026)

Branch `claude/papier-integration`. Nothing is merged; every new behaviour is behind a switch that is off.

## Why

The first run on a real model (`../papier-premier-tirage-2026-11-22/README.md`, US$0.44) showed that of the six
assignments only two are good on real news: «Au comptoir» (3 of 5 stories, the best writing of the run) and
«Le titre» (4 of 5 after fixes). «Le micro» passed on 2 of 5, «L'intox» on 0–1, «Le fil» on none, «La photo»
was never reached. And the feature was an island: it used neither the day's rule, nor the learner's due words,
nor the scene tutor's checks, nor the story, nor the Quartier, nor sound.

## The cut

`REVUE_ASSIGNMENTS_OFFERED` (default `comptoir,titre`). Only these two are dealt and only their material is
built each morning. Fil, intox, photo and micro stay in the code with their tests; setting the list brings one back.

## What ties it into the app

| switch (all default off) | what it does |
|---|---|
| `REVUE_PEDAGOGY_PICK_ENABLED` | stories are ranked by the learner's due words, the day's rule (its detectors run over the story's French) and interests; the reason is kept and shown |
| `REVUE_CHOICE_ENABLED` | the paper opens on a front page of up to three stories; the learner picks one (`choix-*`, `ensemble-front*`) |
| `REVUE_TUTOR_MARKS_ENABLED` | Romy's marks pass the scene tutor's own verification and carry the app's grammar-concept names; a mark under the day's rule is stamped (`regle-*`, `ensemble-marks*`) |
| `REVUE_WORDS_IN_DECK_ENABLED` | words kept in the paper open the next day's deck and reach the scene director's vocabulary |
| `REVUE_ECHO_ENABLED` | what the learner did at the paper (story, side taken, printed sentence, who was there, words kept) reaches the next scene's director; one character may mention it once |
| `REVUE_PLANNED_STEP_ENABLED` | the paper is a planned step of its day, priced at 6 minutes, with its own row on Home (`ensemble-home-*`) |
| `REVUE_QUARTIER_AFFICHE_ENABLED` | today's edition hangs on the quai's Morris column and opens the paper; «LU» once filed (`quartier-*`) |
| `REVUE_VOIX_ENABLED` | the lead is read aloud; each regular's line is heard before it is read; «la dictée de Romy» (`voix-*`, `ensemble-takes-*`, `ensemble-dictee-*`). Server clips also need `ATELIER_EPISODE_AUDIO_ENABLED` |

Always on (plain bug fixes): a correct question is never rewritten to inversion below B2; a mark that changes
nothing is never shown; closing the counter no longer fails when the learner used a word from the word bank;
a word kept by hand in the paper is filed as a paper word; the walk harness fakes speech, so a walk cannot spend.

## Checked

- Suites on the merged branch: 1,208 backend tests after the fix round (1,678 on the wider selection before it),
  910 frontend tests, type check and generated-types check clean, ruff clean, free gold check passes with the
  scene prompt hash unchanged.
- All switches on, full stack with fake providers, phone size, German A2: a Papier day planned with its step,
  front page, counter heard first, Romy's marks, filing, next-day deck opens with the paper's words, the next
  scene's stored context holds the echo, the poster shows the headline and opens the paper. The defects that pass
  found (eight) were fixed and re-shot (`ensemble-*`).

## Not checked

- Nothing new has run on a real model: the ranking, Romy's marks through the tutor check, and whether the scene
  writer uses the echo well are proven only with fake providers.
- «Le titre» on the full stack (the stack's stories carry only the counter), real speech quality, a real phone.
- The echo's way back (Romy mentioning the scene at the next paper) is not built: it needs a record that the
  scene really used the echo.
- A successful use of the day's rule in the paper does not yet count as grammar practice.
- A Papier day still has no rule introduction of its own (the planner plans it as a classic day); the day's-rule
  stamp therefore mostly falls back to the most recent rule.

## Spend

US$0.44 on the first real run. One accidental speech call during the combined check (116 characters, under one
cent): the harness faked text and pictures but not speech; fixed.
