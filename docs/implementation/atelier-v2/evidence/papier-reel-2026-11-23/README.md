# «Le Papier» — the real-model check after the integration (22–23 November 2026)

PR 963 (`281bac67`) was merged at 12:27 UTC on 22 November and Render deployed it by blueprint sync (worker live
12:29, API 12:30). This check ran the same afternoon on the merged code, with real models, behind a spend meter.
Nothing was changed in production. Nothing is merged. No gate was altered.

## 1. Production (read-only: Render logs and a read-only SQL session)

| what | seen |
|---|---|
| deploy | `281bac67` live on `atelier-api` and `atelier-worker`; the migration `b2d4f6a8c0e1` (`revue_story_media`) ran; no error- or critical-level log line on either service since the deploy |
| learners | no learner request to `/revue/*` or a journey since the deploy (to ~14:30 UTC) |
| intake | the last built stories are of 2026-11-20 (2 a day, daily cadence — `REVUE_CADENCE` is set in the dashboard, not in `render.yaml`); 21 and 22 Nov ran while the switch was off (`{'status': 'disabled'}`). The news feeds answer in production (10 feeds `ok`) |
| **stories with takes / titre** | **none.** All twelve stories of 15–20 Nov carry `checks.comptoir = "comptoir:desk_failed"`, `titre` none |
| why | on 15–20 Nov the comptoir desk ran on Claude and production's Anthropic key answered **401 invalid x-api-key**; `ensure_comptoir` recorded the failed call as a final refusal. The key works again (200s in the worker's log on 22 Nov) |
| **what a learner gets today** | the front page shows three stories; tapping one starts a session; `takes_at_start` honours the recorded refusal → **every Papier session is the old pre-cut chat**; «Le titre» cannot be dealt. A2+ learners get a planned (optional) Papier step on a Papier day. No crash, no dead end, the step completes on close |
| tomorrow | the 04:00 UTC intake builds new rows for 2026-11-23 and runs the comptoir (gpt-6-luna) and titre (OPENAI_MODEL = gpt-6-luna) desks on them; the twelve old rows stay chats until they leave the seven-day kiosk |

The owner was told at once. Options given (not taken): clear the stale marks
(`update revue_dossiers set checks = checks - 'comptoir' where checks->>'comptoir' = 'comptoir:desk_failed';`),
or `REVUE_ENABLED=false` until the next intake. The code fix is PR #1015.

## 2. Method and money

Throwaway database `papier_reel_run` (migrated, core lexicon synced). The six real stories of
`app/services/revue/weekly/2026-W40/sources/` built by the real builder (v4, gpt-6-luna) as of 4 October, then stored
as today's daily period `2026-11-22`, and the morning desks run as `app/tasks/revue.py` chains them. Production values
from `render.yaml` (all twelve switches on, `REVUE_COMPTOIR_MODEL=gpt-6-luna`, writer `claude-sonnet-5-5`, critic
`gpt-6.1-sol`, speech `gpt-4o-mini-tts`); pictures refused.

**Spend meter** (scratchpad `run/meter/sitecustomize.py`, loaded into every process through `PYTHONPATH`): every text,
speech and transcription call reserved its worst case in a file-locked ledger before it was sent and was refused past
US$3.00 in total or past its part's own cap; pictures always refused; an httpx guard refused any call to
api.openai.com / api.anthropic.com / api.elevenlabs.io outside the metered provider methods. Nothing was refused.

| part | calls | US$ |
|---|---:|---:|
| smoke test of the keys | 4 | 0.0001 |
| builder + leads + comptoir + titre desks, six stories (gpt-6-luna) | 35 | 0.0430 |
| desk comparison: comptoir + titre, 5+1 stories × 2 rounds, gpt-6-luna | 46 | 0.0540 |
| desk comparison: same on claude-haiku-5-5 | 37 | 0.1515 |
| Romy's marks, 57 learner texts (gpt-6-luna) | 73 | 0.0171 |
| echo: 7 Papier sessions + 7 next-day scenes (Sonnet writer, gpt-6.1-sol critic, luna) | 83 | 1.4651 |
| speech: 7 clips (gpt-4o-mini-tts) + 7 transcriptions (whisper-1) + 3 session starts | 17 | 0.0578 |
| ranking (no model call) | 0 | 0 |
| browser walk, real stack (gpt-6-luna) | 6 | 0.0016 |
| echo re-check on PR #1020 (§9) | 25 | 0.5659 |
| **total** | **326** | **2.3561** (cap 3.00, 0 refused) |

