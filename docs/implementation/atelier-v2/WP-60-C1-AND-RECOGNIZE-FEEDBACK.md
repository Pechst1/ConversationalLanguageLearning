# WP-60 — C1 prose fits the engine; the recognize round speaks the learner's language

Two follow-ups to WP-59, found by running it (2026-09-19, late night).

## 1. C1 lost a day to a character cap

The first C1 live review (`var/reviews/atelier-story-review-C1-2026-09-19.json`)
accepted day 1 — a bench at the Buttes-Chaumont, Romy asking whether a year in
Paris makes the learner smile or run, a 68-word reply — then died on day 2
with `invalid_story_output`: both complication drafts (118 and 129 words,
inside the C1 word limit) overran the schema's 350-character `premise_fr`, and
one also overran the 200-character `objective_native`. The retry saw only the
bare token.

- Field caps are sized for C1 (`premise_fr` 600, `setup_native` 600,
  `objective_native` 320, `objective_semantics` 700, dialogue 320, narration
  360, hint/translation/suggestion 400). Reading time stays bounded by the
  per-band word limits in `_validate_scene`.
- A schema overflow now names its fields in the retry hint
  («objective_native: String should have at most 320 characters … shorten
  the premise and the objective rather than dropping content»).
- The review script's request counter is locked (two drafts run on two
  threads) and a provider call that raised is still recorded in the report.

## 2. The recognize round's immediate feedback (WP-56, second half)

The practice Séance answers a recognize submit from the answer key at once
and upgrades the explanation in the background (`_correct_recognize_ai_first`,
force-run by the relecture); the immediate line was English for every
learner. The deterministic line now follows `native_language` through
`learner_copy` keys (`atelier.recognize.*`, en/de/fr): «Du hast „petit“
gewählt; hier ist „petite“ nötig. Regel: Genus und Numerus: Grundlagen.»
For an English learner the item's authored explanation is appended as before;
for other languages the rule's localized title (`grammar_concept_localizations`)
stands in, because the catalogue's `short_description` is English in every
locale. Labels («Réponse manquante», «Classement», «Banque de mots») and the
word-bank rebuild hint follow too. The profile-specific si/imparfait templates
remain English until the relecture — WP-56's remaining half.

## Tests

`tests/test_living_story.py`: a 118-word C1 premise validates; an overflowing
draft's hint names the field. `tests/test_atelier.py`: German, English and
French immediate feedback for fill and classify, with the localized rule title
and never the English catalogue prose for a German learner.

## Evidence (`atelier-story-review-C1-2026-09-19b.json`, seed `learner-c1-one`)

Four of four days, 17 requests, ≈US$0.07. C1 objectives are moves with
nuance («refuse the invitation, explain briefly why you stay, and suggest a
concrete plan to stay close»; «say that you want Romy to stay but won't
demand she give up Montréal; propose a compromise that preserves her
freedom»), scenes of 105–119 words inside the C1 limit, replies of C1 register
(«je préfère que tu choisisses ta vie plutôt qu'une fuite»). Day 2 ended in
the authored fallback: the actor's second attempt quoted the *scene's* lines
as learner evidence (`fabricated_evidence_quote`) after the first was refused;
the learner still got a settled day. Day 3's «Mon grand, tu me sauves» was
scrubbed to «Tu me sauves» as designed. Chapter «Fuir ou rester» ran setup →
complication → turn (Marin's ring, at the same table) → resolution (a month,
decided together).
