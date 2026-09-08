# Feuilleton audit — 23 July 2026

## Executive assessment

The current Feuilleton problems are structural, not a collection of isolated copy or styling defects. The reader combines an unrelated live-news seed, a generic no-LLM story template, exercises selected independently of the visible scene, and three overlapping presentation systems. The result can look polished at first glance while the story, learning interaction, feedback, and visual hierarchy contradict one another.

The screenshots reported on 23 July are reproducible from the persisted preview data. They show the intended behavior of the current contracts:

- live news is requested by default;
- a six-panel study scene is expected to carry five panel tasks plus a final task;
- missing task concepts inherit the first selected grammar concept;
- generated dialogue is shown both over and below the image;
- the full news source is shown after the fictional story;
- image prompts forbid speech balloons while repeatedly asking the image model to make room for them.

The feature needs a smaller, explicit product contract: one coherent fictional micro-story, four uninterrupted story panels, one meaningful decision, at most one optional language reflection, and a single visual system.

## Evidence inspected

The audit covered:

- the five screenshots supplied on 23 July 2026;
- the active local preview database at `/private/tmp/atelier-pilot-preview.db`;
- the persisted scene `475a3645d38e4a55af500c6cf20776cc`, titled “Romy garde une porte ouverte”;
- story generation, serialization, task correction, image prompting, and serial scheduling in the backend;
- the desktop and mobile readers in `web-frontend/pages/graphic-novel.tsx`;
- the legacy shared Feuilleton presentation in `web-frontend/components/feuilleton/Feuilleton.tsx`;
- existing Feuilleton, serial, and frontend regression tests.

The persisted scene records `provider_error: story_llm_unavailable` and `serial_plan_source: continuity_recovery`. It has neither a serial thread nor an episode index, yet it was generated from the default serial world. Its stored source is the Monique Barbut minister article shown in the screenshots. Its targets concern A1 articles/gender, while a panel asks for the pluperfect form `avait`. The saved feedback for that task discusses pronouns.

## Root-cause chain

### 1. Public news is switched on even when the story does not need it

The minister article is not a random leak:

1. `web-frontend/pages/graphic-novel.tsx` sends `use_news: true` for ordinary scene creation.
2. `app/services/serial.py` also creates serial scenes with news enabled regardless of whether the episode brief requests a news panel.
3. `GraphicNovelScheduler._source_snapshot()` calls the daily Feuilleton news service when that flag is set.
4. The news ranker favors political terms including ministers, government, and presidential subjects; named public figures and larger story clusters receive further weight.
5. `serialize_scene()` exposes the complete source snapshot to the learner.
6. `SceneBrief` prioritizes and renders the news summary, source card, publisher credit, and link after the fictional panels.

The active story metadata even says the seed “stays offstage,” but the source card is still learner-visible. Generation provenance and learner-facing content are not separated.

Additional source-quality defects amplify the problem:

- RSS photo-credit strings can be treated as the publisher;
- summaries are truncated mechanically and can end mid-word;
- the same headline and summary are repeated in multiple blocks.

### 2. The no-LLM path invents a fake serial context

With `ATELIER_LLM_ENABLED=false`, `_local_recovery_story()` does not produce a deliberately authored standalone fallback. It loads the default Paris serial world, even for a scene without a serial thread, and supplies a vague premise about Romy finding a “small contradiction.”

`_serial_recovery_episode_plan()` then expands this through generic templates:

- “the question from yesterday”;
- “the detail everyone chose to avoid”;
- a truth-versus-delay decision;
- an unspecified clue;
- an unexplained door, gesture, or silence;
- a generic final question.

These phrases do not identify a concrete object, goal, obstacle, revelation, or consequence. The panels therefore share a mood but do not form a causal story. The exercise templates are generated independently and cannot reliably refer to the visible event.

### 3. Dialogue is selected mechanically rather than written for the event

The recovery writer chooses signature lines by array position. With four- or six-panel selection, the same character lines can repeat in a single episode. It also interpolates canonical names such as `Romane « Romy » Tremblay` into captions, prompts, and labels instead of using a short display name such as `Romy`.

Bubble positions are parity-based coordinates rather than coordinates derived from speaker staging. The system does not verify that the named speaker is visible, that the name belongs to the scene cast, or that the line describes the panel action.

Whitespace-only dialogue is another contract risk: filtering by truthiness is insufficient; normalization and rendering must both use trimmed strings.

### 4. Exercise selection is independent of story meaning

For a new learner with no preferences or errata, `_select_concepts()` chooses the first active grammar rows in database order. This is neither personalized nor guaranteed to match the generated story.

`_normalize_overlay()` then assigns the first selected concept ID to every task that lacks an explicit concept. This includes:

- cloze tasks that test a different tense;
- narrative choices that test no grammar at all;
- open production tasks whose visible prompt has no relationship to that concept.

In the inspected scene:

- the selected targets concern articles and gender;
- the cloze answer is `avait`, requiring a past-perfect construction;
- the choice answer is the opaque internal value `franche`;
- both tasks inherit the same unrelated concept;
- feedback consequently explains pronoun placement.