Speech is the meter's worst case (US$0.020 per 1,000 characters plus a quarter of the instructions); the app's own
estimate for the same clips is US$0.0148. The scene is the dear part: US$0.09–0.34 a Sonnet page with the critic.

## 3. Romy's marks through the scene tutor's check (`REVUE_TUTOR_MARKS_ENABLED`)

57 texts written before the run with their slips recorded (46 planted slips, 19 fully correct, 6 of them spoken
style), A2 German and B1 English, «Ton avis» on Goncourt / fresh produce / 1er octobre and «À toi» on the Arc / fresh
produce / 1er octobre, through the shipped act functions (`comptoir_loop.apply_act`, `titre_loop.apply_act` →
`_proofread` → `regle.marked` → `vet` → `story_lanes._accepted_correction`), rolled back after each.

| measure | result |
|---|---|
| wrong marks shown (French made wrong, or a correct form marked) | **0** |
| planted slips left unmarked | 5/46 — two false friends («actuellement», «excité»; the edit prompt forbids replacing a correct word), three dropped by the tutor check («devenu», «haute», «médical») |
| marks dropped by the tutor check | 8, **all real slips**, all by `gender_only_change`; 5 restored by `regle._fallback` (only when it was the text's only mark), 3 lost |
| printed «corrigé par Romy» text still wrong | **5 texts** — «je pense **que un** prix», «**Je ai** vu», «les tomates sont **devenu**», «le prix … est trop **haute**», «franchises **médical**» |
| rule names that do not fit | 5 concept names («je ai→j'ai» named «Avoir: ich habe»; «avons allé→sommes allés» named «Ich bin, du bist: être»; «de les→des» named «Un, une, des»; …), 4 kind labels |
| hints that give the answer away | 0 of 33; 10 of 43 marks had no hint |
| correct texts touched | 1/19, and that one was the app's own slip: the A2 frame «parce que» + «un prix» printed «parce que un», then marked as the learner's. Spoken style: 0/6 touched |
| hint language | the learner's (de/en) every time |
| edit call failed (empty content) | 0/57 here; **1/1 in the browser walk** (§6) |

The known gap is confirmed and wider: `gender_only_change` folds «qu'un» to «qu un», so every elision and every
noun-subject agreement looks like a gender-only change. Fixed in **PR #1019** (§8).

Best marks: «achète→acheter · Futur proche: aller + Infinitiv»; «ont devenu→sont devenus · Passé composé with être, and
agreement»; «chers→chères» with a hint that does not show the form; «à le→au · Au, aux, du, des».
Worst: «que un» dropped and printed uncorrected; «devenu» dropped and the text shown as clean; the app's own «parce
que un» marked as the learner's; one pronoun-order slip split into two hintless marks; «Ich bin, du bist» as the rule
for the passé composé auxiliary.

## 4. The echo into the next scene (`REVUE_ECHO_ENABLED`)

Seven learners each played a finished Papier (comptoir on Goncourt, fresh produce, 1er octobre; titre on the Arc and
fresh produce; A2 de and B1 en), then the next day's scene was written as production writes it — ahead of time, on
Sonnet with the critic (six scenes), and once on the live path (gpt-6-luna). Ten were planned; the cap allowed six
Sonnet pages (two cost more than US$0.30 each).

**0 mentions of the paper in 7 scenes — so no false and no forced echo, and no echo at all.** On the night path
(`STORY_PLAN_THEN_WRITE=true`) the page is written by `story_split`'s planner and author, whose payloads are whitelists
without `papier_echo`: the block never reaches the model. On the live path the writer saw it, with Margaux and Gus (both
at the counter) on the page, and left it out. Nothing but the prompt guarded «once» and «no fact beyond the record».
Scenes otherwise intact. The memory line «Tu étais partagé» is masculine for every learner. Fixed in **PR #1020** (§8);
re-checked on the real model in §9.

## 5. Speech (`REVUE_VOIX_ENABLED`)

Real path (`POST /revue/sessions` → `GET …/voix` → `POST …/voix/line`, `line_audio.speak_line`), `gpt-4o-mini-tts`,
each clip transcribed back with the app's Whisper call.

| clip | voice | chars | s | word differences |
|---|---|---:|---:|---|
| produce lead (A2) | narrator → sage | 234 | 23.1 | none («9,9 %», «1,5 %», «2026» exact) |
| Romy's take | nova | 114 | 7.0 | none |
| Margaux's take | alloy | 107 | 8.4 | «prix» → «prises» (Whisper split the liaison; the speech is right) |
| Gus's take | fable | 113 | 8.6 | none |
| dictée | sage | 39 | 5.1 | none |
| Arc lead (A1 — the story has no A2 lead) | sage | 109 | 9.6 | «ParisLongchamp» → «Paris Longchamp», «Daryz» → «Daïz» |
| Arc dictée | sage | 25 | 3.3 | «Daryz» → «Darys» |

Four speakers, four voices; no character can get the narrator's. No truncation, no wrong language, digits read right.
**A second learner got all four clips from the cache with no provider call** (new rows, same bytes; the ledger has no
speech row after the first learner). One weakness: the dictée picks the shortest fitting sentence, here «Daryz veut
gagner encore.», built on a horse's name a learner cannot spell by ear (open).

## 6. The browser walk (real stack, German A2, 390 × 844)

API and `next dev` from the merged code against `papier_reel_run`, real provider behind the meter, a Playwright driver
(cookie minted, no password typed). Two new A2 learners, one per assignment. Screenshots `reel-*.png` in this folder.

**«Le titre» on the Arc** — front page clean (`reel-a2de-1-front.png`); the story's picture is a borrowed plate of a
Paris park, not a race (`reel-a2de-titre-1-lire.png`; production has `REVUE_PLATE_GENERATION_ENABLED=false`, so this is
what learners see). The three headlines hold against the claims (`-3-right`). Faults:

1. **A wrong correction in the trap** (`reel-a2de-titre-4-trap-gagne.png`): exaggerated «C'est sûr, Daryz gagne la
   course une deuxième fois», `wrong_fr` «c'est sûr». A learner who tapped «gagne» was told «Bleibt stehen: Das sagt der
   Artikel» — but the article says Daryz «cherchera à» win; «gagne» (for «essaie de gagner») says too much as well.
   Fixed in **PR #1018** (the desk refuses an exaggeration that changes words outside `wrong_fr`; «stet» only for a
   word of the honest headline — this also protects the desks already stored).
2. **Two slips printed as written, then praised** (`-7-marked`, `-8-page`): «Daryz essaie de gagne le course une
   deuxième fois» → the edit call (`max_tokens=1600`, `reasoning_effort=low`) came back with empty content; the
   headline was printed «TEL QUE TU L'AS ÉCRIT» with no word to the learner, and Romy closed with «Merci ! Ton titre est
   en une, et il dit vrai.» Fixed in **PR #1016** (one retry with a larger budget for every Revue edit call; when it
   still fails, Romy says she could not read it and does not praise it).

