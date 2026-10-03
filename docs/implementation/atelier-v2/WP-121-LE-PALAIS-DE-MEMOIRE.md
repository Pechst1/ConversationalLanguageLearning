# WP-121 · Le Palais de mémoire: the map remembers for you

*Defined 2026-10-03. Owner's brief: «anything really missing? be innovative». The owner delegated the
open decisions to the lead. Builds on WP-119 (Le Papier: words kept at close), WP-120 (La Carte: a
pin per Papier with its plate), the SRS (`UserVocabularyProgress.due_at`, `enhanced_srs.py`,
`kept_words.py`) and the journey's errata (`journey_errata.py`).*

## 1. Goal

Two things that use the memory the app now has of **where** the learner learned something.

**A. Spaced repetition placed on La Carte (the memory palace).** Words kept in a Papier are tied to a
place and a plate. When they fall due, they appear as small marks on the pins. Tapping a pin reviews
the words learned *there*, with the plate as the cue and Romy's or the guest's line as the context.
The method of loci, which nobody ships because nobody has a map of where you learned each word.

**B. La Relecture: answer your own question again.** Weeks after a Papier, the archive re-asks the
reader question the learner wrote with Romy, and shows both answers side by side. The same thought,
said twice, by the same person: the only honest progress display. No score.

**Non-goals.** No counters, no streak decorations on the map, no «collect them all». No new fonts or
colours. The review mechanics are the existing SRS; this package adds a *place* to a card and a
*surface* to review it from, not a second scheduler.

## 2. What exists today

- **Kept words are not in the SRS yet.** `encounter.close` builds `RvKept` for the screen and the
  Relevé but never calls `kept_words.keep_word` → `UserVocabularyProgress`. The first job of this
  package is to close that gap (A.0), or the palace has nothing to review.
- `kept_words.keep_word(db, user, …, met=…)` stores a word with a `met` context (sentence, journey);
  `kept_words_for`/`recent_kept_words` read them. `enhanced_srs.py` schedules; `pages/repetition.tsx`
  and `pages/vocabulary/review.tsx` are the review surfaces; the recall formats of WP-66/78 are posed
  from `journey_contracts` (`MATCH_PAIRS`, `LISTEN_TAP`, `WORD_BANK`, `DICTATION`…).
- La Carte: `GET /revue/carte` (closed sessions → pins with kept words, plate, vignette), `Carte`,
  `CartePinCard`, `carte-projection.ts`. `revue_sessions.state` holds the question made and the
  dispatch; `RvClosing.question_kept_fr`.
- Errata: `journey_errata.build_errata_target` ranks the learner's recurring errors for the day.

## 3. A · The memory palace

### A.0 Kept words enter the SRS at close (`encounter.close`, `kept_words.py`)
Every `RvKept.words[]` item → `keep_word` with `met = {sentence: the claim's fr, source: "revue",
session_id, dossier_id, place_id, week}`. Words the learner used correctly (`used=True`, rubric
`correct`) start one SRS step ahead. Idempotent per session (closing twice keeps once).

### A.1 Place on the card
`UserVocabularyProgress` gains nothing; the place lives in the kept word's `met` context (JSON), so
no migration. `kept_words.words_due_by_place(db, user) -> dict[place_id, list[DueWord]]` groups due
words by the Papier place they were met in; words met in several places belong to the most recent.

### A.2 Marks on the pins (`GET /revue/carte`, `Carte`, `CartePinCard`)
- The carte payload gains per pin `due_words: int` and at the top `due_total`. A pin with due words
  shows a small ink dot on the vignette's ring (reduced-motion: static). Clusters sum.
- The pin card gets a first row when `due_words > 0`: «3 mots t'attendent ici» and a primary
  «Réviser ici». Below it the existing content.