This is the direct cause of the correction shown in the screenshots.

### 5. Narrative decisions are incorrectly graded as grammar answers

The current story choice offers two narratively valid branches but marks one value as the expected answer. The “wrong” branch receives correction language and can create an erratum, even though it is a legitimate authorship decision.

Applying a branch only rewrites a later panel’s hidden `beat`. It does not update the visible caption, dialogue, task, or already-generated art. The learner is told that the choice changes the story, but the visible story cannot react coherently.

Story decisions need a separate `grading_mode: branch` contract:

- every offered branch is valid;
- submitting a branch never creates a grammar erratum;
- feedback describes the immediate story consequence;
- the next visible beat must reflect that consequence.

### 6. Feedback exposes internal taxonomy and duplicates itself

Closed-task feedback is produced from the attached grammar concept. Because the wrong concept is attached, the profiler finds generic pronoun language in the concept description and generates a pronoun lecture for unrelated answers.

The reader then shows too many layers:

- accepted/needs-revision status;
- corrected answer;
- “Pourquoi” explanation;
- repair advice;
- erratum badge;
- vocabulary-credit badge;
- action button.

On mobile, the correction is rendered once by the sheet and again inside `TaskControls`. English fallback text and internal grammar terminology can leak into an otherwise French interaction.

The visible feedback contract should be one short, story-specific French message. A correction may show either the corrected phrase or one actionable hint. Additional explanation should be optional and collapsed.

### 7. Task density is hard-coded

`GRAPHIC_NOVEL_TASK_COUNTS` requires:

- three panel tasks for four panels;
- five panel tasks for six panels;
- seven panel tasks for eight panels.

The final prompt is an additional required task. A six-panel episode therefore contains six mandatory interactions. The serial generation prompt also demands multiple tasks. The overcrowding is expected behavior rather than an accidental layout issue.

This prevents reading rhythm, turns every beat into a form, and makes the story feel like a worksheet.

### 8. Empty speech balloons are baked into the generated images

The visible empty balloon outlines are pixels in the generated PNGs, not empty HTML overlays. The persisted overlay bubbles contain French text, and the frontend already filters visibly empty values.

The image prompt is self-contradictory:

- it says not to draw speech bubbles;
- it then asks for an upper area reserved for HTML speech bubbles;
- the page prompt again asks for areas where HTML speech bubbles will be overlaid.

This repeated semantic cue plausibly primes the image model to draw balloon shapes despite the negative instruction. There is no visual QA/OCR retry step to quarantine noncompliant art.

Existing affected art also remains cached after prompt changes. A prompt-version migration or stale-scene invalidation is needed.

### 9. The reader repeats almost every piece of content

Each panel can display:

- generated art;
- an overlaid dialogue bubble;
- a direction/title label;
- a credit/title label;
- a numbered caption;
- a transcript repeating the same dialogue;
- a task launcher;
- the full task sheet.

After the panels, `SceneBrief` repeats:

- title and edition metadata;
- news-first synopsis;
- story summary;
- target vocabulary;
- the complete source article card.

The final interaction is another outer card containing an inner launcher card. This produces the nested boxes seen in the screenshots.

Choice translations are shown unconditionally even when the learner has not requested English help.

### 10. Three visual systems are stacked

The page combines:

1. a shared component described as a 1:1 port of the old Feuilleton design package;
2. a large page-specific stylesheet;
3. a third set of mobile bottom-sheet overrides.

Competing spacing, border, typography, color, and responsive rules cause the old/new hybrid. The problem is not the global application tokens; it is the duplicated reader systems.

Generated square art is also placed into alternating tall and wide frames with `object-fit: cover`. This arbitrary crop changes composition and can emphasize the empty upper balloon areas.

### 11. Validation checks shape, not coherence

The backend validates counts, lengths, duplicate beats, answer leakage, and coordinate bounds. It does not require:

- a concrete goal, obstacle, reveal, and consequence;
- agreement between panel action, caption, dialogue, and exercise;
- a task anchor that exists in the visible panel;
- a known speaker belonging to the scene cast;
- unique dialogue lines;
- a grammar target matching the expected answer;
- visible branch consequences.

Reported validation failures often become `accepted_with_notes` and are still published. Recovery output can also ship with notes. Semantic failures therefore do not act as a publication gate.

The API schemas make this easier to miss because nested story, overlay, and source payloads are largely untyped dictionaries.

### 12. Old scenes survive a new implementation

Even after correcting the generator, `today()` or a resume URL can return a pre-redesign scene containing:

- live news;
- old prompt-version images;
- five inline tasks;
- unrelated concept assignments;
- saved incorrect feedback.

The rollout needs an explicit content/prompt version. Old incomplete scenes must be regenerated or treated as unavailable rather than resumed.

## First-principles product contract

### Story

- A default episode is fictional and self-contained.
- It contains one concrete object or event, one character goal, one obstacle, one reveal, and one consequence.
- Four panels follow a readable causal sequence: setup → discovery → decision → consequence.
- Every line of dialogue is unique and written for the visible event.
- Character labels use stable short display names.
- News is absent unless an explicitly authored episode brief opts into a news-led story.