**«Au comptoir» on Goncourt**, all switches on, every line heard-first (`reel-a2de-comptoir-3-takes.png`):

3. **An invented fact in an honest take**: Romy «Le 25 septembre, le livre sort» — on 25 September the novel was
   withdrawn from the selection, not published. The planted lie was Gus's «Le 8 octobre» (true: the 6th).
4. **And so a wrong correction**: a learner who tapped Romy's (false) line was told «Non, relis bien» / «nicht dieser»
   (`-5-romy-tapped`). **Not fixed** — no code check can see «sort»; see §10.
5. After that miss the «Prévision» card prints «… doit être publiée le 6 octobre 2026» right above Romy's next
   question «À quelle date, en vrai ?» (`-6-date-visible`): the catch's follow-up becomes copying. Open.
6. **«corrigé par Romy» over a slip** (`-9-avis-done`): «le écrivain dit que il a écrit … la Académie a pas de preuve»
   → round 1 marked «le écrivain» and «la Académie a · ein Wort fehlt» (the elision folded into a «missing word»
   label), round 2 «la Académie»; «que il» was never marked and the printed text kept it. The same tutor-check drop as
   §3; fixed in PR #1019. The first mark's «Im Artikel» example quoted Romy's take, not the article (open, minor).

Dark mode of the printed page: `reel-a2de-comptoir-10-page-dark.png`. No horizontal scroll on any screen (scrollWidth
390 throughout).