### A.3 Reviewing «ici» (`/carte?review=<place_id>`, `components/carte/CarteReview.tsx`)
A review session over the pin's due words only, posed with the existing recall formats from the
word's `met.sentence` (the claim) and the plate as the full-bleed stage behind, Romy or the guest
drawn small with the line that carried the word (the thread item is in the session state). Grading
and scheduling through the existing SRS calls (`enhanced_srs`), evidence through the evidence policy.
When the place's words are done, the dot goes, and «Retour à la carte». Cost: no model calls.

### A.4 Entry from the Relevé and the daily loop
- The Relevé's «Le Papier» section shows «N mots t'attendent sur la carte» → `/carte`.
- The daily planner's recall steps may already pick these words (they are ordinary SRS cards). When a
  recall step poses a word that has a Papier place, its context line shows the place: «vu au marché
  d'Aligre, semaine 41». A small addition to the recall prompt payload (`met.place_label_fr`).

## 4. B · La Relecture

### B.1 When
A Papier whose close kept a reader question (`question_kept_fr`) or a learner-written headline is
eligible **six weeks** after its close (decision: six, not ten; ten loses too many learners), and the
planner may deal a `relecture` recall step on an ordinary day at most once a week, or the learner
opens it from the pin card («Relire ta question»). Never twice for the same Papier.

### B.2 What
The screen shows the plate as a band, the dossier's title and the original question in Romy's
proposal form, then asks the learner to answer **the question itself** in French, one or two sentences
(speak or type), without showing their old answer first. After sending, the two answers appear side by
side: «Semaine 41» and «Aujourd'hui», the words that changed register or grammar underlined by the
rubric (phase-2 `grading.py` with the same claims as context). No score, no verdict word; one line
from Romy in character: what she notices, one thing, kindly (authored templates by band + rubric
flags; a model call only when the critic is on).

### B.3 Where it is kept
`revue_relectures(id, user_id, session_id, asked_at, answer_fr, mode, evidence)`; one per session.
The pin card shows «Relue le 14 nov.» afterwards and can show the pair again.

## 5. Decisions (lead, 2026-10-03)
1. The place lives in `met`, not a new column. 2. Six weeks for La Relecture. 3. Review «ici» uses
the existing recall formats, never a chat. 4. Dots, not numbers, on the pins; the number is in the
card. 5. The Relecture asks the question, not «rewrite your answer».

## 6. Phases and acceptance
| Phase | What lands | Done when |
|---|---|---|
| A.0 | kept words → SRS at close, idempotent, one step ahead when used correctly | closing the acceptance session creates 5 `UserVocabularyProgress` rows with `met.source="revue"` and `place_id`; closing again adds none |
| A.1–A.3 | `words_due_by_place`, carte payload `due_words`, dots on pins, «Réviser ici», `CarteReview` on the plate with existing formats | a fixture with two due words at Aligre shows the dot and reviews them with the plate behind; after both are graded the dot is gone; mock `/carte?mock=1&due=1` |
| A.4 | Relevé line, place line in daily recall prompts | a recall step posing a Papier word shows «vu au …» |
| B | eligibility, the `relecture` step, side-by-side, Romy's one line, `revue_relectures` | a session closed 6+ weeks ago (clock shim) is dealt once; the pair renders; never dealt twice |
| Walk | E-3 `carte-reviews-where-i-learned` | owner's hands-on |

## 7. Status
| Phase | Commit | What landed |
|---|---|---|
| — | — | defined 2026-10-03 |
| A.0–A.3, B | 914692f | kept words enter the SRS at close (`keep_revue_word`, one step ahead when used correctly), `words_due_by_place`, due dots on pins, «Réviser ici» with the journey's recall formats on the plate, La Relecture (six weeks, `revue_relectures` a7c9e1b3d5f8, side-by-side pair, Romy's authored line). Open: planner `relecture` step, «vu au …» line, Relevé due line, voice answer |
| A.4, B step | fec55dc | the «vu au …» line on recall cards, the Relevé due line, the `relecture` desk step dealt by the planner |
