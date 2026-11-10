# The red thread: design, 10 November 2026

*Deliverable 2 of the mandate «give La clé d'Odile its red thread back». It answers `red-thread-diagnosis-2026-11-10.md`. This is a proposal: nothing is built, and Vincent decides between the options in section 2 before any code is written.*

---

## 1. Thesis

**A serial is a promise kept daily.** A reader comes back when three things are true every single day: they know where the story is going, they saw it get closer today, and they are owed something specific tomorrow. A language learner needs a fourth: what they managed to say has to matter, because that is the only reward that is about *them* and not about the plot.

Atelier already has the hard part. The season is planned to the day: 45 generated days, each with a `before`, an `after`, a hook and a turn, all pointing at the next tentpole. The diagnosis shows that the plan and the page have come apart at four seams:

1. **"Done" means "served".** The engine marks a beat as done when a page with its id was shown, even when the page's last line cancels the beat («je ne choisis pas encore»). The books and the page disagree, and every later day is written from the books.
2. **The most important sentence of the day is written by the model with the least information.** The ending comes from the small live model, seconds after the learner's reply, under two rules that pull away from the plan: answer the learner's question first, and never invent success.
3. **The checker is right and has no power.** The critic named the fault on 16 of 18 reads. Each time a whole new page was drawn, and on 8 of 10 days the refused page was served anyway.
4. **The things a reader steers by are treated as leftovers.** The hook is drawn at random from old loose ends, the destination and the countdown are never shown, the learner's words are not kept, and the world is told what the story needs only after the story has been there.

So the design rests on one idea:

> **A day is a transaction on the story's books. It is entered only when it is true on the page, and the page is not served until it can be entered.**

Everything else follows from splitting a day's `after` into the four things it has been hiding:

| Part | What it is | Who owns it |
|---|---|---|
| **The floor** | What becomes true today whatever the learner says. «There is a menu.» | The plan. Written and checked at night, by the strong model. |
| **The mark** | What the learner's own French adds, kept word for word. «One canapé is called *Le petit bateau*.» | The learner. Captured live, always with an authored default. |
| **The hook** | The one thing owed tomorrow. «Lila needs the photo for the middle of the wall.» | The plan. Shown by code, the same line everywhere. |
| **The destination** | Why today matters. «Saturday is the party. Three days.» | The season. Shown by code, on every day of the gap. |

The learner's reply decides **how** the day lands and never **whether**. The models keep everything they are good at: the staging, the jokes, the texture, the reaction to what was actually said. They lose only the power to forget the plan.

What the learner should notice is simple. The top of the page says where the week is going and how many days are left. The page ends on a change they can name. Their own words are on a menu card. And the last line tells them what tomorrow is, and tomorrow is that.

---

## 2. Three options

### Option A · «Die Schrauben anziehen»: patch the pipeline

Keep the pipeline exactly as it is and close the four seams with the smallest change each: pass `after` to the live model as a rule and check its ending with a second small call; print the plan's hook instead of the random teaser; put the countdown and the week's line into the brief; make the critic's "reaches the after" verdict a gate with one rewrite.

- **What the learner notices.** The right hook, from the first day. Endings that land more often.
- **For it.** Small: about four PRs. No new data to author. The hook fix alone removes the most visible symptom.
- **Against it.** The plan is still English prose passed through four models, so "reaches the after" is still a judgement, not a fact. The ending is still improvised by the small model, now under three rules that conflict (answer the question, be honest, land the beat); to enforce it live we must either add a check to the last turn (two to four seconds, at the moment the learner is waiting) or skip the check. Nothing is remembered: the canapé's name still goes nowhere. The retry loop still redraws whole pages.
- **Cost per day.** As today, about $0.55 to $0.80 at night, plus about $0.01 for the ending check.
- **Risk.** Low to build, high of disappointing: I expect the hook to be fixed for good and the landing rate to improve without becoming reliable. In three weeks we would be reading the same critic lines with smaller numbers.

### Option B · «Le contrat du jour»: the day as a typed contract, with the ending written at night (recommended)

