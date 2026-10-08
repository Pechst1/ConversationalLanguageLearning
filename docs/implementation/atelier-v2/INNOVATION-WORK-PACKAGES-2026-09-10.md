# Innovation work packages — 2026-09-10

Follows [NEXT-WORK-PACKAGES-2026-09-07.md](NEXT-WORK-PACKAGES-2026-09-07.md). The
highest-impact packages of 2026-09-10 (WP-24 mistake loop, WP-25 placement, WP-26 latency,
WP-27 voice-first respond, WP-28 integration) are landed or in flight. This document
defines the *innovation* packages: angles no mainstream app ships, each grounded in
published evidence and in a mechanism this codebase already has. Numbering continues
from WP-28.

Every package is written for one Opus agent with an exclusive file lease. The shared
checkout rules of BASELINE.md apply: never `git checkout`/`stash`/`reset`/`add -A`,
commit only leased files by path, never touch `.env`, `.venv` + `TZ=UTC` for pytest.

## 1. What the research says, and what it changes

| Angle | Evidence | Consequence for the design |
|---|---|---|
| Coverage-controlled generation | 95 % known-word coverage is the floor for comprehension with support, 98 % for unassisted reading (Laufer & Ravenhorst-Kalovski 2010; Hu & Nation 2000). Extensive-reading programmes target 95–98 %. | Generation must be *validated* against the learner's own known-word set, not guessed at by CEFR band. Unknown words are a budget, not an accident. |
| Learner-written recap | Free recall beats cued recall beats recognition; retrieval practice shows **no** advantage over restudy unless corrective feedback follows (retrieval-plus-feedback studies 2022–2025; Kim & Webb 2022 on spacing). | The recap is free production from memory **and** is corrected. No correction, no package. |
| Characters and the learner's mistakes | Explicit correction produced uptake in 50 % of cases vs 31 % for recasts (Lyster & Ranta 1997); output-pushing prompts beat input-providing feedback for accuracy (Lyster & Saito 2010; Li 2010; Brown 2016). | Characters do **not** merely recast. They *prompt* self-repair first (clarification request, elicitation), then correct explicitly if the repair fails. |
| Real-situation rehearsal | Transfer from task rehearsal is under-evidenced overall but positive for the lowest-proficiency learners (Benson 2016); rehearsal improves complexity/accuracy/fluency; needs-analysis relevance drives adult engagement (Huang 2022). | Rehearsal targets the learner's declared real need, is repeated once (rehearse → real event → debrief), and is measured by the debrief, not by the rehearsal score. |
| Listening-first episode | Metacognitive listening instruction (predict → listen → verify → debrief) has a consistent moderate effect, largest for weaker listeners (Vandergrift & Tafaghodtari 2010; Vandergrift & Goh 2012). | Audio-first alone is not enough. The radio episode runs the four-stage cycle. |
| Register and pragmatics | Instruction beats exposure; explicit meta-pragmatic instruction has the larger effect (Taguchi 2015; meta-analyses 2022). | Pragmatic adequacy is graded **and explained** ("vous, parce que…"), not only reacted to in character. |
| Inspectable learner model | Open learner models raise self-regulation and agency; the inspectable → editable continuum matters (systematic review 2020; meta-synthesis 2025). | The learner model page is editable with a check ("je connais déjà" → short verification), not read-only. |
| Bring your own French | Needs analysis / authentic materials in TBLT. | Real artefacts become scenes and vocabulary through the existing Courrier and gloss resolver. |

Competitive read (2026): Praktika, Loora, Speak and Duolingo Max converge on voice tutors
with phoneme-level pronunciation; Babbel reorders lessons by error patterns. None
measures lexical coverage against the learner's own state, none carries one continuing
story with commitments, none rehearses the learner's declared real life, none explains
its own model. Those four are the moat; pronunciation scoring stays a WON'T-DO.