## 7. The ranking and the front page (`REVUE_PEDAGOGY_PICK_ENABLED`, `REVUE_CHOICE_ENABLED`)

Three learners with different due words, a rule introduced that day and interests, on a copy of the six stories.
**Each learner's best story came first**; the sensitive budget story and the story without a playable assignment were
never offered. But **5 of 17 stated reasons were false or misleading**:

| learner | card | reason shown | the truth |
|---|---|---|---|
| Anna (de, A2) | produce · Le titre | «Mit 3 deiner Wörter …» | «caisse» and «panier» occur only in the comptoir takes; she meets 1 of 3 |
| Anna | Arc | «Mit 2 deiner Wörter» | «cours» matched «course» |
| Anna | produce | «Regel des Tages: Dans, sur, sous …» | the detector matched «9,9 % sur un an» |
| Ben (en, A2) | Goncourt | «today's rule: Relative pronouns qui and que» | it matched «L'Académie pense qu'…», a conjunction |
| Chloé (fr, B1) | Arc | «ton sujet : sport» for cycling | too broad (kept as a note) |

All fixed in **PR #1017** (the reason of the card's own assignment; a stem match leaves only an inflection; the two
detectors; the lead the learner actually reads).

## 8. The desks: `gpt-6-luna` against `claude-haiku-5-5`

Same six stories (the budget story is a correct `skip` on both), comptoir and titre, two rounds each, no salvage beyond
the shipped retries. Raw answers: scratchpad `run/out/desks.json`, takes side by side `run/out/desks-side-by-side.txt`.

| desk | gpt-6-luna | claude-haiku-5-5 |
|---|---|---|
| Au comptoir | **6/10** (+ 3/5 in the morning run) | **9/10** (the one miss: not JSON) |
| Le titre | **6/10** (+ 3/5 in the morning run) | **7/10** |
| US$ a desk call | ≈ 0.0012 | ≈ 0.0043 |

Luna's refusals are Gus's lie without a fitting distractor, numbers not in the claims, build tiles too long; Haiku's are
build pairs not resting on one claim. The French is close: both write lively regulars and both slip — Luna's Romy «Au
Québec, mon panier n'aimait déjà pas ça», its exaggeration «Daryz gagne toujours la course» (again the ambiguous
«toujours» of the first run, and a change outside `wrong_fr` that PR #1018 now refuses); Haiku's Romy «Mon budget
pleure, c'est pas pire» (Québécois for «not bad» — contradicts itself), its Margaux «Ça dépend, des fruits. En août,
5,9 %.» Haiku's exaggerations are the better ones («…, c'est officiel» against a provisional estimate; «c'est sûr»).

**Recommendation:** with the Anthropic key working again, set `REVUE_COMPTOIR_MODEL=claude-haiku-5-5` (its old
default; 9/10 against 6/10, about a third of a cent more per story). The titre desk has no model setting of its own —
it runs on `OPENAI_MODEL` — so it stays on luna until a `REVUE_RUBRIQUE_MODEL` exists (open). Ten stories a model is a
small sample; watch the morning's `checks` column for a week.