### Learning

- The story is readable without interruption.
- There is one meaningful story decision per episode.
- There may be one optional language-production reflection after the story.
- A narrative branch is authorship, not right/wrong grading.
- A grammar task may carry a `concept_id` only when the task was explicitly authored for that concept.
- Each learning interaction references a visible panel/beat and a concrete story fact.
- Only the next learning action is enabled at any time.
- Feedback is one concise French response grounded in the task and scene.
- English appears only after an explicit learner request.

### Presentation

- One reader stylesheet and the global application design tokens.
- One compact top bar and one short story introduction.
- One panel presentation: art, at most one dialogue line, and a caption only when it adds new information.
- Dialogue is placed below the art for the clean MVP; no visual transcript duplicates it.
- No real-image direction labels, repeated title credits, source card, news block, task status card, or nested final card.
- Art uses one consistent, composition-aware aspect ratio.
- The image prompt contains no balloon, bubble, annotation-zone, blank-shape, or overlay-area language.

### Reliability

- Semantic coherence failures block publication.
- A human-authored deterministic fallback is used when story generation is unavailable.
- Learner-facing serialization excludes internal/offstage source provenance.
- Prompt/content versions prevent stale incompatible scenes from being resumed.
- Noncompliant generated art is retried or quarantined.

## Prioritized remediation

### P0 — stop generating the current failures

1. Default `use_news` to false in standalone and serial creation.
2. Fetch news only when an episode brief explicitly requests a news-led episode.
3. Remove learner-visible source/news cards from the core reader.
4. Stop assigning a fallback concept ID in `_normalize_overlay()`.
5. Treat narrative choices as valid branches, with no errata or grammar correction.
6. Reduce default panel tasks to one decision; permit at most one optional reflection.
7. Replace the generic recovery template with a concrete, human-authored four-panel fallback.
8. Remove all bubble/overlay-area language from image prompts and increment the prompt/content version.
9. Prevent pre-redesign scenes from being resumed as the current edition.

### P1 — rebuild the reader

1. Consolidate onto one reader stylesheet.
2. Replace the newspaper masthead stack with a compact Feuilleton header.
3. Render art, one dialogue line, and only additive captions.
4. Remove duplicate transcripts, directions, credits, `SceneBrief`, source news, and vocabulary summaries.
5. Replace each per-panel task box with one quiet inline action.
6. Replace the mobile task sheet with prompt → input/options → one action → one response.
7. Hide all translations until requested.
8. Use one consistent image ratio and focal treatment.

### P2 — enforce meaning and personalization

1. Introduce a typed episode bundle with IDs for goals, facts, beats, speakers, and task anchors.
2. Validate cause/effect, speaker membership, task grounding, dialogue uniqueness, and target/answer agreement.
3. Make critical semantic errors publication-blocking.
4. Select learning targets from actual learner memory and current story affordances, not database order.
5. Ensure branch consequences update visible content.
6. Add visual QA for accidental text and empty balloon outlines.

## Regression checklist

The redesign is not complete until automated tests cover the following:

1. A normal standalone episode does not call the news service and exposes no public-news source payload.
2. A serial episode with `include_news_panel=false` neither fetches nor serializes news.
3. Offstage generation provenance never appears as a learner-facing source card.
4. A task without an explicit concept does not inherit an unrelated concept.
5. The `avait` fixture cannot produce pronoun feedback.
6. Every valid narrative branch is accepted, changes a visible consequence, and creates no erratum.
7. Every task has a valid visible story anchor.
8. Unknown speakers, repeated dialogue, blank dialogue, and unrelated task/panel anchors block publication.
9. Four- and six-panel defaults expose one panel decision; an eight-panel episode exposes no more than two panel interactions.
10. At least two panels can be read without an interaction.
11. Only one learning action is active at a time.
12. Feedback contains one compact, story-specific French message and no English/internal taxonomy leak.
13. Captions, dialogue, prompts, and relationship labels use canonical short character names.
14. Production image prompts contain no bubble, balloon, blank-shape, or reserved-overlay wording.
15. Whitespace-only dialogue cannot survive backend normalization or frontend rendering.
16. The reader does not render duplicate transcript, source card, correction card, or nested final-task containers.
17. English option translations remain hidden until requested.
18. `today()` and direct resume links cannot revive incompatible pre-redesign scenes.

## Definition of done

The Feuilleton is ready for the first test period when a new learner can open a fresh edition with the LLM both enabled and disabled and:

- understand what physically happens in every panel;
- explain the relationship between the four beats;
- make one choice whose visible consequence makes sense;
- encounter no unrelated current-affairs content;
- receive no feedback about a grammar topic the task does not test;
- read the story without repeatedly opening or dismissing boxes;
- see no empty speech balloons, duplicate dialogue, duplicate corrections, or mixed legacy styling;
- resume only scenes generated under the new content contract.

This audit should remain the acceptance reference for the Feuilleton rebuild and its pilot QA.
