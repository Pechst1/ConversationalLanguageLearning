# Atelier — Package O: L'or (the currency), L'Ardoise and the editions

Owner ask (Vincent, 2026-10-31): an XP economy that rewards *performing well*, is hard to
earn and hard to game, becomes a currency, feeds a leaderboard where learners compete for a
rare piece of the week and of the month (a pin on the coat, a new pencil), is fun and
well designed in the existing design language, triggers dopamine, and works in the 2D app
and in Le Quartier (3D).

The visual design, with live prototypes of every reward moment, is the companion artifact
[«L'or de l'Atelier»](https://claude.ai/artifact/Rb3Ruya2ptBMfxwsCp9U1x). Its mint function
implements the base values and rules of §4.1 and §4.2, so the page doubles as a worked
example of the mint table. This file is the engineering spec the implementation PRs follow.

## Summary

- **One currency, l'or.** Its unit is the *feuille d'or* (gold leaf), drawn as the house
  mark's yellow square, the shape the design system already reserves for reward. Code name
  `gold` (`or` is a Python keyword).
- **It pays for evidence, never for activity.** Gold is minted only from a *checked*
  verdict in the evidence ledger the app already keeps (`EvidenceKind`, server-recorded
  `AssistanceLevel`, idempotent source keys). Production pays more than recognition,
  unaided more than aided, a delayed recall double. Each word or rule pays once a day, at
  its best. A rule *held* («Tenue», 14+ days, delayed recall) is the big prize.
- **It is spent at La Papeterie** (pins, pencils, notebook covers, seal inks, studio
  objects) and on **la dorure**: gilding a piece you own. Nothing can be bought with money.
- **Rare pieces are printed in editions.** Each week and each month has a piece. Everyone
  who has a full week gets the *tirage courant*; the top three of each table get the
  numbered, gilded *tirage de tête*; the month's best gets the *hors commerce* piece that is
  never reprinted.
- **L'Ardoise** is the leaderboard, chalked on Le Mistral's wall: small matched tables,
  settled gold only, no demotion, no countdown, a solo mode with personal records.
- **One record, two renderings.** Every piece is one catalogue row that 2D draws as SVG
  and 3D draws as a mesh, the way `AvatarConfig` already drives both avatars.
- **Shadow first.** The ledger runs silently for two weeks to calibrate the numbers below
  against real play before anything is shown.

---

## 1. What exists today (and what this package builds on)

| Exists | Where | What this package does with it |
|---|---|---|
| Evidence classes: `RECOGNIZED`, `PRODUCED_SUPPORTED`, `PRODUCED_INDEPENDENT`, `NOT_YET`, `UNSCORED` | `app/services/journey_contracts.py` `EvidenceKind`; `journey_learning.classify_evidence` | The mint table is keyed on them. |
| Assistance recorded on the server, never self-reported | `journey_contracts.AssistanceLevel`, `strongest_assistance` | Assistance multipliers. |
| Task outcomes `met` / `partially_met` / `not_yet` / `unscored` | `journey_contracts.TaskOutcome` | Partial pays half; unscored pays nothing and costs nothing. |
| Idempotent evidence keys | `journey_contracts.evidence_source_key`, `effect_source_key` | Gold entries reuse them, so a retry never pays twice. |
| La Forge staircase, evidence caps and massed-practice decay | `app/core/forge.py` (`Rung`, `MASSED_WEIGHT_DECAY`, first success per rule per rung) | «Le meilleur du jour» follows the same idea: repeats add nothing. |
| Unchecked answers never count | `core.forge.Verdict.checked`; `forge.verdict_from_attempt` (`assessment_status`) | Pending gold until the relecture lands. |
| «Tenue»: held = free use on two days ≥ 7 apart + an unaided spaced item ≥ 14 days after the introduction and ≥ 20 h after the last contact | `app/services/concept_life.py` | The biggest regular prize, and the 20 h gap defines the ×2 delayed recall. |
| Released grades corrected later | `journey_learning.correct_released_grading` | Voids pending gold for withdrawn targets. |
| Give-ups and copies are not attempts | `journey_learning.attempted_answer`, `_free_sentence_copies_shown`, `season.turns.reply_is_not_french` | Pay nothing. |
| Package I collectibles: logo tokens (credit 1–4), gilt seals, story seals, plates | `app/services/atelier_rewards.py`, table `atelier_collectibles` | Owned pieces live in the same table (new kinds). See §12 for the consolidation. |
| Avatar pieces earned by achievements, drawn in 2D and in 3D | `web-frontend/lib/avatar.ts` (`PINS`, `EARS`, `REWARDS`), `components/avatar/avatar-art.tsx` (`Pin`, `crayon`), `lib/quartier/cast3d/avatar.ts` (`pin()`, the pencil behind the ear) | Weekly and monthly pieces are new options in the same slots. |
| The learner's studio on the sixth floor | `web-frontend/lib/quartier/world/rooms/user_apartment.json` (`things`) | Studio pieces become `things` with French `look`/`did` lines. |
| «No XP is awarded: nothing on screen spends or shows it, and a number that only grows is not a reward.» | `app/services/achievement.py` docstring (WP-79) | Agreed. Gold is spendable, explained line by line, and ranks a week. |
| Legacy XP still written to `users.total_xp` | `api/v1/endpoints/stories.py::_calculate_story_xp` (5 per message, +10 for ten words, +30 % «sans faute»), `session_service._apply_user_xp`, `audio_session_service` | **Not reused.** It pays for length and participation: ten words of anything earn 19. New ledger, clean break. |

## 2. Design laws

1. **Gold pays for evidence, never for activity.** No gold for opening the app, reading,
   pressing Continue, minutes, message length, streak days, self-rated cards or story
   progress (story seals keep that).
2. **Harder French pays more.** Production over recognition, unaided over aided, delayed
   recall over fresh, a held rule over a practised one.
3. **Spacing beats grinding.** Each target pays once a day at its best; a soft daily
   ceiling; the largest sums come from coming back tomorrow and remembering.
4. **Never a loss.** No gold is taken for a mistake, a missed day or the end of a week. No
   demotion, no stake, no countdown, no «you were overtaken» push. The only debit is the
   learner's own purchase. (Package G and I guardrails stand.)
5. **The server decides.** Amounts are computed server-side; the client never posts an
   amount.
6. **Settled before it counts.** Model-graded gold is pending until the verdict is
   checked. L'Ardoise counts settled gold only.
7. **Rarity by edition, not by chance.** No random drops for money, no loot boxes. The one
   surprise («Joli !») depends on the quality of an answer, not on dice.
8. **One record, two renderings.** 2D and 3D draw the same catalogue row.
9. **Never for sale.** No real money buys gold or pieces, whatever a subscription later
   sells.
10. **Every leaf explains itself.** Each entry carries its reason («Production libre ·
    sans aide · 1ʳᵉ fois aujourd'hui : 5»). Informational feedback supports competence;
    controlling rewards undermine it (Deci, Koestner & Ryan 1999).

## 3. The currency

- **Name.** French «l'or», unit «feuille d'or», plural «feuilles d'or». English «gold
  leaf», German «Blattgold». A gilder's atelier works in leaf; it is sold in booklets of
  25, so the wallet is «ton livret».
- **Glyph.** The yellow square of the house mark with its press: face `--av2-yellow`,
  press `--av2-yellow-deep`, corner radius 2 (as the Seal's forms). In flight the press
  drops away and the square turns like a leaf.
- **States.**

| State | Code | Shown as | When |
|---|---|---|---|
| à l'épreuve (proof) | `pending` | dashed outline square | the verdict is provisional (free production's instant local check) |
| tiré (printed) | `settled` | filled square | the key graded it, or the model's verdict landed and is checked |
| pilonné (pulped) | `void` | the dashed square fades | a pending verdict came back `not_yet`, or the critic withdrew it before it settled |

Settled gold stays settled. If the critic later withdraws a success that was ours to get
wrong, the learning schedule gives the advance back (`correct_released_grading`) but the
gold stays: the learner never sees a balance fall because the grader erred. The only
exception is abuse (see §6, prompt injection), which voids the entry and flags it.

## 4. The mint table (rule version `gold-v1`)

### 4.1 Base values, in feuilles

| Evidence (server) | Formats | Pays |
|---|---|---|
| Recognised, checked correct | choice, who_said, listen_tap, match_pairs, classify, tiles, unscramble; Forge recognise / discriminate / build | 1 |
| Typed recall, checked correct | short_answer, transform, dictation; Forge transform | 2 |
| Guided production, unaided | Forge produce (a model and a frame are given) | 3 |
| Free production, unaided | a reply turn of the scene `met` (objective-level record); Forge free_use | 5 |
| A Courrier letter accepted, unaided | `missions` verdict `accepted` | 8 |
| A repair: a slip turned right in the repair step | journey repair, Forge reprise | 1 |
| `not_yet`, `unscored`, a give-up, a copy, a reply not in French | | 0 |

The ladder extends the one the logo tokens already weigh by (`ATTEMPT_CREDIT`: recognize
1, transform 2, sentence 3, produce 4).

### 4.2 Rules

- **R1 · Le meilleur du jour.** Each target (word, rule, error) pays once per local day,
  at the value of its best evidence. A better evidence later the same day pays the
  difference: recognising a rule (1), then rewriting with it (2, pays +1), then using it
  freely (5, pays +3). A target posed again in the same format pays nothing. Reply turns
  and letters are paid per turn, up to the scene's `max_turns`: a turn pays once, as its
  own unit, and lifts the day's best of every target it shows to «libre» without paying
  them again (no double pay for one sentence).
- **R2 · Aide.** Server-recorded assistance: none ×1, hint ×½, translation ×½, suggested
  response 0, solution 0. Halves round down.
- **R3 · Partiel.** `partially_met` or an accent slip pays half (production never below 1).
- **R4 · Rappel différé ×2.** A correct, unaided spaced item answered at least 20 hours
  after the learner's last contact with the target pays double
  (`concept_life.HELD_SPACED_GAP_HOURS`).
- **R5 · Posé en dessous ×½.** An item posed below the rule's level (a warm-up, a contrast
  partner) pays half (`core.forge.step_level`, #402).
- **R6 · Vérifié seulement.** Unchecked is pending; `unavailable` and `unscored` pay
  nothing. Never negative.
- **R7 · Premier essai.** First submission only, except the repair step.
- **R8 · Le plafond du jour.** Counted on the day's earned gold before the plafond: full
  rate up to 90 a local day, half rate from 90 to 150, nothing past 150, so a day never
  pays more than 120. Milestones and bonuses sit outside it. Only a binge reaches it (§5).

### 4.3 Milestones (once each, idempotent)

| Milestone | Trigger (code) | Pays |
|---|---|---|
| Règle tenue | `UserGrammarProgress.held_at` written the first time (`concept_life`) | 25 |
| Capacité confirmée | a capability reaches `CapabilityState.USED_AGAIN_LATER` (two independent uses ≥ 24 h apart) | 10 |
| Numéro spécial réussi | a level épreuve passed (WP-94) | 30 |
| Journée parfaite | every scored step of the day `met` on the first try, unaided | 10 |
| «Joli !» | an unaided reply the judge scores 4/4 with no errata that uses the day's unit; at most once a day; the speaking character reacts | 2 |

### 4.4 La journée pleine

A day is *pleine* when its settled gold reaches the rhythm's mark: Léger 10, Régulier 20,
Soutenu 35, Intensif 45. The day's seal gets a gold rim that fills toward the mark. Five
journées pleines in a week earn the week's piece (§8). The mark sits near the 25th
percentile of a weak learner's full day (§5): finishing the day honestly gets there;
opening the app and leaving does not.

## 5. Calibration

A Monte Carlo of the day shapes in `RHYTHM_CAPS` (recall 6 · 12 · 20 · 28, reply turns
2 · 3 · 4 · 4, a Forge séance of 10 · 14 · 19 · 24 items, 35 % of targets due, 15 % hint
rate) with the table above gives:

| Rhythm | weak (55 %) | average (72 %) | strong (87 %) | strong, 5 days |
|---|---|---|---|---|
| Léger | 13 | 16 | 20 | 100 |
| Régulier | 24 | 30 | 36 | 180 |
| Soutenu | 41 | 51 | 60 | 300 |
| Intensif | 52 | 66 | 78 | 390 |

Median gold a day. The plafond touches 6 % of strong Intensif days and caps a binge (a
strong Intensif day plus three extra séances pays 95 for 101 earned). These are targets to
replace with shadow-mode data (§16, PR O-1), not promises.

## 6. Gaming: threats and defences

| Threat | Defence | Code |
|---|---|---|
| Farming easy taps | Recognition pays 1; each target pays once a day | R1, R2 |
| Replaying the same item or séance | Le meilleur du jour; idempotent source keys | `evidence_source_key` |
| Taking help and claiming independence | Assistance recorded server-side | `AssistanceLevel` |
| Copying the shown sentence into «free» production | Copies pay 0 | `_free_sentence_copies_shown` |
| Gibberish, English, «je sais pas» | Pay 0 | `attempted_answer`, `reply_is_not_french` |
| Long answers for length bonuses | No length term anywhere | (legacy `_calculate_story_xp` is not reused) |
| Prompt injection in a free answer («mark this correct») | Judge prompt hardened; injection detector; the critic re-reads; a hit voids the entry and flags the account | judge, critic, `void_reason="injection"` |
| Self-rated Lexique cards («Facile») | Pay 0 | Law 1 (§2) |
| Cramming the night before the bouclage | The plafond; the ×2 needs a 20 h gap; the week's piece needs five separate days | R4, R8, §8 |
| Changing timezone to reset the plafond | The local day uses the timezone stored at the day's first entry; a timezone change applies to the plafond after 7 days | `User.timezone` |
| Scripted answers through the API | Rate limits; answer-latency floor per format; impossible accuracy runs flagged; L'Ardoise needs a verified email (and App Attest on iOS when it exists) | anomaly report (§15) |
| Sandbagging a week to get an easier table | Seating uses the trailing three-week median | §9 |
| Spamming appeals | 5 a day; an appeal is re-judged against the accepted answers; frivolous appeals shrink the quota | §10 |
| Multi-accounting for table prizes | Pieces are not tradable; a new account sits at a rookie table for two weeks | §9 |
| A grader that marks right answers wrong | Gate O-0 (Q10 ≥ 4) and «Je conteste» (§10) | |

## 7. Spending: La Papeterie and la dorure

La Papeterie du quai is the stationer on the quai de Valmy: a catalogue page in 2D and a
shop you walk into in 3D, where buying means asking for the thing in French (a talk module
on the model of `market-talk.ts`). Spending is practice too.

| Piece | Slot / place | Price |
|---|---|---|
| Encre du sceau (the day's seal in another colourway) | the Seal | 120 |
| Pin's du catalogue | avatar `pin` | 150–250 |
| Crayon (rouge et bleu, Bauhaus, porte-mine, charpentier) | avatar `ears`; your equipped pencil also draws the caret and underline of the answer field | 300–500 |
| Carnet (a cover for the Cahier) | the Cahier header; the table in the studio | 400 |
| Studio: plante 600 · lampe de bureau 900 · affiche du Mistral 900 · étagère 1 500 · tourne-disque 1 500 · stylo-plume 3 000 | `user_apartment` `things` | as listed |
| La dorure: gild a piece you own (gold material in 3D, gold fill in 2D) | any owned piece | the piece's price, at least 200 |
| 2ᵉ tirage of a past weekly piece | | 400 |

A strong Régulier learner (≈ 180 a week) buys a pin in a week, a pencil in two or three, a
studio object in one to two months. That is the intended pace: not easy, never out of reach.

Gold never stands for euros: in Le Quartier's market the learner pays in pretend euros,
because the prices are the lesson (`lib/quartier/market.ts`).

## 8. The editions: la pièce de la semaine, la pièce du mois

| Edition | Who gets it | Mark on the piece |
|---|---|---|
| **Tirage courant** of the week's piece | everyone with five journées pleines, Monday to Sunday | the week («Semaine du 2 nov.») |
| **Tirage de tête** of the week's piece | the top three of each table at the bouclage (solo: a new personal best week) | numbered «Nº 4 / 18», gilded |
| **2ᵉ tirage** | anyone, at La Papeterie, after the week, for 400 | «2ᵉ tirage», no number |
| **Tirage courant** of the month's piece | three weekly pieces in the calendar month, any edition | the month |
| **Hors commerce** of the month's piece | the month's first at each table (sum of the month's weekly settled gold); solo: a personal best month | «H.C.», never sold, never reprinted |

The week's piece is announced on Monday as a brève on La Une, with the episode it comes
from («Le pin's cigale, d'après la clé d'Odile»). Monthly pieces are larger: a pencil, a
hat, a studio object, one of Lila's paintings for the studio wall. Achievement rewards
(`REWARD_SLOTS`) join the catalogue as hors commerce pieces: earned, never sold.

Missing a week's first edition costs nothing but the number: the object comes back as a
2ᵉ tirage. That keeps rarity without a countdown.

## 9. L'Ardoise (the leaderboard)

- **Tables.** Up to 20 learners per table, re-seated every Monday by the trailing
  three-week median of weekly settled gold, so the race is close. New learners sit at a
  rookie table for two weeks. No leagues to climb or fall from.
- **Metric.** Settled gold earned Monday 00:00 to Sunday 23:59, Europe/Paris (the paper's
  bouclage). Results are frozen Monday 06:00, after the nightly critic and live walk.
- **Display.** Rank, the learner's face (their avatar), display name (first name and
  initial, or a pseudonym), the week's gold, the pieces they wear. Shown: the top five
  and you with two neighbours each side; the full table on tap. A dashed line under the
  third row reads «Tirage de tête». Comparison with near neighbours drives engagement more
  than an absolute board, and hiding the bottom protects the people there (see Sources).
- **Copy.** «Bouclage dimanche soir». No clock, no «danger zone», no push when someone
  passes you.
- **Solo («Ton ardoise»).** Off-table by choice (Réglages → «Jouer seul») or because the
  learner is alone. The rows are your last eight weeks. Gus bets on you every Monday («Deux
  cafés que tu ne fais pas 240 cette semaine»): the target is your best week plus 10 %;
  beat it and he pays 20 and a line. Losing his bet costs you nothing.
- **Small population.** Fewer than eight active learners: one table for everyone. One
  learner: solo. (Today that is Vincent; Phase 4 of the plan brings 10–20.)
- **In 3D.** Margaux chalks the table's top five and you on the slate at Le Mistral.

## 10. «Je conteste»: appeals

The feedback sheet of a wrong verdict carries «Je conteste». The answer is re-judged by
the stronger judge against the accepted answers (#174). If the verdict flips, the learning
record is corrected, the gold is minted (settled), and the case becomes a gold transcript
for the nightly loop. Five a day. A hard currency on an unfair grader would make people
angry; appeals make it fair and turn the anger into grader data.

## 11. The reward moments

Intensity follows the peak–end rule: small and calm per answer, the peak at the end of the
day, the anticipation on Monday. Every motion has a Reduce Motion fallback that keeps the
information and drops the movement. Haptics through `@capacitor/haptics`, gated on
`isNativePlatform()`.

| Moment | 2D | 3D | Haptic |
|---|---|---|---|
| **Le grain** (each paying answer, ~400 ms) | a small yellow square lifts from the answer and lands in the counter pill; the counter's digit rolls once | leaves rise in world space and drift to the HUD counter | light impact |
| **Rappel différé ×2** | the square splits in two: «Tu t'en souvenais.» | the same split | light, twice |
| **«Joli !»** | the speaking character's face reacts (the existing feel faces); «Joli !» +2 | the character's head turns and nods | none |
| **Le tirage du jour** (day end, the peak, ~3 s) | the Seal presses (`av2-seal-press`); the day's leaves flutter down and gild its rim toward the journée-pleine mark; the counter rolls to the new total; «Or +48 · Journée pleine (4 / 5)» and «Tu passes 3ᵉ à ta table» | in the studio, the numbering machine on the desk turns over | success pattern |
| **Le pli du lundi** (weekly) | a sealed envelope from La Papeterie on La Une; tap: the house seal breaks, the card slides out, the piece turns in, the edition stamp lands; «L'épingler» puts it on your avatar | your character wears it from then on | medium impact on the stamp |
| **Le palmarès du mois** | Le Papier prints the month's table winners (names opted in); Lila hands over the month's piece in a cameo (`offer.tsx`, «montre») | Lila hands it over at Le Mistral | medium |
| **Règle tenue** | the rule card's edge gilds, the Seal gains its ring (WP-S7), +25 | | success |
| **Un achat** | the piece is wrapped in paper and string, handed over; the counter rolls down, calmly | the papetière wraps it at the counter | light |

## 12. Consolidation with what exists

Today a learner meets the daily seal and its rings, logo tokens, the almanac's plates,
achievements with avatar rewards and the saucer streak. Adding gold beside them would make
six reward systems. Decided by Vincent on 31 Oct 2026 (reversible):

- **Gold** is the one currency.
- **Pieces** (pins, pencils, objects) are what you own. Achievement rewards become pieces.
- **The Seal and the saucers** mark your days. The Seal gains a gold rim; the saucers stay.
- **Logo tokens and plates** keep minting as history (the code stays), but stop being
  shown as a currency. The workshop's compose step gives way to La Papeterie; existing
  plates stay in the almanac.

## 13. One record, two renderings (2D and 3D)

- **Catalogue.** `app/data/papeterie/catalogue.json` (id, kind, slot, price, edition
  schedule, names fr/en/de, art key) mirrored by `web-frontend/lib/papeterie.ts`, held
  together by a contract test (as `tests/test_avatar_contract.py` holds `REWARDS`).
- **Avatar pieces.** New values in `PINS` and `EARS`; `isLocked` generalised from
  achievement rewards to owned pieces. Each value gets a 2D drawing in
  `avatar-art.tsx` and a 3D branch in `cast3d/avatar.ts` (today's `pins_atelier` and
  `crayon` are the templates). A gilded piece swaps the material to `GOLD`.
- **Studio pieces.** New `things` kinds in `lib/quartier/interior.ts`, placed by the
  server's owned list into `user_apartment`, each with French `look` and `did` lines.
- **The Mistral slate.** A slate mesh at Le Mistral with a canvas texture: the table's top
  five and you, in the app's sans in chalk white.
- **Gold leaf in 3D.** Instanced double-sided quads, `MeshStandardMaterial` in
  `--av2-yellow` with metalness ≈ 0.85 and roughness ≈ 0.35, a sway-and-turn fall.
- **Earning in 3D** needs nothing new: Le Quartier posts answers to the same endpoints
  (Phase 1, #366/#367), so the server mints the same gold.

## 14. Visual tokens (added to `atelier-v2.css`, scoped under `.av2`)

- `--av2-gold`: `var(--av2-yellow)`; `--av2-gold-deep`: `var(--av2-yellow-deep)`;
  `--av2-gold-sheen`: a 115° highlight swept once across a settled square.
- Pending: a 1.5px dashed `--av2-yellow-deep` outline, no fill (as SealMini's dashed
  states).
- The counter pill: `--av2-card` ground, `--av2-r-pill`, the square glyph, Instrument Sans
  600, tabular numerals; digits roll 180 ms with a 40 ms stagger.
- Edition stamps: sharp-cornered (stamps stay sharp), sentence case: tirage de tête in
  `--av2-red`, tirage courant in ink, 2ᵉ tirage in `--av2-blue`, hors commerce in gold.
- Item cards: `--av2-r-card`, the piece drawn flat like the cast (flat fills, no outlines,
  darker and lighter tones of one colour), its name the one Garamond italic line.

## 15. Data model

**`atelier_gold_ledger`** (append-only)

| column | type | notes |
|---|---|---|
| id | uuid pk | |
| user_id | fk users, indexed | |
| amount | int | positive for earning, negative for spending |
| entry_kind | str | `earn` · `milestone` · `bonus` · `award` · `spend` · `adjust` |
| state | str | `pending` · `settled` · `void` |
| source_kind | str | `journey_target` · `journey_reply` · `forge_item` · `letter` · `milestone` · `appeal` · `purchase` · `gilding` |
| source_key | str | unique with `user_id`. Targets: `gold:{kind}:{id}:{local_date}:{rank}` (one row per rank reached, so a top-up is its own row); replies: `effect_source_key(journey, "gold:reply:{step}")` |
| target | jsonb | `{kind, id}` or null |
| evidence | jsonb | evidence_kind, assistance, outcome, format, rung, delayed_recall, below_level |
| breakdown | jsonb | base, multipliers, plafond factor: the learner-facing explanation |
| rule_version | str | `gold-v1` |
| local_date | date | the learner's local day |
| week_id | str | ISO week in Europe/Paris, `2026-W45` |
| created_at, settled_at, voided_at | ts | |
| void_reason | str | `not_yet` · `withdrawn` · `injection` |

Indexes: `(user_id, local_date)`, `(user_id, week_id, state)`, unique `(user_id, source_key)`.

**`atelier_gold_balance`**: user_id pk, balance, earned_total, spent_total, updated_at.
A cache; recomputable from the ledger.

**`ardoise_seats`**: id, week_id, table_id, user_id (unique per week), seeded_median,
final_gold, final_rank, edition_awarded, display_name_snapshot.

**Owned pieces** reuse `atelier_collectibles` with kind `piece`, metadata `{item_id,
edition: courant|tete|hors_commerce|retirage|catalogue, serial_no, edition_size, week_id |
month_id, gilded}`, source kinds `award_week` · `award_month` · `purchase`. Its unique
`(user, source_kind, source_ref, kind)` makes awards and purchases idempotent.

## 16. API

| Route | Returns / does |
|---|---|
| `GET /api/v1/gold` | balance; today (settled, pending, plafond state, journée-pleine mark); week (gold, journées pleines n/5, rank, table size); the week's piece and progress |
| answer responses (journey step, forge item, letter) | `gold: [{amount, state, reason, breakdown}]`, like `minted_collectibles` today |
| `GET /api/v1/gold/ledger?week=` | entries with their reasons («D'où vient ton or») |
| `GET /api/v1/ardoise` | the table (top five, you ± 2), the tirage-de-tête line, the bouclage date; solo rows and Gus's bet when solo |
| `GET /api/v1/papeterie` · `POST /papeterie/buy {item_id}` · `POST /papeterie/gild {piece_id}` | catalogue and owned pieces; buying and gilding with an idempotency key; 409 with the shortfall |
| `POST /api/v1/appeals {step_id \| attempt_id}` | re-judge asynchronously; the result arrives as a corrected verdict and a ledger entry |

Celery beat (the worker already runs `-B`): `ardoise_close_week` Monday 05:30
Europe/Paris (freeze, rank, award editions, queue the pli), then `ardoise_seat_week`;
`ardoise_close_month` on the first Monday after a month ends. All idempotent.

## 17. Where gold is minted

- Journey targets: `journey_learning.apply_learning_evidence`, after `_credit_for` for each
  observation, in the caller's transaction (`commit=False`, like
  `mint_daily_journey_keepsake`).
- Reply turns: `journey_learning._record_objective_evidence`.
- La Forge: the evidence decision of each answered item; `ForgeService.amend_attempt`
  settles pending gold when the relecture lands.
- Letters: the mission completion path in `app/services/missions.py`.
- Milestones: `concept_life` (held), `journey_capabilities` (used again later), the
  level épreuve.
- Withdrawals: `correct_released_grading` voids pending entries of withdrawn targets.
- A pure function `app/core/gold.py::mint(observation, day_state) -> GoldEntry | None`
  holds the table, so a simulation, the tests and the service run the same code (the
  way `app/core/forge.py` serves the séance and the simulation).

Mode flag `ATELIER_GOLD_MODE = off | shadow | live`. Shadow writes the ledger and the
nightly report, and shows nothing.

## 18. Metrics for the nightly loop

The north star stays the plan's: minutes of the learner's own French, words read and heard,
live Q4 / Q10 / Q20 / Q21. Gold has to move those, not itself. Reported nightly:

- gold a day by rhythm; share from production (target ≥ 60 %); share from delayed recall;
  plafond hits (target < 10 % of days); journées pleines a week;
- appeals a day and the share overturned (the grader's false-negative rate);
- rushing signals: time per item falling while accuracy at the same rung falls; a rise in
  recognition-only days;
- with real learners (Phase 4): return after 1, 7 and 30 days, gold UI on vs off.

## 19. Gates and PRs

| PR | Contents | Gate |
|---|---|---|
| O-0 | No code: the grader holds live Q10 ≥ 4 on three nights in a row (#174, #393). | before anything is shown |
| O-1 | Ledger, migration, `app/core/gold.py`, hooks (§17), mode flag, nightly report. No UI. Two weeks of shadow. | — |
| O-2 | 2D earning: counter pill, le grain, ×2, le tirage du jour with the gilded rim, «D'où vient ton or», «Je conteste». | O-0 met, shadow numbers reviewed |
| O-3 | La Papeterie and la dorure: catalogue and contract test, buy/gild, the first pins and pencils in 2D and 3D, seal inks. | O-2 |
| O-4 | Editions and solo ardoise: weekly and monthly jobs, le pli du lundi, Gus's bet. | O-3 |
| O-5 | Ardoise tables for real learners. | eight or more active learners |
| O-6 | 3D: studio pieces, the Mistral slate, gold in world space, the Papeterie venue with its talk module. | the Quartier gates of the 3D plan |

O-1 can start now: it shows nothing and touches no learner-visible screen, so it does not
compete with Phase 1 («Ein Tag», #143). O-2 waits for O-0 and for «Ein Tag», so the
journée-pleine mark reads the same day record as everything else.

## 20. Deliberately absent

Lives, hearts, energy, gems for money, loot boxes, streak wagers, demotion zones,
countdown timers, «you were overtaken» pushes, XP levels (the learner's level is the
measured CEFR band, never bought), gold for time spent or for length. If a later ask
pushes toward any of these, push back: it breaks the brand and the ethics (Package I).

## 21. Owner decisions

Decided by Vincent on 31 Oct 2026:

1. **The name.** «L'or», counted in feuilles d'or (not «XP»).
2. **Consolidation (§12).** L'or is the one currency. Tokens and plates keep minting as
   history but leave the screen.

Still open (needed by O-4 and O-5, not before):

3. **How the week's piece is won.** Both editions (recommended: everyone with a full week
   gets the regular one, the table's top three the numbered one) or rank only.
4. **Names on Le Papier's palmarès.** Opt-in (recommended) or never printed.

## Sources

Read means the abstract or full text was read; secondary means a summary only.

- Sailer & Homner (2020), *The gamification of learning: a meta-analysis*, Educational
  Psychology Review 32: g = 0.49 cognitive, 0.36 motivational, 0.25 behavioural; game
  fiction and social interaction moderate behavioural outcomes (secondary).
- Sailer, Hense, Mayr & Mandl (2017), *How gamification motivates*, Computers in Human
  Behavior 69: badges, leaderboards and performance graphs raise competence; avatars,
  story and teammates raise relatedness (abstract read).
- Hanus & Fox (2015), Computers & Education 80: a leaderboard-and-badge course lowered
  intrinsic motivation, satisfaction and final exam scores over 16 weeks (abstract read).
- Deci, Koestner & Ryan (1999), Psychological Bulletin 125(6): expected tangible,
  performance-contingent rewards undermine intrinsic motivation; positive informational
  feedback raises it (d ≈ 0.33) (abstract read).
- Relative-position leaderboards and bottom-rank demotivation: Internet Research (2023,
  doi 10.1108/INTR-12-2021-0897) and the mixed findings it reviews (abstract read).
- Duolingo leagues: weekly boards of about 30 learners ranked by XP; learners report
  replaying easy lessons to hold a rank (Duolingo blog «improving Duolingo one
  experiment at a time»; Deconstructor of Fun; learner forums — secondary, anecdotal).
- Dai, Milkman & Riis (2014), *The fresh start effect*, Management Science: goal pursuit
  rises after temporal landmarks such as the start of a week (secondary). The Monday pli
  uses it.
- Kivetz, Urminsky & Zheng (2006), *The goal-gradient hypothesis resurrected*, JMR 43:
  effort accelerates near a reward (secondary). The journée-pleine rim and the
  five-day bar use it.
- Nunes & Drèze (2006), *The endowed progress effect*, JCR (secondary).
- Cepeda et al. (2006), *Distributed practice in verbal recall tasks*, Psychological
  Bulletin 132(3): spaced beats massed (abstract read). R1, R4 and R8 use it.
- Zendle & Cairns (2018), PLOS ONE: loot-box spending correlates with problem gambling
  (abstract read). Why no random drops.
- In the project: `docs/ATELIER_FORMS_AND_REWARD_PLAN.md` (G),
  `docs/ATELIER_REWARD_ECONOMY_PLAN.md` (I), the plan «Atelier – Was als Nächstes zählt»
  (30 Oct), and the code anchors cited above.