Sources: [Laufer & Ravenhorst-Kalovski 2010](https://files.eric.ed.gov/fulltext/EJ887873.pdf) ·
[lexical coverage and processing, Applied Linguistics 2024](https://academic.oup.com/applij/article/45/6/953/7841943) ·
[retrieval practice plus feedback](https://www.tandfonline.com/doi/abs/10.1080/14790718.2022.2102172) ·
[Kim & Webb 2022 spacing meta-analysis](https://www.researchgate.net/publication/358406370_The_Effects_of_Spaced_Practice_on_Second_Language_Learning_A_Meta-Analysis) ·
[Li 2010 corrective feedback meta-analysis](https://www.academia.edu/2911659/Li_S_2010_The_effectiveness_of_corrective_feedback_in_SLA_A_meta_analysis_Language_Learning_60_309_365) ·
[Brown 2016 oral CF meta-analysis](https://journals.sagepub.com/doi/10.1177/1362168814563200) ·
[Benson 2016 task transfer](https://dx.doi.org/10.1177/1362168815569829) ·
[Huang 2022 TBLT adult ESL](https://onlinelibrary.wiley.com/doi/full/10.1002/ace.20468) ·
[metacognitive listening intervention 2022](https://www.frontiersin.org/journals/education/articles/10.3389/feduc.2022.819308/full) ·
[L2 pragmatics instruction meta-analysis](https://pmc.ncbi.nlm.nih.gov/articles/PMC9723127/) ·
[open learner models systematic review](https://www.sciencedirect.com/science/article/abs/pii/S0360131520300774) ·
[AI language apps 2026 comparison](https://kippy.ai/blog/best-ai-language-learning-apps-comparison).

## 2. Lease map and waves

WP-28 (integration, in flight) holds: `app/services/daily_journey.py`,
`app/services/living_story.py`, `app/schemas/daily_journey.py`, `pages/atelier.tsx`,
`components/atelier-v2/home/HomeScreen.tsx`, `journey/useDailyJourney.ts`,
`components/releve/Releve.tsx`, `pages/auth/signup.tsx`. No innovation package edits
those files. Where a package needs a hook there, it writes the exact diff into its
handoff doc under "Hooks owed", and the next integration pass applies it.

| Wave | Packages | Rationale |
|---|---|---|
| 1 (now) | WP-29 coverage engine, WP-30 learner-written recap, WP-31 rehearsal, WP-33 register | Disjoint from WP-28 and from each other. |
| 2 (after WP-28) | WP-32 radio episode, WP-34 bring your own French, WP-35 learner model, WP-36 self-repair prompts | WP-32/36 need the journey step and conversation files; WP-35 reads WP-24/25 payloads that WP-28 finishes wiring. |

## 3. Packages

### WP-29 — Coverage-controlled generation (1.5 d)

**Owner:** engine/lexical agent. **Lease:** NEW `app/services/lexical_coverage.py`, NEW
frequency/lemma data under `app/data/lexical/`, additive read-only use of
`app/services/vocabulary_coverage.py` and `UserVocabularyProgress` (FSRS `stability`,
`state`), NEW `scripts/coverage_report.py`, tests, handoff doc.

1. **Known-word set per learner**: a word counts as known when its FSRS retrievability
   ≥ 0.9 (reuse `NAILED_RETRIEVABILITY`) or it belongs to the CEFR-band core list the
   learner has demonstrably passed (placement/measured level from WP-25). Lemmatise
   with the spaCy pipeline already used for POS where available; fall back to the
   curated lemma table.
2. **Coverage of a text**: tokens → lemmas → share known; returns coverage, the
   unknown lemmas ranked by frequency, and which of them are *targets* (due vocabulary /
   errata) versus *accidental*.
3. **Guard function** in the living-story guard style (`(scene, learner) → verdict +
   hint`): accept at ≥ 95 % with ≤ N accidental unknowns, where N scales with band; the
   hint names the accidental words to replace and the targets to keep. Do not register
   the guard (living_story.py is leased to WP-28); write the exact registration line in
   the handoff.
4. **Scene metadata**: coverage, unknown count, target list — additive on the scene
   draft object, readable by telemetry and by WP-35.
5. `scripts/coverage_report.py`: coverage distribution over the last N generated scenes
   for a learner, from stored scenes; digest line if additive.

**Acceptance:** unit tests on coverage math, lemma folding (accents, elision `l'`, `qu'`),
target/accidental split, guard thresholds per band; a fixture A1 learner + a scene with
3 accidental B1 words is rejected with a hint naming them; a scene with only due targets
unknown passes.

### WP-30 — The learner writes the recap ("Le journal de bord") (1.5 d)

**Owner:** learning-loop agent. **Lease:** NEW `app/services/journal.py`, model +
migration (`journal_entries`), NEW router, NEW `components/cahiers/Journal*.tsx`,
`components/cahiers/CahierV2.tsx` (new tab only), `pages/notebook.tsx` (tab routing
only), tests, handoff doc. Corrections through the existing Atelier correction service by
import; errata through WP-24's `error_memory` API by import.

1. The day after a journey (or later), the learner is asked to write 2–4 sentences from
   memory about what happened in yesterday's scene, in French, without the scene text
   visible. Free production, then reveal.
2. Correction: one relevant correction foreground (journey policy), full list on demand;
   each grammar error becomes a WP-24 erratum; vocabulary used from the due set earns
   credit through the existing vocabulary credit service.
3. A character reacts in one line to the *content* (did the learner remember the
   commitment?) — generated with the story context available through the public
   journey/serial read APIs, never by writing story state. Content recall is scored
   against the scene's stored facts (commitments, outcome) as a separate signal from
   grammar.
4. Spacing: the entry is offered at +1 day and the same scene is asked about again at
   +7 days in one line ("Et la semaine dernière, avec Romy ?"), producing the
   `used_again_later` signal the digest watches.
5. Cost telemetry: one priced PilotEvent per correction call (pattern:
   `atelier_correction_cost.py`).

**Acceptance:** tests for the offer schedule (+1/+7), the no-scene-text-visible rule
(source scan), correction → erratum, vocabulary credit, content-recall scoring against
facts, honest provider-failure state; CahierV2 tab renders in av2, French, dark-capable.

### WP-31 — Rehearse a real upcoming situation ("Répétition") (2 d)

**Owner:** situations agent. **Lease:** NEW `app/services/rehearsal.py`, model +
migration (`rehearsals`), NEW router, additive use of `journey_content.py` and
`journey_conversation.py` by import (no edits), NEW `components/atelier-v2/rehearsal/**`,
NEW `pages/repetition.tsx`, `pages/settings.tsx` (one entry link), tests, handoff.

1. The learner declares a real situation in their own words (L1 or French): "appeler le
   propriétaire pour le chauffage, mardi". Structured into: goal, counterpart, register
   (tu/vous), date, key facts. Explicitly *not* story canon: stored separately, never
   written into serial memory (CONTINUOUS-STORY: fiction vs biography).
2. A rehearsal scene is generated with the journey content adapter: objective, private
   rubric, useful phrases on request, attainable endings; 3–6 turns via the journey
   conversation machinery; graded with the evidence rubric so capabilities accrue.
3. **Debrief** on/after the date: "Comment ça s'est passé ?" with three outcomes
   (done / partly / not yet) and one free line; the free line is corrected; the outcome
   is the package's success metric and a digest line.
4. Push reuse: the existing journey push scheduler can send "Votre répétition est prête"
   the day before — write the exact hook, do not edit the scheduler.
5. Cost: priced events per generation/grading call; hard cap of rehearsals per week in
   config.

**Acceptance:** tests for structuring, the no-canon rule (source scan on serial memory
writes), scene generation contract, turn bound, debrief states, cost events; av2 page
French/dark; provider failure yields an honest "non préparée" state.

### WP-33 — Register and pragmatics as a graded dimension (1 d)

**Owner:** evaluation agent. **Lease:** `app/services/journey_capabilities.py`,
`app/services/journey_conversation.py` (evaluation additive only; WP-36 will take the
feedback-policy half later — coordinate by keeping to the evaluation functions),
NEW `app/services/pragmatics.py`, `app/services/learner_copy.py` (new keys),
`journey/journey-copy.ts` (new keys), tests, handoff. Register decision on Lila: apply
the owner's standing guidance (strip below B1) through the existing level guidance in
data, not by editing living_story.py.

1. Deterministic detectors: tu/vous consistency against the counterpart's declared
   register, politeness markers (bonjour/merci/s'il vous plaît, conditional softeners),
   greeting/closing presence, imperative vs request at A1/A2. LLM assessment only for
   what detectors cannot see, with the same honest "non évalué" fallback.
2. New capability dimension `register` alongside the existing rubric states
   (`not_tried → with_support → independent_once → used_again_later`); it flows into
   `build_capability_summary` and therefore the digest without a second rubric.
3. Explicit meta-pragmatic feedback line in French/L1 when register slips ("Ici on dit
   *vous* : c'est votre propriétaire"), foregrounded only when it is the one relevant
   correction per the journey policy.
4. Scene contract: the scene plan declares the counterpart's expected register; tests
   pin that every authored scenario carries it.

**Acceptance:** detector unit tests (tu→vous slip, missing greeting, imperative to a
stranger), rubric integration test, digest shows `register` counts, copy in en/de/fr,
no pronunciation or accent judgement anywhere (source scan).

### WP-32 — Radio feuilleton: listening-first episode (1.5 d) — wave 2

**Owner:** listening agent. **Lease:** `journey/StoryEpisodeStep.tsx`,
`StoryEpisodeReader.tsx`, `story-episode-model.ts` (+tests), NEW
`journey/useEpisodeAudio.ts`, TTS synthesis entry (the OpenAI TTS path in
`llm_service.py`, additive function only), NEW cache table or storage for synthesized
episode audio + migration, priced events, handoff.

1. Optional "Écouter d'abord" mode remembered per learner: the four-stage cycle —
   *prédire* (2 tappable guesses about what happens, from the scene's premise),
   *écouter* (character voices, no text), *vérifier* (guesses confirmed, text revealed
   line by line on tap), *retenir* (one line: what to listen for tomorrow).
2. Synthesis cached per scene revision; cost on the ledger; no synthesis when the flag
   is off; text mode always available.
3. Comprehension is measured by the prediction check and by the next scene's respond
   evidence, not by a quiz.

**Acceptance:** state-machine tests; cache/idempotency; flag gating; French copy; the
text path is unaffected when the mode is off.

### WP-34 — Bring your own French (1.5 d) — wave 2

**Owner:** Courrier agent. **Lease:** `app/services/missions.py` (additive intake
functions), NEW `app/services/intake.py` (text/photo → structured artefact via the
vision-capable model, with a cost ceiling), `components/courrier/Courrier.tsx` (new
intake entry), tests, handoff.

1. The learner pastes text or photographs a menu/letter/email. The artefact is
   summarised, glossed with the existing gloss resolver at the learner's level, and
   turned into one Courrier task (reply, decide, ask) graded like any Courrier mission.
2. Unknown words from the artefact go to the vocabulary queue as *learner-sourced*
   items (provenance stored), which WP-29 counts as targets.
3. Privacy: artefacts are private, deletable, never used for story canon, never sent
   anywhere but the model call; a source-scan test pins the deletion path.

**Acceptance:** intake tests with fixtures (menu, landlord letter), gloss level bound,
Courrier task contract, deletion, cost events.

### WP-35 — The inspectable learner model ("Votre dossier") (1.5 d) — wave 2

**Owner:** learner-model agent. **Lease:** NEW `app/services/learner_model.py`, NEW
router, NEW `pages/dossier.tsx` + `components/atelier-v2/dossier/**`, `pages/settings.tsx`
(one link), tests, handoff. Reads WP-24 errata states, WP-25 placement/estimate source,
capabilities summary, FSRS vocabulary stock, WP-29 coverage if present.

1. One page answering: what the app believes (level + source + confidence; capabilities
   by rubric state; open/repairing/mastered errata; vocabulary stock), and *why today's
   scene* (the because payload).
2. Editable with a check: "Je connais déjà" on a concept or word triggers a 2-item
   verification; pass → schedule advances (through the existing SRS APIs), fail →
   honest "pas encore", no penalty. Never silently trusts the claim.
3. Every number links to the evidence that produced it (journey id, date).

**Acceptance:** contract tests, the verify-before-trust rule pinned, av2 French dark;
no English in learner-facing copy.

### WP-36 — Characters prompt self-repair (1 d) — wave 2

**Owner:** feedback-policy agent. **Lease:** `app/services/journey_conversation.py`
(feedback policy functions), `learner_copy.py` + `journey-copy.ts` keys, tests, handoff.
Prompt-side changes to `living_story.py` written as "Hooks owed".

1. When the learner's turn contains one of their *open* errata (WP-24) and the scene
   allows a follow-up turn, the character first asks for clarification or elicits the
   form ("Pardon, *un* ou *une* homme ?") — output-pushing. If the repair succeeds, the
   erratum records a correct repair; if not, the explicit correction follows in the
   foreground line.
2. Bounded: at most one prompt per scene; never for errata the learner has never seen
   explained; never on the last turn.
3. Recurring mastered errata that resurface are handled by the same path and re-open
   per WP-24.

**Acceptance:** policy tests (prompt → repair → credit; prompt → fail → explicit; bounds),
copy in three languages, no change in scoring for learners without open errata.

## 4. What is deliberately not here

Pronunciation scoring (owner WON'T-DO), social/shared worlds (pre-retention non-goal),
mascots, and any second story engine. Everything above reuses the living story, the
evidence rubric, WP-24's error memory, WP-25's estimate, and the pilot ledger.
