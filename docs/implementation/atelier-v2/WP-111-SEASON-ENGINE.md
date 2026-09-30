# WP-111 · La bible de saison — season 1 as something the engine plays

*2026-09-30. The owner-approved bible (`docs/story/season-1/`) is the source of truth;
this is how the engine reads it. Brief: `HANDOVER-FEUILLETON-REBUILD-2026-09-30.md`.*

## 1. What exists now

| Piece | Where | What it does |
|---|---|---|
| The season format | `app/services/season/format.py` | Typed schema: tentpole days as ordered movements (`panel`, `turn`, `solve`, `hook`, `include`), text at A2 with B1 where it differs, `native` en/de translations, `neutral` date-free wordings, conditions on flags/path/band |
| Season 1 | `app/data/season/s1/` | `season.json` (segments = the bible's §8 calendar, the §6 flag table, cast and registers, Lila's §7 gates, §9 writing rules), `t1.json`…`t8.json` (every tentpole, both days, every variant), `gaps.json` (`09-entre-les-episodes.md`), `world.json` (the director's world: the new cast, places, situation) |
| Fidelity | `app/services/season/fidelity.py`, `scripts/season_check.py` | Every French line of every tentpole script must be carried verbatim (102 lines in T1 alone). Owner-decided departures are listed in `DEVIATIONS` (today: S-9's Camille line) |
| The calendar | `app/services/season/clock.py` | S-12: the season moves one day per day the learner *finishes*; gaps flex ±1 so a tentpole's Day A lands on the weekend when possible (a Friday Day A waits a day; a gap ending on Sat/Sun ends a day early) |
| Flags and Lila | `app/services/season/flags.py` | Set by replies, cards and `state_out`; derived: `s1.promised_to`, `s1.plan`, `s1.berlin_told_how`, `s1.ending`, `s1.painting`, `s1.lila_path` (from gate signals, never accuracy) |
| A tentpole day | `app/services/season/page.py`, `runtime.py` | The day resolved for band, language and flags → the page (JSON, stored on the scene as `script_payload.season_page`). No model call |
| A tentpole turn | `app/services/season/turns.py` | A small classifier (`ReplyChoice`) says which of the bible's likely replies the learner *expressed*; a deterministic matcher stands in without a model. The reaction is always the bible's lines |
| A generated day | `app/services/season/director.py` | The gap's brief for the director (threads, facts from flags, small moments, complications, must-nots, premises, today's scheduled moment), the deterministic forbidden-reveal guard, and the WP-114 story critic |
| Tooling | `scripts/season_jump.py`, `tests/test_season_one.py` | Put a test learner on any season day; the 59-day life; the owner's transcript (`SEASON_REPORT=<path>`) |
| Switch | `ATELIER_SEASON_SCRIPT` | `"s1"`: new lives begin on season 1. Empty (default): the generated serial as before. A life already under way keeps its story |

## 2. How a day runs

- **Tentpole day.** `generate_scene` → `tentpole_brief`: the authored page, instant. `bind_journey`
  publishes it (the tentpole opens its own chapter on Day A and closes it on Day B; each panel
  opens on its own place's plate; no per-learner art — authored pages are drawn once, offline).
  `evaluate_turn` routes each reply; `settle_resolution` applies the routed replies' flags, Lila's
  gate signals, the unplayed solves' defaults, and on Day B the tentpole's `state_out`.
- **Generated day.** The director reads `season_script.brief`. A draft that makes a forbidden
  reveal is refused with the reason (hard). A draft that skips today's scheduled moment is asked
  once more, then served and the moment is owed to the next day (soft: a season never stalls).
  The story critic reads the accepted draft: a refusal buys one retry; a second refusal is
  accepted and logged (`journey_story_critic_override`); every reading is a
  `journey_story_critic_review` row (the WP-114 metric).
- **Settling.** Every day appends to the played log (`live["season_script"]["played"]`), which is
  the learner's own day count.

## 3. Until WP-110: the projection

Today's steps are scene → reply → ending. Until the page reader lands, a tentpole day is shown as:
the panels before the first turn (the scene); every turn of the day in one conversation, each
reaction and the lines leading into the next question said in the thread, other speakers named
(«Margaux : Elle prenait ça.»); the day's hook as the ending. Solves are not posed yet (WP-112):
the story takes the solve's default (or the flag's). The full page is already stored on the scene.

## 4. Interpretations (owner to confirm)

*Owner, 2026-09-30: 1–3 approved. A real-model read of the first ten days approved with a US$1 cap.*

1. **S-9, Camille.** T1 Day B opens with the learner's own balloon, «Vous êtes son fils ?» /
   «Vous êtes sa fille ?», and Camille answers «Son petit-fils.» / «Sa petite-fille.» (two lines
   I wrote). Until WP-112 poses it, a seeded 50/50 stands in.
2. **Lila's path.** Two romance-leaning expressions → romance; the latest leaning expression
   decides between romance and friendship; «open» reads the friendship lines.
3. **S-12.** Diegetic dates stay (a story set in Nov–Jan). Only holiday days switch to a neutral
   wording away from the holiday (Réveillon 26 Dec–3 Jan, Noël 18–27 Dec) — and no neutral
   wordings are written yet (T7, gap 6).
4. **The ending.** `keep` after «kept» is «Laisser partir» (the §6 fold); `sell` after a signed
   lease is «Laisser partir» (S-10). T8's ending 3 has no «keep fold» lines in the bible.
5. **T4 P9.** Nobody trusted or Gus trusted → Lila stands beside you (Gus is the accuser).
6. **Defaults of unplayed solves** (until WP-112): letter → Personne; enquêtes → the flag
   default (found by Lila); key → no; Convaincre → not persuaded; T4 photo → the wall; T6 →
   Marchand only (Margaux nudges toward it); T7 flat → sell; letters → read right.
7. **The authored café fallback** (WP-69) still stands in when the director fails a generated
   day. It is not a season day: the season does not advance, and tomorrow retries the same day.
8. **After day 59.** Season 2 is not re-cut yet (the brief says «not now»): the generated serial
   continues in the season-1 world.

## 5. The real-model read of the first ten days (2026-09-30)

`WP-111-FIRST-10-DAYS-LIVE.md`: gpt-5-mini (director, critic, reply lanes), A2.1, English
chrome, US$0.37 in all (cap US$1: a 3-day pipeline check at US$0.04, then the 10 days at
US$0.32 in 109 calls). Replay: `SEASON_REPORT_LIVE=1 SEASON_REPORT_MAX_USD=… SEASON_REPORT=…
pytest tests/test_season_one.py -k owner` (the key is read from `.env`, never printed).

- **Tentpoles** (days 1–2) are the bible, as written. No model call.
- **Generated days** stage the gap's schedule: g1.1 le billet, g1.2 Romy enquête, g1.3 la
  tradition du comptoir, g1.4 la faveur (la même chose), g1.5 la soupe de Marin. The
  director's checklist names a real change each day. The critic refused once and was
  overridden once.
- **Three days lost** (5–7): g1.3 failed twice on `invalid_story_output` and once on a
  critic refusal whose retry a guard refused. The café fallback stood in; the season
  waited (as designed), and day 8 played g1.3.
  - *Fixed:* the draft the critic refused is served when the retry it bought fails the
    guards (logged as `journey_story_critic_override`). The critic's readings are
    recorded even on a lost day. Every lost generation now logs its refusal hints.
  - The two `invalid_story_output` reasons were not logged then; finding them needs one
    more paid day.
- **Reply lanes.** Three of seven generated days end on the authored «X doit partir avant
  de répondre» (WP-58): the lanes' corrections wrote «perdu(e)» for a learner whose gender
  the story does not know, and the release guard refused them. This is a reply-lane
  finding, not a season one.
- **Self-repair.** «Pardon, On commence maintenant ou quand ? ?» — the forced choice kept the
  sentence's own «?» and capital. *Fixed* (`journey_conversation._mid_sentence`).
- **Level.** The director still slips B1 connectives into A2 lines («lorsque», «afin de»).
  The coverage guard observes them but does not enforce.