## 9. The fixes (draft PRs, guards first, nothing merged)

| PR | fixes | verification (Sonnet, own worktree) |
|---|---|---|
| [#1015](https://github.com/Pechst1/ConversationalLanguageLearning/pull/1015) | a failed desk call is not recorded as a refusal; a row already marked `desk_failed` is asked again (comptoir and leads); real refusals stay final | **sound**: 4 new tests fail on main and pass (5 are guards); 940 revue tests; CI green; a mixed `desk_failed,<real refusal>` stays final; a success clears the stale mark |
| [#1016](https://github.com/Pechst1/ConversationalLanguageLearning/pull/1016) | Revue edit calls retry once on empty content; an unread headline/opinion is said so, never praised | **sound with notes**: 3 new tests fail on main and pass; 935 revue tests and 241 frontend tests pass; CI green. Retry only on the four edit calls, at most 2 attempts, every attempt metered; the honest line never shows the form; fr/de/en present. An Anthropic refusal also gets one retry (harmless) |
| [#1017](https://github.com/Pechst1/ConversationalLanguageLearning/pull/1017) | the five false ranking reasons | **sound with notes**: 14 new cases fail on main and pass; 1,995 related tests; CI green but one walk still running. The stricter stem match no longer finds some real forms («nouveau/nouvelle», «blanc/blanche», «appeler/appelle», «manger/mangeons», «un étudiant/une étudiante») — a due word may be left out of a reason (it under-promises; open) |
| [#1018](https://github.com/Pechst1/ConversationalLanguageLearning/pull/1018) | the trap: exaggeration only inside `wrong_fr`; «stet» only for the honest headline's words (`titre-desk-v4`; the Fête evergreen rewritten) | **sound after a follow-up**: 3 new tests fail on main and pass; 934 revue tests; 25 realistic honest/exaggerated pairs → 0 false refusals, the real Arc pair refused. The verifier found the rewritten Fête evergreen's honest headline («Une fête gratuite qui plaît à beaucoup») rests on no claim; rewritten on the PR (`a9a02ce8`): honest «La fête est gratuite» / «Une fête gratuite pour toutes les musiques» (c2), exaggerated = the same + «toujours calme» (against c3, the noise complaints); the trap test now runs on the shipped file; 934 revue tests pass |
| [#1019](https://github.com/Pechst1/ConversationalLanguageLearning/pull/1019) | elision and noun-subject agreement no longer dropped by `gender_only_change` (shared with the scene tutor; first person still protected); a known slip never printed under «corrigé»; «parce qu'un»; concept names | **sound with notes**: 26 new tests pass (23 fail on main), 1,027 revue/gender tests pass, gold gate unchanged; ~70 adversarial cases — no first-person change let through. Still drops (no regression; main dropped all): a named third person after «je pense que» («Je pense que Marie est fatigué»), «personne», «celle-ci», «avec la femme qui est venu», «Les filles que je vois sont fatigué» |
| [#1020](https://github.com/Pechst1/ConversationalLanguageLearning/pull/1020) | a model-free guard on the echo (once, by someone present, nothing beyond the record), then the echo reaches the night writer; «entre les deux» for «partagé» | real model, 2 Sonnet scenes (US$0.57): the block now reaches planner and author; 0 echoes written (none false); the guard refused synthetic absent-speaker, invented number and invented name lines offline. Gaps: a second mention phrased «le papier de Romy» is not counted as a repeat; the reask path is untested on real output |

Gold fingerprints unchanged on #1019 and #1020 (`scripts/gold_transcripts.py check`); no CI workflow, `gate.json` or
known-failures entry touched by any PR.

**Echo re-check on #1020 (real model).** Two of three planned scenes ran within the part's cap (the third would have
crossed it): comptoir on fresh produce (A2 de, Margaux and Gus on the page) and on Goncourt (B1 en, a Lila page on a
staircase). In both, `papier_echo` reached `planner_payload` and `author_payload`; the writer used it in neither — on
the first page a natural line was there to take («Tu étais pour, moi contre»), on the second it would have been
forced. So after the fix: 0 echoes in 9 scenes in all, no false one. The echo is now possible but rare; a page that
actually echoes the paper was not seen, so the guard has only been tried on synthetic lines.

## 10. Still open

- **Invented facts in honest comptoir takes** (Romy's «le livre sort») and the wrong correction that follows when a
  learner catches one. No code check can read a verb against a claim; this needs either a model critic on the takes or
  an editor. Owner decision.
- The «Prévision» card shows the answer of the catch's follow-up question.
- «Im Artikel» examples may quote a regular's take instead of the article.
- «La photo» and «Le micro» still close with praise after an unread text (parked assignments; not dealt today).
- PR #1017's stem match misses irregular feminines and spelling shifts (see §9); the qui/que verb blocklist is open-ended.
- PR #1019's speaker check still drops «Je pense que Marie est fatigué», «personne», «celle-ci», «avec la femme qui est venu» (no regression).
- The echo guard does not count «le papier de Romy» as a second mention.
- The dictée may pick a sentence built on a proper name.
- Contract days drop the echo by design (`page_pool.DROPPED_KEYS`) — 13 of 45 gap days; owner call.
- The story picture is a borrowed plate unrelated to the story while plate generation is off.
- A titre desk model setting; false friends in the edit prompt (owner call).
- `REVUE_WORDS_IN_DECK_ENABLED` and `REVUE_QUARTIER_AFFICHE_ENABLED` make no model call and were not re-run here (they
  were checked on the full stack with fakes on 22 Nov). The poster prints today's date over the kiosk's top story,
  which can be up to two days old (cosmetic).
- Not built (unchanged): Romy mentioning the scene at the next paper; a rule used in the paper counting as practice; a
  rule introduction on a Papier day. News feeds and Commons were not reachable for «La photo» (parked).

## 11. One recommendation per switch

| switch | recommendation | why |
|---|---|---|
| `REVUE_ENABLED` | **keep on**, and clear the stale `desk_failed` marks (SQL in §1) or merge #1015 | no crash; today every session is the old chat; the 23 Nov intake will build new rows |
| `REVUE_COMPTOIR_ENABLED` | **keep on**; set `REVUE_COMPTOIR_MODEL=claude-haiku-5-5` | 9/10 against 6/10; the invented-fact risk (§10) is the same on both models |
| `REVUE_ASSIGNMENTS_ENABLED` | **keep on, with `REVUE_ASSIGNMENTS_OFFERED=comptoir`** until #1016 and #1018 are merged | «Le titre» showed a wrong «stet» and praised an unread headline |
| `REVUE_POURQUOI_ENABLED` | **keep on** | the «pourquoi» lines read right in the walk |
| `REVUE_TUTOR_MARKS_ENABLED` | **turn off in production until #1019** | 5 of 57 texts and 1 of 1 walk opinion printed «corrigé par Romy» over a real slip |
| `REVUE_PEDAGOGY_PICK_ENABLED` | **keep on**; merge #1017 | the order is right for all three learners; 5 of 17 reasons are false |
| `REVUE_CHOICE_ENABLED` | **keep on** | sensitive and unplayable stories never offered |
| `REVUE_WORDS_IN_DECK_ENABLED` | **keep on** | no model call; not re-run here |
| `REVUE_PLANNED_STEP_ENABLED` | **keep on** | the step completes on close; optional |
| `REVUE_QUARTIER_AFFICHE_ENABLED` | **keep on** | cosmetic date mismatch only |
| `REVUE_ECHO_ENABLED` | **keep on** | harmless: inert on main (never reaches the night writer); with #1020 it reaches it, guarded, and the writer stays cautious (0 in 2) |
| `REVUE_VOIX_ENABLED` | **keep on** | four voices, digits right, cache works |
