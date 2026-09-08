# WP-14F — Longitudinal integration and generation review

Independent QA agent, 2026-09-07. Branch `codex/serial-season-engine-production`, base commit
`04998ec`, **working tree** (the engine owner's uncommitted prompt work on
`app/services/living_story.py` — the learner-address block and `learner_level_band` — is part of
what the live runs measured). Prompt/rubric identity: `living_story.VERSION = "living-story-v1"`.

This report separates two kinds of evidence and never mixes them:

* **Deterministic** — `tests/test_living_story_longitudinal.py`, real API + real SQLite + a
  controllable clock, with a scripted fake provider. It proves state transitions, provenance and
  world invariants. It proves nothing about generated French.
* **Live** — five bounded runs of `scripts/longitudinal_story_review.py` (plus one control run of
  the pre-existing `scripts/review_living_story.py`) against `gpt-5-mini`, synthetic context, no
  application database, no learner records. This is where prose quality is judged.

Nothing here is marked as expected-to-fail to make the feature look finished. Every unresolved
defect is listed in §4 with the day and scene that produced it.

---

## 1. Verification actually run

```
venv/bin/python -m pytest -q tests/test_living_story_longitudinal.py tests/test_living_story.py
........................................                                 [100%]      40 passed

venv/bin/ruff check scripts/longitudinal_story_review.py tests/test_living_story_longitudinal.py
All checks passed!

venv/bin/python scripts/longitudinal_story_review.py            # no --live
No requests made. --live simulates 14 days for a A1 learner using at most --max-requests (60)
model requests (draft + review + turn + review per day). No application database is used.
```

The no-`--live` path returns before any application module is imported, so no provider object can
exist and no request can be made. Under pytest the repository conftest neutralises credentials and
every test injects a fake provider; no test in this file can reach a network.

## 2. Deterministic coverage against the WP-14F list

23 tests in `tests/test_living_story_longitudinal.py`. Assertions compare durable records against
each other — thread state, the pinned brief the director actually received
(`DailyJourneyStep.private_task["scenario_brief"]["story_context"]["draft"]`), the reader
projection and the recap. No test passes on a substring callback alone.

| WP-14F requirement | Test | Key invariant asserted |
|---|---|---|
| ≥14 sessions, A1 / A2 / higher level | `test_fourteen_days_stay_one_world_for_each_level[A1,A2,B1]` | 14 journeys, one director call per day, every earlier event id present in every later director context, 14 completed episodes, `current_episode_index == 14`, distinct novelty keys, 3 distinct chapter ids (resolved chapters replaced, never replayed), `level_band` = the learner's own band |
| Higher level: suitable content or an honest limit | same test + `test_invitation_level_matches_the_generated_scene[A1,A2,B1,B2,C1]` | B1 learners get B1-banded generated scenes and a B1 director context; there is **no** supported-level ceiling below B2 — C1/C2 learners are served the B2 ceiling, and the invitation card now states the same band as the scene |
| Explicit learner proposal → later planning → resolution | `test_a_learner_proposal_stays_open_until_a_later_day_closes_it` | commitment stored with `source_event_id` and the learner's **verbatim** `source_quote`; day 2's director context contains that exact record; day 3 closes it with `resolved_by` = day 3's event id; day 4 shows it resolved with no open duplicate |
| Chain of three causally connected scenes | `test_three_scenes_form_a_causal_chain_with_real_event_provenance` | day *n*'s pinned draft cites exactly day *n-1*'s event id, that event exists and points at a real scene, and the citing character is among its witnesses; day 1 cites nothing |
| Impossible character knowledge | `test_a_character_cannot_use_an_event_they_did_not_witness` | Margaux's actor payload carries no event/commitment from Romy's scene, no `recent_situations`, no `possible_developments` |
| Refusal | `test_a_refusal_is_recorded_honestly_and_keeps_the_chapter_open` | event `outcome == "not_yet"`, learner's quote stored, chapter **not** resolved even though the model asked to close it, no commitment invented, recap `outcome_key == "open"` |
| Changed plans | `test_a_changed_plan_supersedes_the_earlier_arrangement` | old commitment `resolved` with `resolved_by`, new one open with the new verbatim quote |
| Failed communication | `test_failed_communication_never_becomes_success_or_credit` | `not_yet` is durable, recap evidence empty, every capability still without evidence |
| Skipped day | `test_a_skipped_day_creates_nothing_and_the_story_resumes` | the skipped day creates no journey and costs no generation; the next day still cites the last real event |
| Abandoned draft | `test_an_abandoned_draft_invents_no_ending` | scene and episode `abandoned`, empty resolution/summary, no story event, no capability credit; the next day publishes a fresh scene |
| Concurrent optional/daily completion | `test_the_legacy_surface_cannot_complete_the_beat_while_the_journey_settles` | legacy `POST /graphic-novel/scenes/{id}/complete` → 409 both mid-journey and after settlement, no generation, exactly one event, one completed episode, cursor advanced once |
| Stale generation | `test_a_stale_generation_cannot_publish_over_newer_canon` | `bind_journey` raises `story_revision_conflict` when canon moved between generation and publication; a stale `expected_revision` gets 409 `journey_version_conflict` |
| Duplicate requests | `test_duplicate_requests_write_exactly_one_story_event` | replayed create/attempt/finish mutation ids → identical responses, one scene, one director call, one actor call, one story event |
| Absent memory | `test_a_new_learner_has_no_memory_at_all` | a new learner's context has no thread, events, commitments, chapter or situations |
| Superseded facts | `test_a_resolved_commitment_cannot_be_resolved_again` + day 4 of the proposal test | resolving an already-resolved id raises `unknown_commitment`; resolved commitments never reappear as open |
| Another learner's data | `test_another_learners_story_never_leaks_into_this_one` | the second learner's director context contains neither the other learner's event ids nor their sentences; reader list, read and position writes are 404 |
| Repetition detection | `test_a_scene_that_repeats_a_recent_situation_is_refused` | a reworded repeat of a recent premise raises `repeated_situation` |