Each planned day gets a small typed contract in the season data (floor, mark, hook, place, one-ask turns per level). The night writes the page **and its landings**: the closing panels for each way the day can go, with a slot for the learner's words. The live model keeps reacting to every reply, but on the closing turn it only chooses the landing and hands over the learner's words; it no longer writes the ending. A page that fails its contract is repaired panel by panel, then replaced by a short authored page for that same beat, and never served as a refused draft. The hook, the countdown and a one-line «Précédemment» are drawn from the contract by code. A small story ledger records what each day made true and what the learner marked, and tells the forge which rooms the next seven days need.

- **What the learner notices.** Everything in the last paragraph of the thesis.
- **For it.** The beat cannot be undone, by construction and not by persuasion. No model call is added to a live turn; the last turn gets shorter. Repair replaces redraw, so nights get cheaper. The learner's words become durable. It uses what exists: the day plan, the planner's `replies`, the tentpoles' ask-again lines and `{name}` slot, the agency pilot's `TurnContract`.
- **Against it.** It needs authored content: 45 contracts (an extension of the day plan that is already waiting for the owner's review) and 45 short fallback pages. Landings written in advance can feel less alive when a learner says something nobody imagined; the live reaction line and the mark are the answer to that, and it has to be measured. It is the largest of the three to build: about eight slices.
- **Cost per day.** About $0.31 for a clean night, about $0.42 with one repair, about $0.53 in the worst case (estimates from the measured call prices; the replay confirms them). Live turns unchanged.
- **Risk.** Medium. The main one is scope: the ledger must stay small (section 3.2). The second is the small model picking the wrong landing, which is why one landing is always the safe default and lands the beat anyway.

### Option C · «La saison écrite»: all 45 days authored, the model only reacts

Treat the gap days like tentpoles. Draft every generated day once, per level, with the strong model in one batch, review them by hand, and ship them as data with slots for the learner's name, words and choices. At run time nothing is written; the live model only reacts inside the page.

- **What the learner notices.** A perfectly coherent season. And, after a while, that the story does not really listen: a day cannot pick up what they said on Tuesday unless a slot was planned for it.
- **For it.** The highest fidelity possible and nearly free to run. No critic, no retries, no 02:20 risk.
- **Against it.** It gives up the product's central promise, a story that is theirs. It moves the whole cost to the owner: about 135 pages to review for this season (45 days at three levels), and again for every season. Levels and interface languages multiply the content. Personal callbacks, the «Demain» pick and the acts would have to be rebuilt as slots.
- **Cost per day.** About $0.01. One-off: roughly $30 to $60 of drafting and several evenings of owner review.
- **Risk.** Low technically, high for the product.

### Side by side

| | A · patch | **B · contract** | C · authored |
|---|---|---|---|
| The beat always lands | more often | **yes, by construction** | yes |
| The planned hook is shown | yes | **yes** | yes |
| The learner's words come back | no | **yes** | only where slotted |
| The story still answers the learner | yes | **yes** | weakly |
| Destination and countdown visible | if added | **yes** | yes |
| World pulled by the story | no | **yes** | possible |
| Night cost per day | $0.55 to $0.80 | **about $0.31 to $0.42** | about $0.01 |
| Added wait on a live turn | 2 to 4 s on the last turn, or no check | **none** | none |
| Content to author | none | 45 contracts, 45 short fallbacks | about 135 pages per season |
| Size | about 4 PRs | about 8 slices | data, plus a simpler runtime |

### Recommendation

**B, started with A's cheapest win, and with C as its safety net.** The first slice of B that changes behaviour is the deterministic one (hook, countdown, «Précédemment» from the contract), which is Option A's best part and is visible the next morning. B's fallback tier is a small piece of C: one short authored page per beat, used only when the night fails, so the promise "a day is always served" finally means "that day", not "some page".

---

## 3. The recommended design in detail

### 3.1 The day contract

The `days` entries of `gaps.json` grow from prose into a contract. The canapé day, as it would be authored:

```json
{
  "day": 5,
  "premise": "les_canapes",
  "place": "marin_lila_flat",
  "place_alt": "le_mistral",
  "lands": [
    {"id": "g3.menu", "text": "The party has a menu of three canapés.", "show": ["menu"]}
  ],
  "turns": [
    {"id": "keep",
     "ask": {"a1": "Tell Marin which canapé stays.",
             "b1": "Tell Marin which canapé to keep, and why, kindly."},
     "ask_again_fr": "Le un, le deux, le trois ? Lequel reste ?"},
    {"id": "name",
     "ask": {"a1": "Give the canapé a name."},
     "mark": {"id": "g3.canape_name", "kind": "name", "max_words": 4,
              "default_fr": "le canapé de {name}",
              "comes_back": ["g3.7", "t4"]}}
  ],
  "routes": [
    {"id": "named", "when": "The learner picks one and names it."},
    {"id": "picked", "when": "The learner picks one and gives no name."},
    {"id": "elsewhere", "default": true,
     "when": "Anything else: a question, a refusal, silence. Marin chooses alone and takes the name from something the learner said."}
  ],
  "also": {"if": "s1.marchand_invited", "show": "Marchand's reply card: «J'y serai. M.»"},
  "hook": {"speaker": "lila_bonnet", "about": "au_milieu_du_mur",
           "fr": {"a1": "Demain, j'ai besoin de toi. Il manque la photo du milieu."},
           "must_name": ["photo", "milieu"]},
  "after_fr": {"a1": "Il y a un menu. Un canapé s'appelle « {g3.canape_name} »."},
  "closing_job": "mark"
}
```

and once per gap:

```json
"destination": {"tentpole": "t4", "title_fr": "Les 25 ans du Mistral",
                "when_fr": "samedi", "stake_fr": "Samedi, Gus et Marin veulent parler."}
```

What each field buys, against the diagnosis:

| Field | It ends this failure |
|---|---|
| `lands` (the floor, with ids) | "Done" meaning "served". A fact is entered when its landing has played. |
| `turns[].ask` per level, one ask each | The A1 guard refusing the plan's own turn (3 of Vincent's last 4 days). A build test runs the same guard over every authored ask, so the conflict is found once, at authoring time, not nightly. |
| `ask_again_fr` | The off-topic question taking over the ending. One authored re-ask, as the tentpoles already have. |
| `mark` with `default_fr` and `comes_back` | The learner's words going nowhere. |
| `routes` with exactly one `default` | The ending being improvised. |
| `hook` with `about` | The random teaser. A build test checks that each hook's `about` is the next day's premise or the tentpole. |
| `place`, `place_alt` | The beat being moved silently, and the forge not knowing what is coming. |
| `after_fr` | Tomorrow's «Précédemment» and today's "what changed" line, without a model. |
| `closing_job` | The word hunt and the story turn fighting for the same reply. A closing turn has one job: a mark or a word, never both. |

