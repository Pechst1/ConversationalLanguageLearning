# WP-115 · Les mots qui reviennent — vocabulary inside the story

*2026-09-30, revised the same day with the owner's answers (§7). The owner asked whether vocabulary review sits in the right place and is the
best version it can be, and how Anki-style review could become disruptive, effective and
fun. This is the answer: a map of what exists, the evidence, and a proposed package. It
is a proposal; nothing is built.*

## 1. Short answer

**It is not in the right place, and it is not the best version.** Review today is a
flat, self-rated Anki clone in the Cahier (`/vocabulary/review`). An owner decision
(`WORK-PACKAGES-2026-09-23-learning.md` §5) puts most of the review load there. It sits
outside the story, which is the one thing the product has that nobody else does. Its
scheduler is also weaker than it looks.

The disruptive move is to **make the story one of the scheduler's delivery vehicles**.
When a word is due, a character needs it, and the learner retrieves it inside the scene,
graded, in the voice of the character they learned it with.

**One memory, several places.** One scheduler decides what is due. The story, the
day's practice and the Cahier's drill are places where a due word can be retrieved, and
all of them credit the same card. The drill stays a first-class accelerator (owner,
2026-09-30): the story alone would be too slow for new words, and mixing words into
grammar practice distracts.

## 2. What exists (mapped 2026-09-30)

- **Scheduler** (`app/services/srs.py:43-150`)
  - It is labelled FSRS but is a heuristic: stability × 1.3 on Good, and so on.
  - **Elapsed time and retrievability are ignored.** A review taken early grows
    stability as much as an on-time one, and the "fragile" and "kept-extra" pools review
    early every day.
  - The coverage code (`progress.py:347`) uses the real FSRS forgetting curve, so the two
    disagree.
- **Two review paths grade differently.**
  - The journey grades objectively on a 0/2/3 scale; "Hard" is never issued.
  - The word drill is self-rated on 4 buttons: a typed answer only shows a verdict.
  - The drill posts to `/anki/review` and skips the journey's once-a-day fold, so a word
    can advance twice in one day.
- **Most "recall" is recognition.** choice, classify, listen_tap, tiles, word_bank,
  unscramble and match_pairs are recognition or assembly. True recall appears only in
  short_answer, transform and the reply. There is no gloss → French typed recall in the
  day.
- **The drill picks the card mode from `proficiency_score`** (a ±10 counter), not from
  memory stability.
- **Story words don't become cards.**
  - The scene lexicon writes an interaction but no progress row. A word becomes a card
    only when a practice day drills it or the learner taps «Garder».
  - No card stores who said the word, its panel or its line audio. The drill's "episodic
  anchor" is the episode's first cast member, not the speaker.
- **The director is nudged, not scheduled.** It is told to "bring one or two back" from
  kept or drilled words (`living_story.py:764`). It is never given the due set, and
  nothing checks that a due word was retrieved.
- **`review_logs` has no format or source column**, so recognition and production can't
  be told apart, and retention can't be measured per format.

## 3. What the evidence says (full sources in the research notes)

**Strong evidence**