Not covered deterministically (out of scope here, covered elsewhere or still open): PostgreSQL row
locks (`scripts/verify_story_engine_pg.py`, 33/33 per the engine handoff), frontend reader
integration, and real learner cohorts.

## 3. Live runs — what they cost and what they produced

All runs: `gpt-5-mini` (provider `openai`), `--attempts 2` (production value), prompt version
`living-story-v1`, learner address `neutral`, synthetic context, no database.

| Run | Level | Days attempted | Accepted | Failed | Requests | Cost (USD) | Report |
|---|---|---|---|---|---|---|---|
| A1 #1 | A1 | 14 (1 scripted skip) | **0** | 13 | 31 | 0.0887 | `var/reviews/atelier-longitudinal-A1.json` |
| A2 #1 | A2 | 14 (1 skip) | **0** | 13 | 33 | 0.0945 | `var/reviews/atelier-longitudinal-A2.json` |
| Control (existing 3-scene sampler) | A1 | 3 | 1 | 1 (aborts) | 6 | 0.0133 | `var/reviews/wp14f-control-three-scenes.json` |
| A1 #2 (instrumented) | A1 | 9 before the request cap | 6 | 2 | 40 | 0.0929 | `var/reviews/atelier-longitudinal-A1-instrumented.json` |
| A2 #2 (instrumented) | A2 | 10 before the request cap | 4 | 5 | 36 | 0.0903 | `var/reviews/atelier-longitudinal-A2-instrumented.json` |
| B1 | B1 | 4 before the request cap | 3 | 1 | 20 | 0.0451 | `var/reviews/atelier-longitudinal-B1.json` |

**Total paid: 166 requests, US$0.4248**, inside the owner's ~US$0.50 authorisation. Across the five
longitudinal runs: 51 simulated days, 4 scripted skips, **13 accepted days and 34 days that produced
no usable scene or turn**.