Rules for the contract itself:

- **Small.** At most two turns, at most four routes, one mark, one hook. A day that needs more is two days.
- **It says what may stay open.** Anything not in `lands` is free: which three canapés, what they taste of, who else is in the kitchen, what the joke is.
- **It extends, it does not replace.** `must_not`, `sets_allowed`, `required`, `needs`, `by_flag` and every canon guard stay exactly as they are and still run first.
- **One vocabulary.** The agency pilot already has `Contract` and `TurnContract` (`season/agency.py`). The day contract is built on those types, not beside them.
- **Authored, reviewed, versioned.** I draft the 45 contracts from the existing day plan; Vincent reviews them like the day plan. Gaps 3 and 4 come first because learners are in them now.

### 3.2 The story ledger

The diagnosis found about nine partial records and no place that says what this gap has made true. The design does not merge them. It adds one thin layer:

- **One read model**, `story_ledger.read(state)`, that answers the four questions every lane asks: *what is true so far in this gap* (one line per played day), *what did the learner mark* (word for word, and the corrected form), *what is owed and when* (promises, plants, the next hook), and *how far is the destination*. It reads the existing records and the two new ones below.
- **Two new typed records**, written at settle and nowhere else:
  - a **fact**: `{id, day, route, source: learner | default | settled_without}`;
  - a **mark**: `{id, said, kept, day, comes_back, returned_on}`. `said` is the learner's exact words. `kept` is the corrected form the evaluator already produces, and it is what a menu card prints.
