# WP-124b — recovery that cannot stall the season (policy, code, and the bridges proposal)

**Status.** The recovery code is committed and safe on its own. The **bridges are new story text**: they are an owner-approval item and are **not committed**. They ship as [`WP-124B-BRIDGES-PROPOSAL.patch`](WP-124B-BRIDGES-PROPOSAL.patch). Apply it with `git apply docs/implementation/atelier-v2/WP-124B-BRIDGES-PROPOSAL.patch` once approved.

Inputs: owner decision 1 in [EXPERIENCE-REVIEW-2026-10-04](EXPERIENCE-REVIEW-2026-10-04.md) §8; the WP-124b section of [WORK-PACKAGES-2026-10-04-experience](WORK-PACKAGES-2026-10-04-experience.md); [WP-133a-RESULTS](WP-133a-RESULTS.md), which measured 4 lost days in 19 (21 %) with four different guard reasons.

## 1. The problem

WP-124a made a lost gap day honest: the learner re-reads the last season page. But a re-read does not move the season. A gap whose generation keeps failing re-reads the same page every day. Owner decision 1(b) said that two lost days in a row play the next tentpole day. The package makes that a recovery with prerequisites, never a blind cursor jump: a tentpole reads what its gap should have staged (a gate of Lila's path, the usual order, the roof…).

## 2. The policy

Decided only when today's generated day has just failed (`app/services/season/recovery.py`):

| Lost day in a row, same gap | What the learner gets |
|---|---|
| 1st (`REPRISES_BEFORE_RECOVERY = 1`) | The WP-124a reprise. It is a learner day, not a season day. |
| 2nd (`RECOVER_AT_FAILURE = 2`) | An authored continuation that needs no model and is bound and settled as a season day: **the next tentpole's Day A**, if every moment the gap marks `required` has been staged; otherwise **the gap's bridge**, which stages exactly the moments still owed and then closes the gap, so the next day is the tentpole. |
| 2nd, with no bridge data for that gap | The reprise again. The cursor never jumps over a moment the story needs. This is the behaviour of the committed code until the proposal is applied. |

- **The constants.** At p = 0.21, a 6-day gap holds a run of two lost days 18 % of the time. About 3 lives in 4 meet at least one such run over the season's seven gaps, 1.3 runs a life on average. Waiting for a third lost day would leave a learner on the same page for two days in one life in four. So the second lost day recovers. `MAX_CONSECUTIVE_REPRISES = 1` is the walk's bound.
- **"Lost day" and the reset.** A lost day is a learner day whose plan is a reprise or a recovery, or that was left unavailable. A day the director wrote breaks the run; that is the counter's reset. The run is read from the learner's own journeys and never stored (`recovery.failures_before`). A run in another gap does not count.
- **Prerequisites** (`recovery.prerequisites_hold`) are the gap's `required` moments, recorded in `state["premises"]`. A generated day records a moment only when the learner engaged (WP-113); a bridge records it only once its turn was answered.
- **What a bridge may do** (`app/services/season/bridges.py`, `validate_bridges`; enforced at load and in `scripts/season_check.py`):
  - It stages only the gap's own required moments, one block per moment, and every block asks the learner something.
  - A gate moment carries its gate, with a romance reply, a friendship reply and a neutral fallback. The signal is what the learner expresses, as on any day.
  - It sets only the flags its premise lists. A flag the learner decides (the usual order) is set by the learner's reply or card, never by the page: no turn-level `sets`, no solve default.
  - A `fixed` fact is allowed only when it quotes the gap's `establish` line. One is used: the ticket moved to 2 December, the same fact every life reaches.
  - It makes none of the gap's forbidden reveals, at any written level, and its hook ends on «À suivre…».
- **What the learner is told.** The day's task starts with an honest line in their language (`RECOVERY_COPY`):
  - bridge: «The story moves on faster today: a few days, told in one page.»
  - tentpole: «A few days of the story went by without an episode.»
- **What is recorded.**
  - `state["shortened"]` gets one row per gap cut short: `{gap, played_days, nominal_days, via: bridge|tentpole, moments_bridged, reason, date, event_id}`.
  - The played-log row says `bridge` / `recovery`.
  - The journey's `plan_selection.generation_fallback` is `{kind: season_recovery, recovery, gap, failure, page_key, moments, season_day: true}`. A reprise's marker now also carries `gap`, `failure` and `recovery`.
  - The Cahier (`story_archive`) is built from the learner's days, so skipped episodes never appear as planches. The bridge is one planche under the gap's own title.

### Edge cases

- **The first gap after T1.** T1 B is the page to re-read, so day 3 is the reprise. Day 4 is g1's bridge: Romy, «La même chose ?», the ticket. Day 5 is T2 A.
- **A tentpole day** is authored and does not fail. If one cannot be served, the lost day is a reprise (`not_a_gap_day`).
- **After the finale** there is no season left to stall. A lost day re-reads the last page, and nothing moves (`season_finished`, whatever the run). What comes after T8 belongs to the epilogue (WP-132B). This package keeps its after-finale behaviour minimal: `recovery.decide` is the one place an epilogue continuation would plug in.
- **Successful generation** resets the run (test `test_a_written_day_resets_the_run`).
- **Mixed success and failure** never re-reads twice in a row, and the played log only grows (test `test_mixed_outages_…`).
- **Prefetch invalidation.** A prefetched scene is keyed on the story revision (`living_story.story_revision`, the thread state's fingerprint). Settling a bridge or a recovered tentpole changes it, so a scene prefetched for a closed gap is discarded, never served. The clock also never returns a closed gap's day again.
- **Reloads and concurrency.** The continuation is chosen under the generation claim and persisted with the plan. A reload or a second create reads it. A double finish settles once, because `record_played`, `_shorten` and the premise rows are idempotent per event and per gap (test `test_a_recovered_day_is_chosen_once_…`).
- **A bridge left unfinished.** A moment whose turn was never answered stays owed, and the gap stays open. The next lost day is a recovery again, with only what is still owed.
- **Bridges and the grammar plan.** A bridge is answered as an authored page (`kind: tentpole` + a `bridge` marker), so like a tentpole day it introduces no new unit; the quota offers it the next day. It happens at most once per gap.

## 3. The code (committed)

| File | Change |
|---|---|
| `app/services/season/recovery.py` (new) | The policy (`decide`), the run (`failures_before`), the prerequisites, the continuation brief (`recovery_brief`), the honest copy. |
| `app/services/season/bridges.py` (new) | The bridge format, loader (`{}` without a file or with an invalid one), validator and page composer. |
| `app/services/season/clock.py` | `shortened_gaps`: a closed gap's next day is its tentpole, with no weekend flex. `record_played(extra=…)`. |
| `app/services/season/runtime.py` | `tentpole_brief(page=…, season_extra=…)`; `settle` stages a bridge's answered moments, applies its fixed facts and records the shortened gap. A bridge turn always routes the story (`routes_the_story`). |
| `app/services/daily_journey.py` | `_serve_season_reprise` asks for the decision first. It serves the continuation through `_serve_season_recovery`, else the reprise, whose marker gains `gap`/`failure`/`recovery`. |
| `scripts/season_check.py` | Validates the bridges, requires one for every gap holding a required moment, and prints the **deviation record**. |
| `tests/test_wp124b_recovery.py`, `tests/walk_checks_wp124b.py` (new) | See §6. |
| `tests/experience_walk.py`, `tests/test_experience_walk.py` | Additive: `season_cursor` per day, and the forced outage `WALK_FAIL_RATE` (deterministic per life; `1` = every generated day lost). |

## 4. The proposal: four bridges, six moments (owner approval)

- **Files.** `app/data/season/s1/bridges.json` (new), `app/data/season/s1/levels_bridges.json` (new; A1 with en/de translations, B2, C1), and 6 entries appended to `app/data/season/s1/tasks.json` (plain tasks and «ask again» lines).
- **Deviation record.** In the file: «EXPERIENCE-REVIEW 2026-10-04, owner decision 1(b)… these bridges supply the required moments a skip would drop», `approved: pending`.
- **Levels.** B1 reads the A2 line, as the bible does where it wrote no B1.

| Bridge | Moments (gap `required`) | First lines (A2) | Words A1 / A2 / B1 / B2 / C1 |
|---|---|---|---|
| g1 «La première semaine» | `romy_enquete`, `la_meme_chose` (card, sets `user.usual_order`), `le_billet` (fixed `user.return_ticket` = «mercredi 2 décembre») | «Quelques jours après, au Mistral.» · Romy: «Solvel achète des cafés dans le quartier. Tu sais quelque chose ?» · Margaux: «J'ai rien entendu.» | 155 / 179 / 179 / 220 / 243 |
| g2 «L'appartement s'ouvre» | `le_diner_rate` (gate 2) | «Un soir, dans la cuisine d'Odile. Lila, toi et une omelette.» · «La fumée. Puis l'alarme.» · Lila: «Bon. Pas de dîner. Dis quelque chose, vite.» | 51 / 57 / 57 / 68 / 79 |
| g3 «Avant la fête» | `sur_le_toit` | «Une nuit, Lila t'emmène sur le toit.» · Lila: «Regarde. Le canal, d'en haut. Personne ne vient ici.» · Marchand: «La succession Ferrand n'a rien à faire sur mon toit.» | 59 / 71 / 71 / 84 / 97 |
| g4 «Le quartier sait» | `la_dispute` (gate 3; the argument reads `s1.fire_photo`) | «Un matin, au bord du canal.» · Lila (wall): «C'est ma faute ? La photo est au mur, l'assurance appelle. Dis-le.» / (margaux): «Encore un secret. Ici, tout le monde cache tout. Même toi.» · «Plus un mot. Pas avant le lendemain.» | 52 / 62 / 62 / 70 / 82 |

The word counts are every French word on the page at that level, every reply branch included; one path through a page is about two thirds of that. g5, g6 and g7 hold no required moment, so their recovery is the next tentpole and they need no bridge.

**Owner lines reused verbatim.**
- From `gaps.json` premises: «J'ai rien entendu.» and «La succession Ferrand n'a rien à faire sur mon toit.»
- From bible §7, the gates' own example lines: «C'est le meilleur dîner raté de ma vie.», «On dit à Marin que c'était exprès.», «Je ne veux pas me disputer avec toi. Pas toi.», «On est une équipe. Pardon.»
- «La même chose ?»

**Deliberate departures from the premise texts.**
- Romy says «tu» (the gap's register rule) where the premise quotes «C'est vous, l'héritage ?».
- Gus's «un habitué» became the agreement-free «vous êtes d'ici, maintenant», because lines to Toi are agreement-free.

**Validation, with the proposal applied.**
- `season_check.py` prints `bridges: ok` and the deviation record.
- `season_levels.py --file bridges --strict` reports **0 problems**: A1 95.6 % known of 297 words, B2 98.0 %, C1 97.2 %. Every A1 line is ≤ 10 words with ≤ 1 word outside the A1 list and no grammar above A1. Every A1 variant has en/de translations, and every turn has a plain task and an A1-checked «ask again».
- The whole-season `season_levels.py --strict` stays at 0 problems.

The full text follows (A2 with en/de, then A1 with its own translations, B2, C1).

### Bridge g1 · «La première semaine» (13–17 nov., 6 min)


#### Moment `romy_enquete`

*(g1.romy.p1)* Le Mistral in the morning. A young woman with a phone held out like a microphone leans on the zinc; Margaux dries a glass and does not look at her.
- **CAPTION** · A2 «Quelques jours après, au Mistral.» — *en* A few days later, at Le Mistral. · *de* Ein paar Tage später, im Mistral.
  - A1 «Au Mistral, quelques jours après.» — *en* At Le Mistral, a few days after. · *de* Im Mistral, ein paar Tage danach.
  - B2 «Au Mistral, quelques jours ont passé.»
  - C1 «Au Mistral. Quelques jours ont filé.»
*(g1.romy.p2)*
- **Romy Tremblay** · A2 «Solvel achète des cafés dans le quartier. Tu sais quelque chose ?» — *en* Solvel is buying cafés in the neighbourhood. Do you know anything? · *de* Solvel kauft Cafés im Viertel. Weißt du etwas?
  - A1 «Solvel achète des cafés ici. Tu as une info ?» — *en* Solvel is buying cafés here. Do you have any info? · *de* Solvel kauft hier Cafés. Hast du eine Info?
  - B2 «Solvel rachète les cafés du quartier les uns après les autres. Tu en sais quelque chose ?»
  - C1 «Solvel fait main basse sur les cafés du quartier. Tu aurais quelque chose à me dire ?»
- **Margaux** · A2 «J'ai rien entendu.» — *en* I didn't hear anything. · *de* Ich habe nichts gehört.
  - A1 «Moi ? Rien.» — *en* Me? Nothing. · *de* Ich? Nichts.
  - B2 «Je n'ai rien entendu.»
  - C1 «J'ai rien entendu.»

**Turn `g1.romy.turn`** → Romy Tremblay · fallback `guarded`
*(g1.romy.p3)* Romy turns the phone toward Toi. Margaux, behind her, rolls her eyes.
- **Romy Tremblay** · A2 «Et toi ? C'est toi, l'héritage d'Odile ?» — *en* And you? You're Odile's inheritance? · *de* Und du? Du bist also das Erbe von Odile?
  - A1 «Et toi ? Tu es la famille d'Odile ?» — *en* And you? Are you Odile's family? · *de* Und du? Bist du die Familie von Odile?
  - B2 «Et toi, alors ? C'est toi, le fameux héritage d'Odile ?»
  - C1 «Et toi, tiens ! Ce serait donc toi, le fameux héritage d'Odile ?»
- Task (en/de/fr): Tell Romy who you are and what you think of Solvel, as much or as little as you want. / Sag Romy, wer du bist und was du von Solvel hältst, so viel oder so wenig du willst. / Dis à Romy qui tu es et ce que tu penses de Solvel, autant ou aussi peu que tu veux.
- Plain task: Tell Romy who you are, and what you think of Solvel if you like. / Sag Romy, wer du bist, und wenn du magst, was du von Solvel hältst. / Dis à Romy qui tu es, et ce que tu penses de Solvel si tu veux.
- Ask again: «Oui ? Et Odile, c'est qui pour toi ?» (en Yes? And who is Odile to you? · de Ja? Und wer ist Odile für dich?); named «{name} ? Et Odile, c'est qui pour toi ?»
- Reply `open` (Talks): The learner says who they are to Odile, or gives an opinion on Solvel. Examples: «Oui. Odile, c'est ma grand-mère.» / «Je suis la famille d'Odile. Solvel, je ne sais pas.»; A1 «Oui, Odile est ma grand-mère.» / «Je suis la famille d'Odile.»
  *(g1.romy.open.r1)*
- **Romy Tremblay** · A2 «Sa famille. Parfait. Tu me plais, comme source.» — *en* Her family. Perfect. I like you, as a source. · *de* Ihre Familie. Perfekt. Du gefällst mir, als Quelle.
  - A1 «Sa famille. Super. Je reviens te voir.» — *en* Her family. Great. I'll come back to see you. · *de* Ihre Familie. Super. Ich komme wieder zu dir.
  - B2 «De la famille ! Parfait. Tu feras une excellente source.»
  - C1 «De la famille, rien que ça. Toi, tu vas devenir ma source préférée.»
- Reply `guarded` (No comment): The learner deflects, or will not talk to a journalist. Examples: «Pas de commentaire.» / «Je ne parle pas aux journalistes.»; A1 «Non. Pas de journalistes.» / «Je ne parle pas.»
  *(g1.romy.guarded.r1)*
- **Romy Tremblay** · A2 «« Pas de commentaire. » Tu parles déjà comme Margaux.» — *en* "No comment." You already talk like Margaux. · *de* "Kein Kommentar." Du redest schon wie Margaux.
  - A1 «Non ? Tu parles comme Margaux !» — *en* No? You talk like Margaux! · *de* Nein? Du redest wie Margaux!
  - B2 «« Pas de commentaire. » Trois jours ici et tu parles déjà comme Margaux.»
  - C1 «« Pas de commentaire. » Trois jours au Mistral, et tu parles déjà comme Margaux : c'est-à-dire le moins possible.»
- After any reply:
*(g1.romy.after)* Romy writes «3» on a paper napkin and slides it toward Toi.
- **Romy Tremblay** · A2 «Trois cafés dans le quartier cette année. Tous pour Solvel.» — *en* Three cafés in the neighbourhood this year. All of them to Solvel. · *de* Drei Cafés im Viertel dieses Jahr. Alle an Solvel.
  - A1 «Cette année, Solvel achète trois cafés ici.» — *en* This year, Solvel is buying three cafés here. · *de* Dieses Jahr kauft Solvel hier drei Cafés.
  - B2 «Trois cafés rachetés dans le quartier depuis janvier. Tous par Solvel.»
  - C1 «Trois cafés du quartier rachetés depuis janvier, et toujours le même acquéreur : Solvel.»

#### Moment `la_meme_chose`

*(g1.order.p1, silent)* Le Mistral, early. Gus at the end of the zinc with his croissant; Margaux, a cup in her hand, already looking at Toi.
- **CAPTION** · A2 «Encore un matin au Mistral.» — *en* Another morning at Le Mistral. · *de* Noch ein Morgen im Mistral.
  - A1 = A2
  - B2 «Troisième matin au Mistral.»
  - C1 «Au troisième matin.»
*(g1.order.p2)*
- **Augustin « Gus » de Roncourt** · A2 «Attention. Ici, votre café dit beaucoup sur vous.» — *en* Careful. Here, your coffee says a lot about you. · *de* Vorsicht. Hier sagt Ihr Kaffee viel über Sie.
  - A1 «Ici, le café dit beaucoup sur vous.» — *en* Here, the coffee says a lot about you. · *de* Hier sagt der Kaffee viel über Sie.
  - B2 «Prudence. Ce que vous commandez ici dira qui vous êtes.»
  - C1 «Prudence, je vous prie. Ici, dis-moi ce que tu bois, je te dirai qui tu es — pardon, vous.»

**«Le choix» `g1.order`** → Margaux (no default: the learner taps a card; sets `user.usual_order`)
- **CAPTION** · A2 «La même chose ?» — *en* The same? · *de* Das Gleiche?
  - A1 = A2
  - B2 «La même chose ?»
  - C1 «La même chose ?»
- Task: Choose your usual order. Margaux will remember it. / Wähle deine übliche Bestellung. Margaux wird sie sich merken. / Choisis ta commande habituelle. Margaux s'en souviendra.
- Card `creme` «Un café crème» (en A café crème · de Einen Café crème) → sets {"user.usual_order": "un café crème"}
  *(g1.order.creme.r1)*
- **Margaux** · A2 «Un crème. C'est noté.» — *en* A crème. Noted. · *de* Ein Crème. Gemerkt.
  - A1 «D'accord. Demain, la même chose.» — *en* All right. Tomorrow, the same. · *de* In Ordnung. Morgen das Gleiche.
  - B2 «Un crème. C'est noté.»
  - C1 «Un crème. Retenu.»
- Card `noisette` «Un noisette» (en A noisette · de Einen Noisette) → sets {"user.usual_order": "un noisette"}
  *(g1.order.noisette.r1)*
- **Augustin « Gus » de Roncourt** · A2 «Un noisette ! Une personne précise.» — *en* A noisette! A precise person. · *de* Einen Noisette! Ein genauer Mensch.
  - A1 «Ah ! Très bien, très bien.» — *en* Ah! Very good, very good. · *de* Ah! Sehr gut, sehr gut.
  - B2 «Un noisette ! Voilà une personne qui sait ce qu'elle veut.»
  - C1 «Un noisette ! La précision faite boisson.»
- Card `the` «Un thé» (en A tea · de Einen Tee) → sets {"user.usual_order": "un thé"}
  *(g1.order.the.r1)*
- **Augustin « Gus » de Roncourt** · A2 «Un thé, au Mistral. Quel courage.» — *en* A tea, at Le Mistral. What courage. · *de* Einen Tee, im Mistral. Was für ein Mut.
  - A1 «Un thé ? Ici ? Oh là là.» — *en* A tea? Here? Oh dear. · *de* Einen Tee? Hier? Oje.
  - B2 «Un thé, au Mistral ? Quel courage.»
  - C1 «Un thé, au Mistral ? Voilà qui frise l'insolence.»
- Card `chocolat` «Un chocolat chaud» (en A hot chocolate · de Eine heiße Schokolade) → sets {"user.usual_order": "un chocolat chaud"}
  *(g1.order.chocolat.r1)*
- **Margaux** · A2 «Un chocolat. Comme Lila.» — *en* A hot chocolate. Like Lila. · *de* Eine Schokolade. Wie Lila.
  - A1 = A2
  - B2 «Un chocolat. Comme Lila.»
  - C1 «Un chocolat. Tiens, comme Lila.»
*(g1.order.p3)* Gus raises his cup to the room. Nobody laughs. Margaux puts the cup down in front of Toi without asking anything.
- **Augustin « Gus » de Roncourt** · A2 «C'est officiel : vous êtes d'ici, maintenant.» — *en* It's official: you're from here now. · *de* Es ist offiziell: Sie sind jetzt von hier.
  - A1 «Voilà : maintenant, vous êtes d'ici.» — *en* There: now you're from here. · *de* So: Jetzt sind Sie von hier.
  - B2 «C'est officiel : vous faites partie des meubles, désormais.»
  - C1 «C'est officiel : vous voilà désormais du quartier, et ce n'est pas une plaisanterie.»

#### Moment `le_billet` — fixed fact: `user.return_ticket` = «mercredi 2 décembre» (gap establish: “The return ticket has moved to 2 December (user.return_ticket).”)

*(g1.billet.p1)* The booth of Le Mistral. A phone on the table, on speaker. Lila sits too close, a pencil behind her ear.
- **CAPTION** · A2 «Le lendemain. Ton billet de retour est pour mercredi.» — *en* The next day. Your return ticket is for Wednesday. · *de* Am nächsten Tag. Dein Rückflug ist am Mittwoch.
  - A1 «Le jour après. Ton billet : mercredi.» — *en* The day after. Your ticket: Wednesday. · *de* Am Tag danach. Dein Ticket: Mittwoch.
  - B2 «Le lendemain. Ton billet de retour est toujours pour mercredi.»
  - C1 «Le lendemain. Ton billet de retour indique toujours mercredi.»
*(g1.billet.p2)*
- **Lila Bonnet** · A2 «Tu appelles, moi je t'aide. Enfin… j'essaie.» — *en* You call, I help. Well… I try. · *de* Du rufst an, ich helfe. Na ja… ich versuch's.
  - A1 «Tu appelles. Moi, je t'aide. Enfin… je pense.» — *en* You call. I help you. Well… I think. · *de* Du rufst an. Ich helfe dir. Na ja… glaube ich.
  - B2 «Tu appelles, et moi je te coache. Enfin… je fais de mon mieux.»
  - C1 «Tu appelles, je te souffle les répliques. Enfin… à ma façon.»

**Turn `g1.billet.turn`** → L'EMPLOYÉE · fallback `vague`
*(g1.billet.p3)* Close on the phone's screen: «Service clients». Lila mimes a big sad face.
- **L'EMPLOYÉE** · A2 «Bonjour, service clients. Vous voulez changer votre billet ? Pour quelle raison ?» — *en* Hello, customer service. You want to change your ticket? For what reason? · *de* Guten Tag, Kundenservice. Sie möchten Ihr Ticket ändern? Aus welchem Grund?
  - A1 «Bonjour. Vous changez votre billet ? Pourquoi ?» — *en* Hello. You're changing your ticket? Why? · *de* Guten Tag. Sie ändern Ihr Ticket? Warum?
  - B2 «Service clients, bonjour. Vous souhaitez modifier votre billet ? Puis-je savoir pourquoi ?»
  - C1 «Service clients, bonjour. Vous souhaitez modifier votre réservation ? Pour quel motif, je vous prie ?»
- Task (en/de/fr): Explain to the agent why you are staying. You decide how honest you are. / Erkläre der Mitarbeiterin, warum du bleibst. Du entscheidest, wie ehrlich du bist. / Explique à l'employée pourquoi tu restes. Tu décides à quel point tu es honnête.
- Plain task: Tell the agent why you are staying longer. / Sag der Mitarbeiterin, warum du länger bleibst. / Dis à l'employée pourquoi tu restes plus longtemps.
- Ask again: «Pardon ? Pourquoi vous restez ?» (en Sorry? Why are you staying? · de Wie bitte? Warum bleiben Sie?)
- Reply `honest` (Personal): A personal reason: the people, the café, the neighbourhood, wanting to stay. Examples: «Je reste parce que j'aime le quartier.» / «Il y a des gens ici. Je veux rester.»; A1 «J'aime le quartier.» / «J'aime les gens ici.»
  *(g1.billet.honest.r1)*
- **Lila Bonnet** *(a whisper)* · A2 «Trop honnête. J'adore.» — *en* Too honest. I love it. · *de* Zu ehrlich. Ich liebe es.
  - A1 «C'est vrai, ça. J'adore.» — *en* That's true, that. I love it. · *de* Das ist wahr. Ich liebe es.
  - B2 «Beaucoup trop honnête. J'adore.»
  - C1 «D'une honnêteté désarmante. J'adore.»
- Reply `practical` (Practical): A practical reason: the notary, the papers, the flat. Examples: «Pour le notaire. Les papiers prennent du temps.» / «Pour l'appartement de ma grand-mère.»; A1 «Pour le notaire.» / «Pour l'appartement.»
  *(g1.billet.practical.r1)*
- **Lila Bonnet** *(a whisper)* · A2 «Ennuyeux. Mais ça marche.» — *en* Boring. But it works. · *de* Langweilig. Aber es funktioniert.
  - A1 «C'est triste. Mais ça marche.» — *en* It's sad. But it works. · *de* Das ist traurig. Aber es klappt.
  - B2 «Ennuyeux à mourir. Mais efficace.»
  - C1 «Soporifique. Mais redoutablement efficace.»
- Reply `vague` (Vague): No clear reason, or anything else. Examples: «C'est compliqué.» / «Je ne sais pas.»
  *(g1.billet.vague.r1)*
- **Lila Bonnet** *(grabbing the phone)* · A2 «Donne ! Il y a une grand-mère, un appartement et beaucoup de croissants.» — *en* Give it here! There's a grandmother, a flat and a lot of croissants. · *de* Gib her! Es gibt eine Großmutter, eine Wohnung und viele Croissants.
  - A1 «Donne ! Une grand-mère, un appartement, des croissants.» — *en* Give it! A grandmother, a flat, croissants. · *de* Gib her! Eine Großmutter, eine Wohnung, Croissants.
  - B2 «Donne-moi ça ! Il y a une grand-mère, un appartement et une quantité déraisonnable de croissants.»
  - C1 «Passe-moi ça ! Alors : une grand-mère, un appartement, et une consommation de croissants franchement préoccupante.»
- After any reply:
*(g1.billet.after)*
- **L'EMPLOYÉE** · A2 «Très bien. Mercredi 2 décembre, alors.» — *en* Very well. Wednesday 2 December, then. · *de* Sehr gut. Also Mittwoch, der 2. Dezember.
  - A1 «Bien. Mercredi 2 décembre.» — *en* Good. Wednesday 2 December. · *de* Gut. Mittwoch, 2. Dezember.
  - B2 «Parfait. Ce sera donc mercredi 2 décembre.»
  - C1 «Entendu. Je vous mets sur le mercredi 2 décembre.»
- **CAPTION** · A2 «Le billet change. Et toi aussi, un peu.» — *en* The ticket changes. And so do you, a little. · *de* Das Ticket ändert sich. Und du auch, ein bisschen.
  - A1 «Le billet change. Toi aussi, un peu.» — *en* The ticket changes. You too, a little. · *de* Das Ticket ändert sich. Du auch, ein bisschen.
  - B2 «Le billet change de date. Et quelque chose change en toi aussi.»
  - C1 «Le billet change de date. Et, l'air de rien, toi aussi.»

#### Hook

*(g1.hook.p, silent)* The stairwell from below: the first-floor door, closed, a strip of light under it from the landing lamp.
- **CAPTION** · A2 «En haut, l'appartement attend toujours. À suivre…» — *en* Upstairs, the flat is still waiting. To be continued… · *de* Oben wartet die Wohnung noch immer. Fortsetzung folgt…
  - A1 «En haut, l'appartement attend. À suivre…» — *en* Upstairs, the flat is waiting. To be continued… · *de* Oben wartet die Wohnung. Fortsetzung folgt…
  - B2 «Au premier, l'appartement attend toujours. À suivre…»
  - C1 «Au premier, l'appartement attend, porte close. À suivre…»

### Bridge g2 · «L'appartement s'ouvre» (20–25 nov., 5 min)


#### Moment `le_diner_rate`

*(g2.diner.p1)* Odile's small kitchen. Lila breaks eggs with too much confidence; Toi holds the pan. A bottle of wine, two mismatched glasses.
- **CAPTION** · A2 «Un soir, dans la cuisine d'Odile. Lila, toi et une omelette.» — *en* One evening, in Odile's kitchen. Lila, you and an omelette. · *de* Eines Abends, in der Küche von Odile. Lila, du und ein Omelett.
  - A1 «Le soir. La cuisine d'Odile. Lila, toi, une omelette.» — *en* Evening. Odile's kitchen. Lila, you, an omelette. · *de* Abend. Die Küche von Odile. Lila, du, ein Omelett.
  - B2 «Un soir, dans la cuisine d'Odile : Lila, toi, et une omelette improvisée.»
  - C1 «Un soir, dans la cuisine d'Odile : Lila, toi, et une omelette de fortune.»
*(g2.diner.p2, silent)* Black smoke from the pan; the smoke alarm on the ceiling, drawn as a scream. Lila waves a tea towel at it.
- **CAPTION** · A2 «La fumée. Puis l'alarme.» — *en* Smoke. Then the alarm. · *de* Rauch. Dann der Alarm.
  - A1 «La cuisine est noire. Ça sonne fort !» — *en* The kitchen is black. Something rings loudly! · *de* Die Küche ist schwarz. Es klingelt laut!
  - B2 «De la fumée. Puis l'alarme, stridente.»
  - C1 «De la fumée. Puis l'alarme, qui hurle.»
*(g2.diner.p3, silent)* Margaux in the kitchen doorway, out of breath, the café's fire extinguisher raised. She looks at the burnt omelette. She lowers the extinguisher and goes back down the stairs without a word.

**Turn `g2.diner.turn`** → Lila Bonnet · gate 2 · fallback `neutre`
*(g2.diner.p4)* Lila on the kitchen floor, back against the oven, laughing. The smoke thins above her.
- **Lila Bonnet** *(sitting on the floor, laughing too hard to stand)* · A2 «Bon. Pas de dîner. Dis quelque chose, vite.» — *en* Well. No dinner. Say something, quick. · *de* Na gut. Kein Abendessen. Sag was, schnell.
  - A1 «Bon. Pas de dîner. Dis un mot !» — *en* Well. No dinner. Say a word! · *de* Na gut. Kein Abendessen. Sag ein Wort!
  - B2 «Bon. Le dîner est officiellement raté. Dis quelque chose, vite, avant que je pleure de rire.»
  - C1 «Bon. Le dîner est un désastre officiel. Dis quelque chose, vite, avant que je meure de rire.»
- Task (en/de/fr): Say the line that saves the evening, however you like. This is a path gate: what you express is read, never how well you say it. / Sag den Satz, der den Abend rettet, wie du magst. Das ist ein Weichenpunkt: Gelesen wird, was du ausdrückst, nie, wie gut du es sagst. / Dis la phrase qui sauve la soirée, comme tu veux. C'est un point de bascule : ce qu'on lit, c'est ce que tu exprimes, jamais la qualité de ta phrase.
- Plain task: Say something to Lila that saves the evening. / Sag Lila etwas, das den Abend rettet. / Dis à Lila quelque chose qui sauve la soirée.
- Ask again: «Allez, dis un mot !» (en Come on, say a word! · de Los, sag ein Wort!)
- Reply `tendresse` (Tenderness, path romance): Tenderness toward her: the evening with her was good, whatever happened to the dinner. Examples: «C'est le meilleur dîner raté de ma vie.» / «J'aime bien dîner avec toi.»; A1 «Le meilleur dîner raté de ma vie.» / «J'aime dîner avec toi.»
  *(g2.diner.tendresse.r1, silent)* Lila stops laughing. She looks at Toi a second too long.
  *(g2.diner.tendresse.r2)*
- **Lila Bonnet** · A2 «… Moi aussi.» — *en* … Me too. · *de* … Ich auch.
  - A1 = A2
  - B2 «… Moi aussi.»
  - C1 «… Moi aussi.»
- Reply `complice` (Complicity, path friendship): Complicity: a joke between accomplices, a plan, the two of them against the world. Examples: «On dit à Marin que c'était exprès.» / «On commande une pizza ?»; A1 «On dit à Marin : c'est exprès.» / «Une pizza ?»
  *(g2.diner.complice.r1)*
- **Lila Bonnet** · A2 «Exprès, bien sûr. C'est de l'art.» — *en* On purpose, of course. It's art. · *de* Absichtlich, natürlich. Das ist Kunst.
  - A1 «Pour Marin ? Oui ! C'est un dîner d'artiste.» — *en* For Marin? Yes! It's an artist's dinner. · *de* Für Marin? Ja! Das ist ein Künstleressen.
  - B2 «Exprès, évidemment. Une performance artistique.»
  - C1 «Exprès, cela va de soi. Une performance, une installation.»
- Reply `neutre` (Neither): A neutral remark, a halting reply that expresses neither tenderness nor complicity. Examples: «Oups.» / «Bon appétit.»
  *(g2.diner.neutre.r1)*
- **Lila Bonnet** · A2 «Oui. Bon appétit, l'héritage.» — *en* Yes. Enjoy your meal, l'héritage. · *de* Ja. Guten Appetit, l'héritage.
  - A1 «Oui. Bon appétit !» — *en* Yes. Enjoy your meal! · *de* Ja. Guten Appetit!
  - B2 «C'est ça. Bon appétit, l'héritage.»
  - C1 «Voilà. Bon appétit, l'héritage.»
- After any reply:
*(g2.diner.after)* Lila writes «NE REFAIS JAMAIS L'OMELETTE» on the fridge's whiteboard.
- **Lila Bonnet** · A2 «Règle numéro un : ne refais jamais l'omelette.» — *en* Rule number one: never make the omelette again. · *de* Regel Nummer eins: Mach nie wieder das Omelett.
  - A1 «Plus jamais d'omelette. Jamais !» — *en* No omelette ever again. Never! · *de* Nie wieder Omelett. Niemals!
  - B2 «Règle numéro un : ne refais jamais, jamais l'omelette.»
  - C1 «Règle numéro un, gravée dans le marbre : ne refais jamais l'omelette.»

#### Hook

*(g2.hook.p, silent)* Le Mistral at closing time: Gus and Marin at two different tables, each writing something on a card, each hiding it from the other.
- **CAPTION** · A2 «Jeudi, deux personnes ont quelque chose à te demander. À suivre…» — *en* On Thursday, two people have something to ask you. To be continued… · *de* Am Donnerstag wollen zwei Leute dich etwas fragen. Fortsetzung folgt…
  - A1 «Jeudi, deux amis ont une question. À suivre…» — *en* On Thursday, two friends have a question. To be continued… · *de* Am Donnerstag haben zwei Freunde eine Frage. Fortsetzung folgt…
  - B2 «Jeudi, deux personnes vont te demander quelque chose. À suivre…»
  - C1 «Jeudi, deux personnes auront chacune une faveur à te demander. À suivre…»

### Bridge g3 · «Avant la fête» (28 nov. – 4 déc., 5 min)


#### Moment `sur_le_toit`

*(g3.toit.p1)* The fifth-floor skylight, open. Lila already outside on the zinc roof, holding out her hand.
- **CAPTION** · A2 «Une nuit, Lila t'emmène sur le toit.» — *en* One night, Lila takes you up on the roof. · *de* Eines Nachts nimmt Lila dich mit aufs Dach.
  - A1 «La nuit. Lila et toi, sur le toit.» — *en* Night. Lila and you, on the roof. · *de* Nacht. Lila und du, auf dem Dach.
  - B2 «Une nuit, Lila t'entraîne sur le toit par la lucarne du cinquième.»
  - C1 «Une nuit, Lila te fait passer par la lucarne du cinquième, direction le toit.»
*(g3.toit.p2)* The canal at night from the roof: the locks, the lit footbridges, a barge.
- **Lila Bonnet** · A2 «Regarde. Le canal, d'en haut. Personne ne vient ici.» — *en* Look. The canal, from above. Nobody comes up here. · *de* Schau. Der Kanal, von oben. Niemand kommt hier hoch.
  - A1 «Regarde. Le canal, la nuit. C'est beau.» — *en* Look. The canal, at night. It's beautiful. · *de* Schau. Der Kanal, nachts. Das ist schön.
  - B2 «Regarde. Le canal vu d'en haut. Ici, personne ne vient jamais.»
  - C1 «Regarde-moi ça. Le canal, vu d'en haut. Personne ne monte jamais jusqu'ici.»
*(g3.toit.p3, silent)* A torch beam finds them. Behind it, in a dressing gown and a hat, M. Marchand.

**Turn `g3.toit.turn`** → M. Marchand · fallback `insolent`
*(g3.toit.p4)* Marchand's face in the torchlight. Lila, behind Toi, bites her sleeve not to laugh.
- **M. Marchand** · A2 «La succession Ferrand n'a rien à faire sur mon toit.» — *en* The Ferrand estate has no business on my roof. · *de* Der Nachlass Ferrand hat auf meinem Dach nichts zu suchen.
  - A1 «Vous ! Ici ! C'est mon toit.» — *en* You! Here! This is my roof. · *de* Sie! Hier! Das ist mein Dach.
  - B2 «La succession Ferrand n'a rien à faire sur mon toit.»
  - C1 «La succession Ferrand n'a rien à faire sur mon toit.»
- Task (en/de/fr): Talk your way down, politely, to M. Marchand. Use your best «vous». / Rede dich höflich bei M. Marchand heraus. Mit deinem besten «vous». / Sors-toi de là poliment, avec M. Marchand. Ton plus beau « vous ».
- Plain task: Talk to M. Marchand politely, and get off the roof. / Sprich höflich mit M. Marchand und komm vom Dach herunter. / Parle poliment à M. Marchand, et descends du toit.
- Ask again: «Pourquoi vous êtes ici, sur mon toit ?» (en Why are you here, on my roof? · de Warum sind Sie hier, auf meinem Dach?)
- Reply `poli` (Polite): A polite apology or promise to come down, in vous. Examples: «Pardon, monsieur. Nous descendons tout de suite.» / «Excusez-nous, monsieur Marchand.»; A1 «Pardon, monsieur.» / «Excusez-nous. On descend.»
  *(g3.toit.poli.r1)*
- **M. Marchand** · A2 «Hm. Poli, au moins. Descendez. Lentement.» — *en* Hm. Polite, at least. Come down. Slowly. · *de* Hm. Wenigstens höflich. Kommen Sie herunter. Langsam.
  - A1 «Bien. Descendez. Pas vite.» — *en* Good. Come down. Not fast. · *de* Gut. Kommen Sie herunter. Nicht schnell.
  - B2 «Hm. Poli, c'est déjà ça. Descendez. Lentement.»
  - C1 «Hm. La politesse, au moins, est sauve. Descendez. Lentement.»
- Reply `excuse` (An excuse): An excuse or explanation: the view, the canal, a mistake. Examples: «On regardait le canal, c'est tout.» / «Nous voulions voir la vue.»; A1 «On regarde le canal.» / «Pour la vue.»
  *(g3.toit.excuse.r1)*
- **M. Marchand** · A2 «La vue. Bien sûr. Mais la vue aussi est à moi.» — *en* The view. Of course. But the view is mine too. · *de* Die Aussicht. Natürlich. Aber die Aussicht gehört auch mir.
  - A1 «La vue ? La vue est à moi aussi.» — *en* The view? The view is mine too. · *de* Die Aussicht? Die gehört auch mir.
  - B2 «La vue. Évidemment. Sachez qu'elle m'appartient aussi.»
  - C1 «La vue. Mais naturellement. Sachez qu'elle figure, elle aussi, au cadastre.»
- Reply `insolent` (Cheeky): Something cheeky, or anything else. Examples: «Bonsoir ! Belle nuit, non ?»
  *(g3.toit.insolent.r1)*
- **M. Marchand** · A2 «Bonne nuit, oui. En bas.» — *en* Good night, yes. Downstairs. · *de* Gute Nacht, ja. Nach unten.
  - A1 «Bonne nuit. En bas !» — *en* Good night. Downstairs! · *de* Gute Nacht. Nach unten!
  - B2 «Bonne nuit, en effet. En bas.»
  - C1 «Excellente nuit, en effet. En bas.»
- After any reply:
*(g3.toit.after)* The stairs, going down: Lila doubled over, Toi a step behind; above, the torch still on.
- **Lila Bonnet** *(giggling on the stairs)* · A2 «Et voilà. Demain, tout le quartier connaît l'histoire.» — *en* There you go. Tomorrow, the whole neighbourhood knows the story. · *de* Na also. Morgen kennt das ganze Viertel die Geschichte.
  - A1 «Marchand, toi et moi, la nuit. Quelle histoire !» — *en* Marchand, you and me, at night. What a story! · *de* Marchand, du und ich, in der Nacht. Was für eine Geschichte!
  - B2 «Il nous a vus, tous les deux. Demain, je raconte ça à tout le quartier.»
  - C1 «Il nous a pris la main dans le sac, tous les deux. Demain, le quartier entier sera au courant.»

#### Hook

*(g3.hook.p, silent)* Lila's banner, rolled up on the zinc: «25».
- **CAPTION** · A2 «Samedi, le Mistral a vingt-cinq ans. À suivre…» — *en* On Saturday, Le Mistral turns twenty-five. To be continued… · *de* Am Samstag wird das Mistral fünfundzwanzig. Fortsetzung folgt…
  - A1 = A2
  - B2 «Samedi, le Mistral fête ses vingt-cinq ans. À suivre…»
  - C1 «Samedi, le Mistral fête ses vingt-cinq ans. À suivre…»

### Bridge g4 · «Le quartier sait» (7–12 déc., 5 min)


#### Moment `la_dispute`

*(g4.dispute.p1)* The quai de Valmy, grey morning. Lila walks fast, hands in her pockets; Toi a step behind.
- **CAPTION** · A2 «Un matin, au bord du canal.» — *en* One morning, by the canal. · *de* Eines Morgens, am Kanal.
  - A1 «Le matin, au canal.» — *en* Morning, at the canal. · *de* Morgen, am Kanal.
  - B2 «Un matin, au bord du canal.»
  - C1 «Un matin, sur les quais du canal.»
*(g4.dispute.p2m, when {"s1.fire_photo": "margaux"})*
- **Lila Bonnet** · A2 «Encore un secret. Ici, tout le monde cache tout. Même toi.» — *en* Another secret. Here everyone hides everything. Even you. · *de* Noch ein Geheimnis. Hier verheimlicht jeder alles. Sogar du.
  - A1 «Ici, il y a trop de secrets.» — *en* There are too many secrets here. · *de* Hier gibt es zu viele Geheimnisse.
  - B2 «Encore un secret. Ici, tout le monde cache tout à tout le monde. Même toi.»
  - C1 «Encore un secret. Ici, chacun cache tout à tout le monde. Toi compris.»
*(g4.dispute.p2w, when {"s1.fire_photo": "wall"})*
- **Lila Bonnet** · A2 «C'est ma faute ? La photo est au mur, l'assurance appelle. Dis-le.» — *en* It's my fault? The photo is on the wall, the insurance is calling. Say it. · *de* Ist es meine Schuld? Das Foto hängt an der Wand, die Versicherung ruft an. Sag es.
  - A1 «C'est ma faute, la photo ? Tu penses ça ?» — *en* Is the photo my fault? Is that what you think? · *de* Ist das Foto meine Schuld? Denkst du das?
  - B2 «C'est ma faute, c'est ça ? À cause de la photo au mur, l'assureur appelle Margaux. Vas-y, dis-le.»
  - C1 «Tu me tiens pour responsable, c'est ça ? La photo au mur, l'assureur de Margaux au téléphone… Vas-y, dis-le.»
*(g4.dispute.p3, silent)* Two figures walking away from each other along the canal, in opposite directions.
- **CAPTION** · A2 «Plus un mot. Pas avant le lendemain.» — *en* Not another word. Not before the next day. · *de* Kein Wort mehr. Nicht vor dem nächsten Tag.
  - A1 «Plus un mot. Pas ce soir.» — *en* Not one more word. Not tonight. · *de* Kein Wort mehr. Nicht heute Abend.
  - B2 «Plus un mot. Jusqu'au lendemain.»
  - C1 «Plus un mot. Pas avant le lendemain.»

**Turn `g4.dispute.turn`** → Lila Bonnet · gate 3 · fallback `pardon`
*(g4.dispute.p4)* The next morning. Lila at the door of Le Mistral with two paper cups of coffee, not quite looking at Toi.
- **Lila Bonnet** *(at the door, two coffees in her hands)* · A2 «… Bon. Qui commence ?» — *en* … Well. Who goes first? · *de* … Na gut. Wer fängt an?
  - A1 = A2
  - B2 «… Bon. Qui commence ?»
  - C1 «… Bon. Lequel de nous deux commence ?»
- Task (en/de/fr): Apologise, your way. This is a path gate: what you express is read, never how well you say it. / Entschuldige dich, auf deine Art. Das ist ein Weichenpunkt: Gelesen wird, was du ausdrückst, nie, wie gut du es sagst. / Excuse-toi, à ta façon. C'est un point de bascule : ce qu'on lit, c'est ce que tu exprimes, jamais la qualité de ta phrase.
- Plain task: Say sorry to Lila, your way. / Entschuldige dich bei Lila, auf deine Art. / Excuse-toi auprès de Lila, à ta façon.
- Ask again: «Alors ? Je t'écoute.» (en So? I'm listening. · de Also? Ich höre.)
- Reply `pas_toi` (What she means, path romance): Naming what she means to the learner: not her, not a fight with her. Examples: «Je ne veux pas me disputer avec toi. Pas toi.» / «Avec toi, non. Pas avec toi.»; A1 «Pas avec toi.» / «Je ne veux pas, pas avec toi.»
  *(g4.dispute.pas_toi.r1)*
- **Lila Bonnet** · A2 «… Pas moi. D'accord.» — *en* … Not me. All right. · *de* … Nicht ich. In Ordnung.
  - A1 = A2
  - B2 «… Pas moi. D'accord.»
  - C1 «… Pas moi. Entendu.»
- Reply `equipe` (The team, path friendship): Naming the alliance: they are a team, accomplices. Examples: «On est une équipe. Pardon.» / «Toi et moi, on est ensemble là-dedans.»; A1 «On est une équipe.» / «Toi et moi, une équipe.»
  *(g4.dispute.equipe.r1)*
- **Lila Bonnet** · A2 «Une équipe. Avec deux cafés. Pardon aussi.» — *en* A team. With two coffees. Sorry too. · *de* Ein Team. Mit zwei Kaffees. Entschuldige auch.
  - A1 «Une équipe. Deux cafés. Pardon aussi.» — *en* A team. Two coffees. Sorry too. · *de* Ein Team. Zwei Kaffees. Entschuldige auch.
  - B2 «Une équipe. Avec deux cafés, en plus. Pardon aussi.»
  - C1 «Une équipe. Avec deux cafés, qui plus est. Pardon aussi.»
- Reply `pardon` (Sorry): A plain apology that names neither, or anything else. Examples: «Pardon.» / «Excuse-moi.»
  *(g4.dispute.pardon.r1)*
- **Lila Bonnet** · A2 «Pardon aussi. Ton café refroidit.» — *en* Sorry too. Your coffee's getting cold. · *de* Entschuldige auch. Dein Kaffee wird kalt.
  - A1 «Pardon aussi. Ton café est froid.» — *en* Sorry too. Your coffee is cold. · *de* Entschuldige auch. Dein Kaffee ist kalt.
  - B2 «Pardon aussi. Ton café refroidit.»
  - C1 «Pardon aussi. Ton café est en train de refroidir.»
- After any reply:
*(g4.dispute.after, silent)* Two paper cups side by side on the café's window ledge.
- **CAPTION** · A2 «Une dispute. Et le lendemain, deux cafés.» — *en* An argument. And the next day, two coffees. · *de* Ein Streit. Und am nächsten Tag zwei Kaffees.
  - A1 «Un jour difficile. Puis, deux cafés.» — *en* A hard day. Then, two coffees. · *de* Ein schwerer Tag. Dann zwei Kaffees.
  - B2 «Une dispute. Et le lendemain, deux cafés.»
  - C1 «Une dispute. Et, le lendemain, deux cafés.»

#### Hook

*(g4.hook.p, silent)* Lila's canvas bag on a chair; the corner of an envelope sticks out.
- **CAPTION** · A2 «Dimanche, Lila a une lettre dans son sac. À suivre…» — *en* On Sunday, Lila has a letter in her bag. To be continued… · *de* Am Sonntag hat Lila einen Brief in der Tasche. Fortsetzung folgt…
  - A1 «Dimanche, Lila a une lettre. À suivre…» — *en* On Sunday, Lila has a letter. To be continued… · *de* Am Sonntag hat Lila einen Brief. Fortsetzung folgt…
  - B2 «Dimanche, une lettre attend au fond du sac de Lila. À suivre…»
  - C1 «Dimanche, une enveloppe dort au fond du sac de Lila. À suivre…»

## 5. The all-provider-down season (proof, with the proposal applied)

`tests/test_wp124b_recovery.py::test_an_all_down_season_reaches_its_ending_with_prerequisites_and_choices_intact`. Every generated day is lost from T1 to T8. The learner makes the «keeper» choices of `test_season_one`'s endings test, and «Un thé» at the order card.

| Band | Days to the finale | Reprises | Recoveries | Ending | Prerequisites |
|---|---:|---:|---:|---|---|
| A1.1 | 27 | 7 (one per gap) | 7 (4 bridges, 3 tentpole jumps) | «Garder» | all 6 required moments staged; gates 1–5 read |
| A2.1 | 27 | 7 | 7 | «Garder» | same |
| B1.1 | 27 | 7 | 7 | «Garder» | same |
| C1.1 | 27 | 7 | 7 | «Garder» | same |

Sequence: `t1.a t1.b reprise bridge(g1) t2.a t2.b reprise bridge(g2) t3.a t3.b reprise bridge(g3) t4.a t4.b reprise bridge(g4) t5.a t5.b reprise t6.a* t6.b reprise t7.a* t7.b reprise t8.a* t8.b`, where `*` marks a tentpole served as the recovery.

What holds at the end of that run:
- The learner's choices are intact: `s1.letter_trusted_to = margaux`, `user.usual_order = un thé`, Margaux persuaded, `s1.ending = garder`.
- All seven gaps are recorded as shortened, g1–g4 via a bridge and g5–g7 via the tentpole.
- Without the proposal, the same outage stalls in g1 on re-reads of T1 B, which is the safe behaviour.

**The forced-outage life walk.** These runs had the proposal applied: `WALK=1 WALK_FAIL_RATE=<rate>`, deterministic per life, scripted provider. In the sequences below, `R` is a reprise day and every other entry is the season day played that day.

- **Rate 1.0 (all down), a1-de-fresh average and c1-de struggling.** The finale is reached on day 27, and 13 tentpole headlines are read in 30 days. All 7 gaps are recorded as shortened. Sequence: `t1.a t1.b R g1.1 t2.a t2.b R g2.1 … t8.a t8.b R R R`; the last three are re-reads after the finale (§2, the epilogue's day). The WP-124b checks are clean. c1 passes every walk check.
  - The a1 life fails other walk checks, but only on **bible pages that A1 lives never reached in 30 days before**:
    - T5 B's «adieu» above A1.1 in recall;
    - T6's «C'est le cahier d'Odile.» / «Das ist Odiles Notizbuch.» (the name check reads «Odiles» as a missing name);
    - T8 B's `setup_native` falling back to French («La lumière est fausse»).
  - They are findings for the content owners, not for this package.
- **Rate 0.21, three lives, all pass, including the WP-124b checks.**
  - a1-de-fresh average: 10 days lost. g1 was closed by a bridge after `g1.2 R`, g3 by the T4 jump after `g3.2 R` (its roof scene had already been staged), and 7 headlines were read.
  - a2-de-placed average: 9 days lost. g1 was closed by a bridge.
  - c1-de struggling: 4 days lost, never two in a row in one gap.


## 6. Tests

- **`tests/test_wp124b_recovery.py`** (24 tests; 9 need the proposal and skip without it):
  - the policy per failure count;
  - prerequisites gate the tentpole jump;
  - safe without bridges;
  - after the finale;
  - shortened gaps end at once, with no flex;
  - a bridge stages only answered moments and closes the gap only then, idempotent per event;
  - a recovered tentpole records its gap;
  - the bridge rules refuse a fabricated choice, a foreign flag, a loose fixed fact, a missing or stray moment, a spoiler and a gate without both paths;
  - a broken bridges file means no bridge;
  - end to end: the tentpole jump, the reprise kept without bridges, the counter reset, mixed outages, reload and a double finish (and the revision change that discards a prefetch);
  - with the proposal: the shipped bridges hold; the first gap after T1; the gate bridge records the expressed signal; the all-down season at four bands;
  - the walk checks, which fire and stay quiet.
- **`tests/walk_checks_wp124b.py`**:
  - `check_reprise_runs`: never more than `MAX_CONSECUTIVE_REPRISES` reprises in a row; a reprise of the finale is exempt.
  - `check_season_cursor`: the played log never shrinks, the season never moves back, and a shortened gap stays recorded.
  - Both run in the life walk when `WALK_FAIL_RATE` is set. To run them on every life, add `problems += walk_checks_wp124b.check_life_wp124b(record)` to `test_a_month_of_a_whole_life`.

## 7. To apply the proposal

1. `git apply docs/implementation/atelier-v2/WP-124B-BRIDGES-PROPOSAL.patch`. It adds the two data files and the six `tasks.json` entries, and pins one WP-124a test to the no-bridge path: that test asserts two reprises in a row in g1, which a bridge now replaces.
2. Check:
   - `venv/bin/python scripts/season_check.py`
   - `venv/bin/python scripts/season_levels.py --file bridges --strict`
   - `venv/bin/python -m pytest tests/test_wp124b_recovery.py tests/test_wp124a_season_reprise.py tests/test_season_one.py -q`
3. Set `deviation.approved` in `bridges.json` to the approval date.