Latency (A1 #2, per stage, seconds): director draft median 15.1 / max 17.6; director review median
3.3 / max 5.6; actor turn median 9.8 / max 16.9; actor review median 4.6 / max 12.2. Per accepted
day the whole pipeline used 30–76 s of provider time and US$0.0087–0.0185 (mean 0.0155). A2's
accepted days averaged US$0.0226. **The measured cost is roughly twice the ≈US$0.007 per scene
recorded in `ENGINE-IMPLEMENTATION.md`**, because rejected attempts are paid for too.

No run completed fourteen live days: A1 #1 and A2 #1 produced no scene at all after day 1, and the
instrumented runs hit their request caps at day 9, day 10 and (B1) day 4. **The tested live horizon
is nine consecutive days (A1), ten (A2) and four (B1) — not fourteen.**

### 3.1 The B1 sample answers the "suitable content or an honest limit" question: neither

The B1 run's band labelling is correct (`level: B1` in the director context, B1 on the brief), but
the content it produced is A1 material:

* day 1 objective — *"Order a coffee and a croissant at the café."*, premise *"Tu viens d'arriver à
  Paris… Marin t'encourage à commander toi-même pour la première fois."*
* day 2 objective — *"Practice ordering a coffee and pastry and specifying 'to drink here' or 'to
  go'."*, premise *"Marin t'encourage à la répéter toi-même pour te sentir plus sûr·e."*
* day 3 is the only day a B1 learner would learn from — confirming a dinner (time, guest count,
  what to bring), and it arrived only because the learner proposed the dinner on day 2.

Scene word counts were 82, 73 and 105 against a 170-word ceiling, so nothing pushed the density up.
A B1 learner is therefore neither served suitable content nor told about a limit; they are served
beginner scenes with a B1 label. (Day 2's premise also carries another inclusive-dot form,
*"sûr·e"*, see L-6.)

One thing worked notably better than at A1: the learner's day-2 proposal became **day 3's scene**
immediately, citing `day:1` and `day:2`.

## 4. Findings, ranked by severity

Every finding below is from the **live** runs unless marked otherwise. Each names the run and day
whose recorded scene/turn is the evidence; all of them are in the JSON reports listed above.

### L-1 — Critical. The director cites situation ids as event sources, and loses the whole day

`bind_journey` writes each published situation into `live["recent_situations"]` as
`{"id": "story_<hex>", "novelty_key", "premise_fr", "causal_reason"}`, and `story_context` passes
that straight to the director. The director then mixes those ids into `source_event_ids`, which
`_validate_scene` only accepts from `events[].id` — so the entire draft is thrown away with
`unknown_story_source`.

Evidence (A2 #2, day 5, both attempts, from the captured raw drafts):

```
attempt 1  source_event_ids: ["day:1", "day:3", "story_547d72792d1a484dab3ff886ec12747a"]
attempt 2  source_event_ids: ["day:1", "day:2", "day:3", "story_f731e681f5...", "story_6604c8f3...",
                              "story_d5897954...", "story_547d7279..."]
```

`story_547d7279…` is a `recent_situations` id, not an event. Same shape again on day 8. The learner
pays two model calls and gets `story_unavailable`.

It becomes total when `events` is empty, because then *every* citation is unknown. That is exactly
the state left by a day whose turn never settled — including the abandoned draft WP-14F requires to
work. In **A1 #1** the day-1 turn failed, so no event ever existed, and **all 13 remaining days
failed, 12 of them with `unknown_story_source`**: the learner would have been permanently unable to
start a day. A2 #1 collapsed the same way from day 3.

Suggested fix (engine owner): stop projecting `id` into the director's `recent_situations` (or
rename it and state in the prompt that `source_event_ids` come only from `events[].id`), and drop
unknown ids instead of failing the draft — the same tolerance already applied to
`demonstrated_target_ids`.

### L-2 — High. Five of six accepted A1 days were the same practice task

A1 #2, days 1, 2, 3, 5 and 7 are all "order a drink at the counter and ask to sit at the booth".
`objective_native` is literally identical on days 3, 5 and 7 ("Order a drink and ask to sit at the
booth."), and the suggested answers are near-identical ("Un café, s'il te plaît…", "Un café, s'il te
plaît, et je peux m'asseoir à la banquette ?", "Je voudrais un thé, s'il te plaît, et je peux
m'asseoir à la banquette ?").

The novelty guard fires on wording only. Day 4 was correctly rejected as `repeated_situation`, and
day 5 was then **accepted with the same situation reworded** ("Il pleut…" → "La pluie tombe toujours
sur le Canal…"). Two rejected day-4 drafts and the accepted day-5 draft describe the same beat.

The chapter rule compounds it: `_validate_scene` raises `abandoned_chapter` unless an unresolved
chapter's dramatic question is preserved, and here the question was "Vas-tu réussir à commander un
verre et t'installer avec le groupe sans confusion ?" — so the engine actively required five days of
the same task until the model finally set `chapter_resolved` on day 7.

Materially different situations beyond café/meeting/delay: **1 of 6 accepted A1 days** (day 8, the
Saturday meal follow-up) and **1 of 4 accepted A2 days** (day 9, Gus's "château" turning out to be
in Créteil, forcing a choice between asking for the address and meeting at 21 h). Both are good.
Everything else is one café-counter task (A1) or one party-confirmation task (A2).

Suggested fix: include `objective_semantics`/`objective_native` in the repetition check, and bound
scenes per chapter or require a new development each scene.

### L-3 — High. The character's reply recites the app's private suggested answer

A1 #2, day 5. Learner: *"Je suis d'accord, je vais à le marché demain et j'ai allé hier aussi."*
Reply: *"D'accord pour le marché — c'est noté. Mais ici, commande d'abord un verre pour que Margaux
t'apporte quelque chose. **Dis par exemple : « Un café, s'il te plaît — je peux m'asseoir à la
banquette ? »**"* — verbatim the scene's `suggested_response_fr`.

The actor is handed the whole draft, and only "do not expose rubric or internal reasoning" is
forbidden. The learner-visible reply therefore hands over the answer key with **no assistance
recorded**; on a repair turn a copied answer would be credited `PRODUCED_INDEPENDENT`. A
deterministic guard (reply must not contain the suggestion, folded like `_same_utterance`) is the
obvious fix, matching the existing `reply_echoes_learner` rule.

### L-4 — High. Not one commitment was created in thirteen accepted live days

Across all five runs, every accepted turn returned `commitments: []`, including days where the
learner plainly committed: *"Oui, je viens à 20h — peux-tu m'envoyer l'adresse et je prends une
bouteille de vin ?"* (A2 #2 day 3, outcome `met`) and *"je peux organiser un petit repas chez moi
samedi"* (A1 #2 day 2). The only commitment the model ever proposed (A2 #1 day 2) was rejected by
the critic as `incorrect_commitment_source_attribution` — correctly: it had quoted the learner's
line as the source for a commitment that was really the character's reply.

So the durable open-commitment channel that WP-14B/14D rely on to drive later scenes was **never
exercised by the real model**; live continuity ran entirely through `events`. The deterministic
tests prove the bookkeeping is correct when the model emits a commitment; the live sample shows it
usually does not.

### L-5 — Medium. The learner's proposal came back, credited to the wrong person

A1 #2 day 2, the learner proposed a Saturday meal. Day 8's scene is exactly that follow-up, citing
`day:2` as its source and opening a new chapter question ("Vas-tu confirmer si tu peux organiser ou
participer au repas de samedi ?"). This is the WP-14F "explicit proposal affects later planning"
behaviour working live, and it is the best moment in the sample.

But its premise says *"Lila te regarde… et rappelle qu'**elle** a proposé un repas samedi"* — the
learner proposed it, not Lila; the panel dialogue repeats the inversion. The critic accepted it.
An invented authorship of a canon fact is exactly the class of defect the critic exists to catch.
It also took six days to arrive, because the open chapter blocked any new dramatic question until
day 7 resolved it (see L-2).

### L-6 — Medium. The new learner-address rules are prompt-only and are still violated

All runs used `address: neutral`, whose instruction forbids gendered endearments and inclusive-dot
spellings.

* A1 #2 day 1: *"Choisis quelque chose d'élégant, **mon ami**"*; day 3: *"Fais-nous rêver avec ta
  commande, **mon grand**."* — masculine endearments to a neutral learner, in accepted scenes.
* A2 #2 day 2 premise: *"Personne n'a donné l'adresse **au·à la nouvel·le arrivé·e**"*; day 3
  premise repeats *"nouvel·le arrivé·e"*; the day-2 resolution says *"La proposition **du·de la
  nouvel·le arrivé·e**"*. Inclusive-dot forms the prompt names explicitly as forbidden.
* A2 #1 day 1 was rejected for the same class of defect — but by the **critic**
  (`inclusive_dot_form: premise_fr contains 'trempé·e'`), not by a rule.

There is no deterministic guard for this in `living_story.py`; enforcement is a prompt sentence plus
an unreliable critic. A regex for `·` plus a short endearment list would settle it at zero cost.

### L-6b — High (B1). A B1 learner is served A1 content under a B1 label

See §3.1. Two of the three accepted B1 days are "order a coffee and a croissant" and "repeat your
order, and say whether it is to drink here or to take away", with the mentor character coaching the
learner as an absolute beginner. WP-14F asks for suitable content **or an honest supported-level
limit**; the engine gives neither. The deterministic suite confirms there is no ceiling below B2 in
code (`learner_level_band`), so this is a prompt/level-targeting gap, not a missing feature flag.

### L-7 — Medium. Level fit is checked on the scene and nowhere else

`_validate_scene` bounds premise + panels to 110 words (A1) / 170 (A2). Nothing bounds `reply_fr`,
`resolution_fr` or the hint, and they drift well above the learner's level:

* A1 #2 day 2 reply to an A1 learner: *"Putain, quelle ambition — j'aime l'idée ! Mais écoute : ce
  soir on est au comptoir, alors commence par commander quelque chose et viens t'asseoir. On
  discutera des détails (heure, qui invite qui) une fois assis. Tu veux dire que tu invites tout le
  monde ?"* — future tense, embedded clauses, a parenthetical aside, 40+ words.
* A1 #2 day 7 panel, inside a scene that passed the A1 word count: *"dépêche-toi avant qu'Augustin
  ne la squatte"* — subjunctive, `ne` explétif and slang in one A1 line.

### L-8 — Medium. Grammatical defects in the generated French itself

* A1 #2 day 7: Margaux — a woman in the world bible ("Owner-bartender of Le Mistral") — says
  *"**Désolé** — plus de café au lait."* The cast id `margaux_barman` is the likely cause of the
  masculine agreement; a `gender` field in the cast projection would fix it.
* A2 #2 day 2 resolution refers to the learner in the third person (*"le participant apporte une
  bouteille"*, *"du·de la nouvel·le arrivé·e"*) instead of addressing them as *tu*.
* Inclusive-dot forms as in L-6, which no French teacher would put in front of an A1/A2 learner.

### L-9 — Medium. One correction per turn, and not the important one

A1 #2 day 5, learner: *"Je suis d'accord, je vais **à le** marché demain et **j'ai allé** hier
aussi."* The engine corrected `à le marché → au marché` (right, and well explained) and said nothing
about `j'ai allé` → `je suis allé`, a core A1/A2 auxiliary error. The one-correction policy has no
priority rule, so the cosmetic error can crowd out the structural one.

### L-10 — Medium. A slightly mismatched learner turn becomes an outage, not a clarification

A2 #2 day 4. The scene was about tomorrow at 20 h; the learner refused with *"Non, désolé, je ne
peux pas aujourd'hui. Je dois travailler ce soir."* The critic rejected both attempts —
*"contradictory past events … the learner's line says they cannot come aujourd'hui/this evening — a
time mismatch"* — so the whole day returned `turn_unavailable`. In production that is `pending:
true`, no reply, no ending. A time mismatch in a comprehensible refusal is precisely what
`needs_clarification` exists for; the critic's veto pre-empts it, and the learner loses the day.

### L-11 — Low/medium. The critic earns its place, but it is expensive and inconsistent

It caught three real defects in these runs (the commitment misattribution above, a director premise
contradicting the recorded `day:3` event in A2 #2 day 7, and the `trempé·e` inclusive-dot form). It
also produced the day-4 rejection in L-10, and it accepted the authorship inversion in L-5 and every
address violation in L-6. It is 9 of 22 requests in A1 #2 — roughly 40% of the spend.

### L-12 — Low. Cost and latency are about twice the documented figures

Documented: ≈US$0.007 per scene. Measured per accepted day: US$0.0087–0.0185 (A1 #2, mean 0.0155)
and mean US$0.0226 (A2 #2), because rejected attempts are billed. Provider time per accepted day:
30–76 s (A1 #2 day 5 spent 75.7 s over seven requests). Draft calls alone run 15 s median against a
25 s per-call window and a 75 s per-operation budget, so a retry-plus-review sequence is close to
the ceiling on a slow day.

### L-13 — Low. The prompt version did not change when the prompts did

`living_story.VERSION` is still `living-story-v1` although the director, actor and critic prompts
gained the learner-address block in the working tree. Caches, pinned `content_version` values and
this report's own provenance cannot distinguish the two prompt revisions.

### Fixed while this review was running

The first deterministic run found `describe_next` hard-coding `level_band="A1"`, so the invitation
card advertised A1 to every learner. The engine owner's working tree now derives it from
`learner_level_band(user)`; `test_invitation_level_matches_the_generated_scene` asserts the fixed
behaviour for A1/A2/B1/B2 and the B2 ceiling for C1.

## 5. Reading the samples as a French teacher

**Coherence across days.** Good, where the engine let scenes happen. In A1 #2 the counter scene
carries forward correctly (day 3 "Tu es *enfin* au comptoir"), day 7 introduces a real complication
(no more café au lait) and day 8 follows the learner's own earlier proposal. In A2 #2 the party
thread runs day 1 → 3 → 9 with the address question and the bottle carried correctly, and day 9's
twist (Gus's "château" is actually in Créteil) is a genuinely good beat. Every accepted scene from
day 2 on cited real prior events. What breaks coherence is not memory but the rejection loop: days
disappear entirely (L-1, L-10), and the story then has holes it never acknowledges.

**Natural French.** The dialogue is idiomatic and in character: Margaux's *"Tu veux quoi ? J'arrive
tout de suite."*, Lila's teasing *"dépêche-toi avant qu'Augustin ne la squatte"*, Augustin's *"Fais-
nous rêver avec ta commande."* This reads like written French, not textbook French — the main
achievement of the sample. The defects are narrow and listed in L-8: one agreement error in a
character's own line (*"Désolé"* from Margaux), third-person references to the learner, and
inclusive-dot spellings.

**Level fit.** Scenes respect the word budget; replies do not (L-7). At A1 the character answers in
40-word sentences with subordinate clauses and future tense, which is above the scene the same
system just produced. At B1 the problem is the opposite: the material is A1 (L-6b). The band is
plumbed through correctly everywhere; what is missing is any pressure to *use* it.

**Usefulness of corrections.** Exactly one correction appeared in thirteen accepted days — the only
accepted day whose scripted learner made a grammar mistake (A1 #2 day 5). It was accurate,
verbatim-spanned and well explained ("Fixed the preposition+article: 'à le marché' → 'au marché'"),
and the character's reply modelled the corrected form implicitly, which is good practice. Nothing
was manufactured on a correct sentence, so the fix recorded in the earlier live review holds. The
weakness is selection, not accuracy (L-9): the auxiliary error in the same sentence was ignored. The
sample is too small to say more: the other two grammar-mistake days never produced a turn (A2 #2 day
5 was lost to L-1; the B1 run stopped first).

**Novelty vs repetition.** Counting materially different situations beyond the three authored
families (café ordering, arranging a meeting, explaining a delay): **A1 — one** (day 8, hosting a
meal, and it originated from the learner); **A2 — one** (day 9, the Créteil dilemma, on top of a
single party-confirmation thread); **B1 — one** (day 3, dinner logistics, again the learner's own
idea). Every other accepted day is a variation on ordering a drink or confirming an invitation, and
all thirteen accepted scenes across all runs happen in `le_mistral`. The engine never chose another
location, and used four of the five cast members.

**Repetitive loops.** The clearest is A1 #2 days 1–7 (L-2), where the same task survived because the
guard compares wording and the chapter rule preserves the question. A second, subtler loop is
visible in A2 #2 days 4–8, where the director kept re-proposing "confirm attendance and ask for the
address" after the learner had already done both on day 3; the critic rejected it twice as
`contradicts_past_events`. The engine noticed, but only after paying for it.

**Unsupported inferences and invented past events.** One clear case (L-5): Lila claiming she
proposed the Saturday meal the learner proposed. Otherwise the samples were disciplined — no scene
invented an event that had not happened, and days 2+ always cited real event ids. The
`unknown_story_source` rejections (L-1) are not invention; the model is citing situations it can
legitimately see, in the wrong field.

**Impossible character knowledge.** None observed live. The witness filter is enforced
deterministically (`_turn_payload`) and covered by
`test_a_character_cannot_use_an_event_they_did_not_witness`; in the live runs the addressed
character only referred to exchanges they were part of.

**Unclosed commitments.** None — because none were ever opened (L-4). Every accepted run ends with
`open_commitments_at_end: []` even after the learner promised to come at 20 h with a bottle.

**Gendered address and register.** L-6: masculine endearments and inclusive-dot forms for a
`neutral` learner. On register, the `tu`/`vous` mixing noted in the earlier review persists in a new
place — the app's own suggested answers switch between *"s'il te plaît"* (A1 #2 days 1, 3, 7) and
*"s'il vous plaît"* (A1 #2 day 2, B1 day 1) for the same characters within the same week. Lila's
*"putain"* appeared twice in six A1 days; the world bible sanctions it, so this stays a product
decision rather than a defect, but it is now measurably frequent rather than a one-off.

**Outcome consistency.** The best-behaved part of the system. In thirteen accepted days there was no
fabricated success: the off-topic answer about dogs and cats got `not_yet` with a reply that named
the miss (*"tu ne réponds pas à ma question !"*), the topic change to the Saturday meal got
`not_yet` while still welcoming the idea, and the two real orders got `met`. Resolutions and
`summary_native` matched the actual exchange every time, and `chapter_resolved` was set exactly once,
on a genuinely completed objective. Refusals could not be judged live at A2/B1 because the critic
rejected the refusal turn (L-10); refusal handling is covered deterministically instead.

## 6. Tested horizon and remaining limits

* **Deterministic:** 14 consecutive sessions for each of A1, A2 and B1, plus targeted coverage of
  every WP-14F scenario, on SQLite in one process with a fake provider. It does not prove
  PostgreSQL lock behaviour (covered separately by `scripts/verify_story_engine_pg.py`), frontend
  integration, or anything about generated prose.
* **Live:** nine consecutive days (A1), ten (A2), four (B1), all synthetic, one model
  (`gpt-5-mini`), one prompt revision, `--attempts 2`. Two further 14-day attempts produced zero
  scenes and are reported as such. No fourteen-day live run exists yet; L-1 must be fixed before one
  is worth paying for.
* **Not covered at all:** real learner accounts, cohort behaviour, cost at scale, image/panel
  continuity, voice input, and the frontend reader against these scenes.
* This review says nothing about indefinitely unique storytelling. Within the horizon above, the
  engine keeps one coherent world and honest outcomes; it does not yet produce varied situations
  (L-2), reliable generation (L-1), or level-appropriate material at B1 (L-6b).

## 7. Reproducing this

```
# Deterministic (no credentials, no network)
venv/bin/python -m pytest -q tests/test_living_story_longitudinal.py tests/test_living_story.py
venv/bin/ruff check scripts/longitudinal_story_review.py tests/test_living_story_longitudinal.py

# Live sampler — makes no request without --live
venv/bin/python scripts/longitudinal_story_review.py
venv/bin/python scripts/longitudinal_story_review.py --level A1 --live --attempts 2 --max-requests 60
venv/bin/python scripts/longitudinal_story_review.py --level B1 --live --attempts 2 --days 6 --max-requests 20
```

Artifacts (not committed): `var/reviews/atelier-longitudinal-{A1,A2,B1}.json`,
`var/reviews/atelier-longitudinal-{A1,A2}-instrumented.json`,
`var/reviews/wp14f-control-three-scenes.json`, and the raw run logs `var/reviews/run-*.log`. Each
report contains every request (stage, model, tokens, cost, latency, raw model content) and every
day's full scene, learner line, turn, event and open commitments.

## 8. Acceptance judgement

WP-14F's deterministic obligations are met: the coverage table in §2 is complete and green, and the
engine's state machine, provenance and isolation hold up over fourteen simulated days per level.

WP-14F's generation obligation is **not** met yet. On the live evidence: **34 of 47 non-skipped
simulated days produced no usable scene**, two whole 14-day runs produced none at all, five of six accepted A1 days were the
same task, a B1 learner got A1 content, no commitment was ever recorded, and one reply handed the
learner the answer key. L-1, L-2, L-3 and L-6b should be fixed and a fresh live 14-day run paid for
before WP-14 is called complete.