- **Every lane that writes story text reads the same view**: the planner, the author, the live model, the contract check, the teaser, the Home card and, as they are touched, the Courrier and the Journal. Lanes move over one at a time; none is rewritten for this mandate.
- **Validation** is the contract check of section 3.6: it receives "true so far" and refuses a page that contradicts it (the ticket date of g3.1 is the model case).
- **Storage** is the JSON state the other records already live in. No table, no migration, no backfill.
- **Days played before the contract are unknown, not landed.** The diagnosis shows why: the canapé day is in the books as done and its last line says there is no menu. So for a learner in the middle of a gap, an earlier day's facts enter the read model as `source: unverified`. A page may not build on an unverified fact silently. Either the page makes it true in plain sight (Thursday's first panel: Marin pins up the menu he wrote overnight), or the day does not rely on it. The contract check treats "relies on an unverified fact without showing it" as a failure, and a fact shown this way is entered as verified from then on. The first contract day of each learner is therefore also the day the books are put right.

This is deliberately the narrow end of issue #145: enough state to make a day a transaction, and a single door through which later work can pass.

### 3.3 Where the hook comes from

- On a planned day the hook **is** the contract's hook. It is the last panel of every landing, spoken by its `speaker` in the scene, and the same sentence is the «À suivre…» line on the Done screen, the line on the Home card and the text of the evening push.
- The author may rephrase the line in the speaker's voice. Two checks hold it to the promise. The `must_name` words are a cheap first filter in code. The words alone prove nothing (a line can say «photo» and «milieu» and owe the learner nothing), so the contract check of section 3.6 also reads the hook for its meaning: does it say who needs what from the learner tomorrow, and is that tomorrow's beat. If either check fails, the authored line is used as written. There is no repair round for a hook; the authored line is always good enough.
- If the learner picks tomorrow with «Demain», the hook is the picked beat's own invitation, which exists today («On va …»).
- The day before a tentpole keeps `season_teaser()`.
- `next_teaser()` is not called on a season's planned days. Loose ends are not teasers; they are debts (section 3.5).

### 3.4 The reply and the ending

This is the centre of the design.

**At night** the author writes the page and, in the same call, one **landing** per route: two or three closing panels in which the floor becomes true, with the mark's slot where the route has one, ending on the hook. Landings are held to the same guards and the same contract check as the page. The planner already imagines replies (`PagePlan.replies` with `gist`, `intent`, `then`); a landing is that `then`, written out and checked.

**Live**, each turn works as today: the character reacts to what the learner actually wrote, in one or two lines. Three things change.

1. **A question is answered, then the scene comes back.** If the learner asks something else at a contract turn (what a word means, where someone is), the character answers in character and then puts the turn's question again in simpler words, using the authored `ask_again_fr`. Once. The learner's question is honoured and the day is not spent on it.
2. **On the closing turn the live model chooses, it does not write.** It returns the route and, where there is a mark, the span of the learner's reply that is the mark. Code checks both: the route must be one of the contract's, else the default; the span must be the learner's exact words (the existing fabricated-quote check), short enough, and clean of the gap's `must_not` patterns and the canon's «Never»s, else the authored default. Then the night-written landing plays with the mark filled in.
3. **The reaction line before the landing stays live and stays short.** It is told what the next panel is and that it may not decide, refuse, promise or announce anything.

Why this is honest: the rule «an honest ending, not invented success» is kept. The default landing never pretends the learner did the task. It shows the story moving on without them: Marin chooses alone. That is the sentence the planner prompt already contains and nothing enforced: *the reply decides how the day lands, never whether the story moves on.*

**A day the learner leaves half-way** is settled on its default route when the next day is prepared, and the next page says so in its «Précédemment» line («Hier, Marin a choisi sans toi.»). The books and the page agree again.

### 3.5 Payoffs: marks, promises and plants