| Mechanism | Effect | What it means here |
|---|---|---|
| Retrieval practice | g≈0.5–0.6; 80% vs 36% at one week (Karpicke & Roediger 2008) | Every review must make the learner *produce* something, not re-read it |
| Feedback after errors | ~5× one-week retention (Pashler et al. 2005) | Show the right form every time an answer is wrong |
| Spacing | g≈0.74 (Latimier et al. 2021; Kim & Webb 2022 for L2) | Expanding gaps beat equal gaps only when an item is tested many times |
| Successive relearning | Rawson & Dunlosky | Correct once in each of several spaced sessions beats many correct answers in one |
| Sleep between sessions | Half the relearning needed (Mazza et al. 2016) | Evening and morning spacing works |
| Personalised scheduling | +16.5% retention vs massed study, in a real classroom (Lindsey et al. 2014) | Worth building properly |
| FSRS vs SM-2 | Better recall prediction in ~99.6% of 10k collections; ~20–30% fewer reviews (maintainers' benchmark, not peer-reviewed) | Use real FSRS |

**Moderate evidence**
- **Generation effect** (d≈0.4).
- **Retrieval direction by level** (Terai et al. 2021): A1 starts with receptive recall,
  B1 leans productive.
- **Production effect** from saying words aloud: real, but smaller between learners.
- **Involvement load:** the "evaluation" component (using a word in a context) matters
  most (Yanagisawa & Webb 2021).
- **Chunks over single words** fit A1–B1 conversation (Boers & Lindstromberg).

**Weak, or a warning**
- **Reading alone** needs 8–15 encounters per word. A story alone cannot fix vocabulary.
- **One fixed context** gives no advantage (Webb 2007). What helps is *varied* context
  across encounters.
- **Pictures** breed overconfidence unless paired with retrieval (Carpenter & Olson 2012).
- **Keyword mnemonics:** forgotten faster after a delay, so use them for leeches only.
- **Grouping by theme** hurts initial learning.
- **Method of loci:** little evidence for L2 word meanings.

**Fun**
- Game fiction and stakes help (Sailer & Homner 2020, g≈0.49 cognitive).
- Badges, leaderboards and engagement-contingent rewards *lower* intrinsic motivation
  and scores (Hanus & Fox 2015; Deci et al. 1999).
- Anki predicts grades but students dislike it (Seibert Hanson & Brown 2020).
- **Fun that *is* the retrieval works; fun that pays for showing up does not.**

## 4. The proposal

### 4.1 The foundation: one honest memory
1. **Real FSRS** (the `fsrs` package, FSRS-6 default parameters).
   - Uses elapsed time and retrievability.
   - Target retention 0.87 with a **hard daily cap**, because backlog kills habits.
   - Refit parameters per learner once they have about 400 reviews.
   - One scheduler for vocabulary; errata and grammar keep theirs for now.
2. **One grading scale, earned rather than self-rated.** The grade comes from the format
   and the result: recognised = Hard, recalled = Good, recalled fast and unaided = Easy,
   wrong = Again with the right form shown. Self-rating remains only for imported Anki
   cards.
3. **Every path goes through one fold**: at most one scheduling step per word per day
   (fixes the drill's double credit).
4. **`review_logs` gains `format`, `direction` and `source`** (journey, story, drill,
   letter).
5. **A card remembers where it was learned:** sentence, speaker, panel id and image,
   line-audio key, scene, date. Scene lexicon words become *new* cards the day they are
   met; the pace setting still limits new cards.
6. **The unit can be a chunk** («je voudrais un…», «ça te dit de…») taken from the
   dialogue.

### 4.2 Narrative spacing: the words come back in the story (the flagship)
1. **The director receives the due set.** At most 2 due words per generated day, each
   with a **"need"**: a character must need that word from the learner. For example,
   Gus: «Comment on dit déjà, ce truc pour ouvrir la porte… ?»
   - **Which words (owner, 2026-09-30): the ones that don't stick.** The story's two
     come from the due words the learner finds hardest: most lapses, or FSRS
     difficulty high, with at least 2 lapses. A word that keeps failing in the drill
     needs a *different* encounter, not more of the same (leech research). A scene
     where someone needs it is that encounter: a speaker, a place, a reason. The drill
     keeps the easy bulk; the story takes the stubborn few.
   - Tentpoles are authored and stay as written.
   - Gap days carry the due words, as the WP-111 director brief already carries small
     moments.
2. **Retrieval inside the reply is a graded review**, but only when it demands recall,
   not recognition. The tutor lane records «recalled `la clé`» and the fold schedules it.
   A due word the scene didn't reach falls back to the practice after the ending
   (WP-109) the same day, so no due word ever slips.
3. **The Courrier as composition.** Once a week a character's letter asks for an answer
   that needs 2–3 due words. This is the highest-involvement task ("evaluation"), graded
   for correct use.
4. **Transfer is rewarded inside the story.** When the learner uses a due word unprompted
   in conversation, the character notices («Tiens, tu as retenu "la clé" !»). No points.

### 4.3 The recall ladder: format follows memory, not a counter
The format follows memory stability:

1. First meeting: guess the word from the panel before it is revealed (errorful
   generation with immediate feedback).
2. The original scene: the panel, the character's line in their own recorded voice, with
   the word blanked.
3. **New contexts from the third review on:** other characters, other places (varied
   context).
4. Productive recall: from the gloss to typed French, then **said aloud**, graded
   leniently with folded quotes and accents, with silent typing always available.
5. Free use in the chat or a letter.

A1 learners stay longer on receptive recall; B1 learners move to production sooner.

### 4.4 The Cahier's drill: the accelerator (and the safety net)
- **The learner sets the pace, as in Anki** (owner, 2026-09-30):
  - **new words per day** and **maximum reviews per day** are learner settings;
  - the defaults are moderate, and the ceilings are high for learners who want more;
  - the target retention stays at 0.87.
  - The story takes at most 2 due words a day, the hardest ones (§4.2); the rest are
    the drill's.
- **Drill to go faster** (replaces the evening review). An offer, never a nag, computed
  from the learner's own numbers: «Avec 10 mots de plus par jour, tu atteins A2.2 environ
  30 % plus tôt», from the level's word target, the words held and the current pace. An
  optional reminder, off by default.
- **Objective grading**, using the panel and voice as cues.
- **Successive relearning inside a session:** an item answered wrongly comes back at the
  end of the session until it is right once.
- **Leech rescue.** Its first step is the story (§4.2): a stubborn word is handed to
  the next generated day. After 5 lapses the card also changes method in the drill:
  - «Gus a une astuce»: an image or mnemonic;
  - a minimal-pair audio contrast;
  - a fresh context.
- **What the learner sees.** Words *retrieved* at 21+ days, per character and per place
  («Les mots de Margaux»): a collection that fills only by retrieval. No "words seen"
  counter, no league.

### 4.5 Measurement: retention, not session accuracy
- **Headline:** delayed retrieval on held-out probes at 7 and 30 days, receptive and
  productive separately.
- **Scheduler health:** calibration, meaning retention measured at the due moment against
  the 0.87 target.
- **Efficiency:** words retained at 30 days per minute of review.
- **Transfer:** unprompted correct use of scheduled words in chat.
- **Engagement:** D1, D7 and D30 return; due vs done; backlog.
- **Does the story help? (optional, 4 weeks).** The scheduler stays one. The only switch
  is *where* a due word may be retrieved: for a random half of each learner's *hard*
  words,
  the story is allowed to carry them; for the other half, only the practice and the
  drill are. The learner sees nothing different. Comparing 30-day retention of the two
  halves tells us whether story retrieval is worth its cost in director instructions.
  Without it, "the story helps" stays an assumption. The switch is removed after the
  pilot.
  - Keep a no-probe control subset.
  - Analyse intention-to-treat.

## 5. Where it lives after this
- **The day** (WP-109): warm-ups are the morning relearn and due words; the episode
  carries 1–2 due words as story needs; the practice after the ending mops up the rest.
- **The Courrier:** a weekly composition with due words.
- **The Cahier:** the safety net, the evening review, leech rescue and the collection.
- The "Words" chip on Home stays, but points to the evening review, not a backlog.

## 6. Packages and order

| # | Package | Size | Depends on |
|---|---|---|---|
| 115a | FSRS for real; one earned grade; one fold; review logs with format and source; card metadata (speaker, panel, audio); chunks | L | — |
| 115b | The recall ladder in the day's practice and the Cahier (panel cue, voice, gloss → French, spoken answer); successive relearning; leech rescue | L | 115a |
| 115c | Narrative spacing: due words in the director brief with a "need"; graded retrieval in the reply; fallback to the practice after the ending | M | 115a, WP-109, WP-111 |
| 115d | The weekly composition letter with due words; transfer noticed in the story | M | 115c |
| 115e | Measurement: probes, calibration dashboard, per-word randomisation; opt-in evening review | M | 115a |

Suggested order: **115a → 115e → 115b → 115c → 115d.** Measurement comes second so that
the story's contribution can be proven rather than assumed.

## 7. Decisions (owner, 2026-09-30)
1. **The 09-23 decision is revised.** Due words are carried by the day and the story, and
   the drill stays a first-class way to go faster (the story alone is too slow for new
   words, and grammar practice must not be crowded with words).
2. **Anki-like settings:** the learner sets new words per day and maximum reviews per
   day, with high ceilings. The target retention is 0.87.
3. **Self-rating** (decided by me as the implementer): grades are earned from answers
   everywhere for the app's own words (typed, chosen, spoken). The drill keeps an
   optional **flashcard mode** with Anki's four buttons for fast learners, and imported
   Anki decks keep self-rating. A self-rated answer never counts as production.
4. **Spoken answers** (decided by me): a graded production format, lenient (quotes and
   accents folded), with typing always offered. It is not required.
5. **The evening review becomes «drill to go faster»:** an in-app offer with an honest
   projection from the learner's own pace. An optional reminder, off by default.
6. **The pilot** is the optional per-word switch in §4.5. The scheduler is one either
   way; it only measures whether story delivery earns its place. It can be skipped.

## 8. Status — 115a built (2026-09-30)

| Piece | Where |
|---|---|
| FSRS-4.5 for every vocabulary card (elapsed time, retrievability, target 0.87) | `app/services/vocab_fsrs.py`; used by `ProgressService` (the day's credit) and `EnhancedSRSService` (the drill). Grammar, conjugation and errata keep theirs; imported Anki decks keep SM-2 |
| Earned grades | the day: recalled = Good, recognised = Hard; the drill: a typed/cloze/audio answer sends its result and the server grades it (`earned_rating`); an unanswered card stays a self-rated flashcard. The drill shows one «Next» after an answered card |
| One daily limit | FSRS itself: a second review the same day barely moves a word (R ≈ 1). The journey's once-a-day fold stays |
| What a review was | `review_logs.source / format / direction` (migration `f7b9d1e3a5c7`) |
| Where a word was met | `user_vocabulary_progress.context`: sentence, speaker, panel, line audio key, journey, date — written by «Garder» from the reader |
| Anki-like caps | new words per day up to 100; `users.max_reviews_per_day` (default 200), in Réglages; the drill stops at the cap |

**Not yet (115b onwards):**
- chunks as card units;
- the drill's card format chosen by stability instead of `proficiency_score`;
- scene-lexicon words becoming cards on the day they are met (today only «Garder»
  and practice create cards);
- «Easy» earned from answer speed.

## 9. Status — 115c built (2026-09-30)

- **Which words** (`app/services/story_words.py`): up to 2 *due* words the learner finds
  hardest (≥ 2 lapses, or difficulty ≥ 7 after ≥ 3 reviews), most lapses first; FSRS
  cards only, with a meaning in the learner's language.
- **The director** (generated days; tentpoles stay as written) gets them as
  `story_words`: a cast member must need each word, describing it in French without
  saying it, so the learner's reply gives it. A scene that prints the word is asked
  once more (`story_word_printed`, soft: the retry is served either way).
- **The planner** ranks them first and makes them targets the reply is graded on (the
  tutor's `demonstrated_target_ids` credit a recall); the day's practice takes them too,
  so a word the reply missed is still retrieved that day.
- **Not yet:** the transfer moment (a character noticing a due word used unprompted) is
  115d; measuring whether the story helps is 115e.