- **Marks come back where the contract says.** `comes_back` names days or tentpoles. The brief of such a day carries the mark as a *due payoff*, and the gate checks that the page shows it. For the canapé: the menu card on the counter on day 7, and one line of Saturday's page. The tentpole change is a single slot with an authored default, the same device as the existing `{name}` slot; it touches authored canon, so it is Vincent's to approve line by line.
- **A plant needs a due date.** A generated page may plant a detail only if it also names the day in this gap that pays it. The gate refuses a plant without one. At most one new plant a day.
- **At most one debt falls due per day**, listed in the brief as "due today". The planner stages it or says why not; the contract check reads the page for it.
- **A debt that passes its date is closed, not recycled.** It leaves the pool. It is never promoted to a teaser.
- **Existing loose ends** (the card in Marin's pocket with Gus's handwriting) are given a due date inside the current gap or closed when the flag is switched on, by a rule, not by hand.

### 3.6 Check, repair, fall back

At night, in this order:

1. **Deterministic gate.** All existing guards, unchanged. Then the contract lint, pure code: the place is the contract's `place` or `place_alt`; the task line is the contract's ask for this level; every landing contains its `show` words and its mark slot; the last panel is the hook and names its `must_name` words; the destination's `when_fr` appears on the page; no new plant without a due date.
2. **Contract check.** One small model call with the contract, "true so far", the page and its landings. It answers item by item: is each `lands` fact true at the end of each route; does anything contradict what is already true; does the page lean on an unverified fact without showing it (section 3.2); is the due payoff shown; does the hook, if rephrased, still make the contract's promise for tomorrow (section 3.3). Each failure names the panel. About $0.02.
3. **Targeted repair.** The author receives the page, the failing items and the panel numbers, and rewrites only those panels. At most two repairs. About $0.09 each, against $0.27 for a redraw today. Guards and the critic no longer share one budget.
4. **Fallback.** If the page still fails: the authored short page for this beat (the C tier), four panels at A1 French, readable at every level, with its own landings. It is served and counted. A refused draft is never served on a contract day; `journey_story_critic_override` stops firing there.
5. **The critic becomes a reader, not a gate.** It still reads the page for craft (do people talk like people) and its notes go into the repair when there is one. Taste does not block a page; the plan does.

Live, there is nothing to check: the landing was checked at night, and route and mark are checked by code.

### 3.7 How the world pulls the story

Vincent's rule of 8 November stands: «Erst erwähnen, dann betreten». The design turns it into a pipeline instead of a restriction.

1. **Mention.** Every contract names its place. A build test checks that a place is named on a page at least one day before a day is set there; usually that is the previous day's hook («Demain, chez Marin.»).
2. **Build.** The forge's season queue reads the places of the **next seven planned days of every active learner**, ordered by how soon the first of them gets there. The public frontier endpoint gains the day (`g3.6`), not only the gap. Had this existed, the roof would have been queued when Vincent entered gap 3 on 5 November and Marin's kitchen right behind it; at one place a night both could have stood before he reached them on the 8th and the 10th. The forge keeps its rhythm of one place a night and merges its own PRs as now.
3. **Enter.** On the day, the page is set at `place`. If the room is not built yet, it is set at `place_alt`, which is authored and canon-safe. If there is neither, the plan swaps the day with a later one that `needs` allows, the way «Demain» already reorders days. The writer no longer guesses, and the canon is no longer loosened by a guard.
4. **Fresh places attract.** A place built since the learner's last day, and not yet visited, is listed in the brief as *fresh*. A contract may list it as an alternative, and the side act («À côté») goes there first, staging one of the gap's small moments. So a new room shows up in the story within a day or two of being built.
5. **Play it there.** Phase one, «tu es là»: on a day whose place is built, the day opens in the room and its lines play where the characters stand. The plumbing exists for the owner build; generated pages need to carry their place and speakers in the form `stage_view` walks. Phase two: the author adds simple blocking (who stands where, one move) from the contract, and `STAGED_DAYS` stops being a hand-kept list. Opening the quarter's door to all learners stays Vincent's switch.

### 3.8 The arc on screen

All of it from the contract and the ledger, by code, with no model call and no new visual element (av2 caption style, existing tokens):

- **A strip above the page and on the Home card:** the gap's title and the countdown. «Avant la fête · noch 3 Tage bis Samstag».
- **One line of «Précédemment»** above the first panel: yesterday's `after_fr`, with the learner's mark in it.
- **On the Done screen:** "what changed today" (today's `after_fr`) and the hook.

### 3.9 The learner who finishes late

Today a learner who closes yesterday's day in the morning gets today's page from the cheapest path (diagnosis, section 4). With a floor this is fixable: the night can write tomorrow's page **before** yesterday is finished, relying only on what yesterday's contract guarantees on every route, and referring to yesterday's mark through its slot. The page is a little less personal (it cannot quote a reply that has not been written yet) and it is written by the real writer. The one-call live path stops being used for planned days; it remains as the last resort it was meant to be.

### 3.10 Measuring it

**Golden transcripts first, and they must fail today.** Recorded, replayable cases in the existing harness (`scripts/gold_transcripts.py`, `tests/prompt_regression/`):

- the canapé day with Vincent's real reply, checked for: the menu exists at the end, a canapé has a name, the hook is Lila's, Saturday is named;
- g3.2, g3.3, g3.4 and g4.4 for "the hook is on the page";
- g3.1 for "an established fact is not replaced".

**Plan fidelity, per served day:**

| Metric | Meaning | Today |
|---|---|---|
| `landed` | every `lands` fact is true at the end of the day | not reached on at least 4 of 10 days |
| `hook_kept` | the last line is the planned hook | 0 of 9 walked days |
| `destination_named` | the page or its frame names where the week is going | never by design |
| `mark_returned` | a mark that fell due was shown | no marks exist |
| `first_pass` | the page passed its contract without repair | first critic read accepted on 0 of 10 |
| `refused_served` | a page its checker refused was served | 8 of 10 |
| cost per day | measured, not estimated | $0.55 to $0.80 |

**The baseline replay** (needs Vincent's go, because it is paid): gap 3, days 1 to 7, at A1 with German interface and at B1 with English interface, each day played twice with a scripted learner (once on plan, once off topic), with the real writer, critic and live models, read by `story_judge`. That is 14 pages and 28 endings. Estimate: $10 to $11; I would cap the run at **$15**. Each re-score after a slice costs about half of that under the new design.

**A reader who binges.** Once a week, per gap, the judge reads the seven served days in one sitting and answers three questions: what was this week about, what changed each day, what are you waiting for now. It is a measurement, never a gate. A few cents per learner and week.

**The existing instruments stay:** the 30-day experience walk, extended to read the strip and the hook, and the live-walk rubric with «Would come back» at 4 or more as the target.

### 3.11 What I am deliberately not doing

- **Not touching the canon or its guards.** No invariant, guard or test is loosened, skipped or quarantined. The tentpoles are not rewritten; the single proposed slot in T4 is put to Vincent on its own.
- **Not building the grand ledger.** No new table, no migration, no merge of the nine records. The Courrier, the Journal and the cast registry (#147) are not rewritten here.
- **Not branching the plot.** The learner changes how a day lands and leaves marks; there are no alternative storylines.
- **Not adding a model call to a live turn**, and not checking a live ending with a model.
- **Not making the critic stricter.** Craft stays advisory. Only the plan is a gate.
- **Not writing days from templates.** The authored short page is a net for a failed night, not the way days are made.
- **Not removing the word hunt.** It is kept off the closing turn of a mark day, nothing more.
- **Not changing the look.** One caption strip in av2. No new fonts, colours, mascots or social features. Image generation is not touched.
- **Not opening the quarter to every learner, and not blocking all 45 days in 3D.** Phase one only, behind the existing switch.
- **Not changing the forge's rhythm.** One place a night, its own PRs; only its queue learns to look ahead.
- **Not writing to the production database by hand, and not backfilling played days.**

---

## 4. Today's canapé day under this design

*Illustrative. The lines below show the shape; they are not canon text, and the night's writer would phrase them its own way within the contract.*

**Who and when.** Vincent, A1, German interface. Gap 3, day 5. In the story: Wednesday 2 December, three days before the party.

**Where.** Marin's kitchen (`marin_lila_flat`). Under section 3.7 it was named in yesterday's hook («Marin a besoin de toi. Demain, chez lui. Viens avec faim.») and queued for the forge on 5 November. Had it not been built, the page would be set at the zinc of Le Mistral after closing, the contract's `place_alt`.

**Frame, drawn by code.**

- Strip: **Avant la fête · noch 3 Tage bis Samstag**
- Précédemment: «Hier : Gus et Marin veulent parler samedi. Tous les deux.»

**The page.**

| Panel | What is on it |
|---|---|
| 1 | Caption: «Mercredi soir. Chez Marin. Samedi, c'est la fête.» Six small plates on the table, each with a number on a scrap of paper. **Marin:** «Six canapés. Zéro menu. Goûte !» |
| 2 | *Silent.* The learner's hand over number two. Marin watching, much too close. |
| 3 | **Marin:** «Alors ? … Non, attends. Ne dis rien.» A beat. «Si. Dis.» *(If Marchand was invited: a card under a magnet on the fridge, «J'y serai. M.»)* |
| 4 | Marin holds up three fingers. **Marin:** «Samedi, il y a trois canapés. Pas six. Quel canapé reste ?» |

Task line, from the contract's A1 ask: **«Sag Marin, welches Häppchen bleibt.»** One ask, five words: the level guard has nothing to refuse.

### Reply A: the learner plays along

> **Learner:** «Le deux. Il est bon.»
>
> **Marin** *(live)*: «Le deux ! Ma grand-mère disait toujours : le deux, c'est le bon. Mais il n'a pas de nom. Tu lui donnes un nom ?»

Task line: **«Gib dem Häppchen einen Namen.»**

> **Learner:** «Le petit bateau.»

The live model returns `route: named` and the span «Le petit bateau». Code checks that these are the learner's own words and that the route exists, then plays the landing written at night:

| Landing | What is on it |
|---|---|
| L1 | Marin writes on a card, the tip of his tongue between his teeth. On the card: **MENU · 1. « Le petit bateau »**. Caption: «Il y a un menu.» |
| L2 | **Marin:** «C'est un signe, ça. Samedi, il est sur le menu.» |
| L3 | Lila in the doorway, a roll of tape around her wrist. **Lila:** «Demain, j'ai besoin de toi. Il manque la photo du milieu.» |

Done screen: *Heute:* «Il y a un menu. Un canapé s'appelle « Le petit bateau ».» · *À suivre :* «Demain, j'ai besoin de toi. Il manque la photo du milieu.»

Entered in the books: the fact `g3.menu` (route `named`, by the learner) and the mark `g3.canape_name` = «Le petit bateau», due on day 7 and at the party.

### Reply B: what Vincent actually wrote

> **Learner:** «C'est quoi, un canapé ?»
>
> **Marin** *(live, answering first, then bringing the scene back with the authored re-ask)*: «Un canapé ? C'est petit. Du pain, et dessus, quelque chose de bon. On mange ça debout. Alors : le un, le deux, le trois ? Lequel reste ?»
>
> **Learner:** «Je ne sais pas.»

The live model returns `route: elsewhere`. There is no name, so it offers the learner's own «C'est quoi» as the span. The default landing plays:

| Landing | What is on it |
|---|---|
| L1 | Marin looks at the six plates, eats number four himself, and nods. **Marin:** «Bon. Je choisis. Le deux, le quatre, le six.» He writes the card. Caption: «Il y a un menu.» |
| L2 | **Marin:** «Et le deux s'appelle « C'est quoi ? ». C'est toi qui l'as dit.» |
| L3 | Lila in the doorway, a roll of tape around her wrist. **Lila:** «Demain, j'ai besoin de toi. Il manque la photo du milieu.» |

Done screen: *Heute:* «Il y a un menu. Un canapé s'appelle « C'est quoi ? ».» · *À suivre :* the same line of Lila's.

Entered in the books: `g3.menu` (route `elsewhere`, decided by Marin) and `g3.canape_name` = «C'est quoi ?», taken from the learner's words. Had the learner written nothing usable at all, the name would be the authored default, «le canapé de {name}» with the learner's first name, and line L2 its plain variant.

Set this beside what was served on 10 November: «Pour samedi, je ne choisis pas encore ; je garde mes six idées avec moi.» and a teaser about a card in Marin's pocket. The question about the word is answered in both versions. Only one of them is an episode.

**And then.** Thursday's page opens with «Hier : il y a un menu. Un canapé s'appelle « C'est quoi ? ».» and is the photo for the middle of the wall, as promised. On Friday the menu card stands on the counter of Le Mistral. On Saturday one line of the party carries the name.

**At B1 with English interface** the same contract gives the fuller turn («Tell Marin which canapé to keep, and why, kindly»), longer panels and the same floor, mark and hook.

---

## 5. Order of work, once Vincent has decided

Each slice is one PR behind `STORY_DAY_CONTRACT` (off by default, switched on for the owner and the walk account first), with focused tests and the full suite green. Re-scored against the baseline after every slice. Merging deploys, so every merge is Vincent's call.

| # | Slice | The learner notices | Cost |
|---|---|---|---|
| 0 | Golden transcripts and the baseline replay | nothing | paid run, about $10 to $11, capped at $15, **needs go** |
| 1 | Contracts for gaps 3 and 4 as data, loader, build tests (asks pass the level guard, hooks point at the next day, places are mentioned first) | nothing | none |
| 2 | Hook, strip and «Précédemment» from the contract | the right «À suivre…», the countdown, yesterday in one line | none |
| 3 | Landings at night, route and mark live, facts and marks entered at settle | the day ends on its change; their words on the page | about $0.02 more per night |
| 4 | Contract check, targeted repair, authored fallback per beat; the override retired on contract days | no more refused pages | nights get cheaper |
| 5 | Marks come back (`comes_back`), debts with due dates | their canapé on Saturday's menu | none |
| 6 | World pull: day-level frontier, forge queue seven days ahead, fresh places | new rooms appear in the story | none |
| 7 | Pages written on the floor for late finishers | no cheap morning pages | about $0.30 per affected day |
| 8 | Gap days in the quarter, phase one | the day opens in its room (owner build) | none |

Against the mandate's suggested order (a to f): the hook and the week's line move ahead of the ending, because they are pure code and visible the next morning; the rest follows the same sequence. The contracts for gaps 1, 2 and 5 to 7 are authored alongside, each before a learner reaches it.

## 6. What I need from Vincent

1. **Which option:** A, B or C.
2. **The go for the baseline replay**, about $10 to $11 with a hard cap of $15.
3. **The stored page of 10 November.** A read of the production database was refused in this session and I did not work around it. For the golden transcript I need that one page: either a read is granted, or slice 0 adds a small owner-only export, or the case is rebuilt from the lines quoted in the mandate.
4. **Later, line by line:** the contract texts for gaps 3 and 4, and the one slot in Saturday's page.

## 7. Risks, plainly

| Risk | What I do about it |
|---|---|
| Landings feel canned | The reaction line stays live; the mark is the learner's own words; the judge scores "did the story answer me" before and after. If it drops, routes get finer before anything else. |
| The small model picks the wrong landing | Every landing lands the floor. A wrong pick costs nuance, never the beat. Golden transcripts cover both replies. |
| The ledger grows into #145 | Two records and one read model. Anything more is a separate decision. |
| Authoring load on the owner | I draft everything from the existing plan; review is line by line, two gaps at a time. |
| A learner is mid-gap when the flag flips | Contract days start with the next day. Earlier days are unverified, never assumed landed: a page shows such a fact before it builds on it (section 3.2). Nothing already served is rewritten. |
| The contract check lets a bad page through | It is the second line after deterministic checks; `refused_served` and `landed` are tracked nightly and the binge reader looks at the whole week. |
| Cost estimates are wrong | They are built from measured call prices and confirmed by the replay before slice 3. |
