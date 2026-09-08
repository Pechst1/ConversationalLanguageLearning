# WP-14 — New situations within one continuing story

Owner requirement, 2026-09-06: conversations must recognize new opportunities, generate fresh situations, and form one coherent continuing story. This is a required extension of the initial functional scope, not optional visual polish. Proposed implementation; nothing in this document claims completion.

## Current implementation and the gap

- `daily_journey._rotated_scenario_key` chooses among the authored catalog by recency. The catalog contains café ordering, arranging a meeting, and explaining a delay, with authored A1/A2 variants.
- `journey_content._apply_variation` changes prose and ending lines. `scenario_variation_v1.json` expressly fixes objectives, cast, location, and outcome keys. This is wording variation, not situation creation.
- `ScenarioBrief.scenario_key` is a `CapabilityKey`; scene identity is coupled to three progress categories. `_INTENT_TESTS` and `_OUTCOME_MAPPERS` in `journey_conversation` are family-specific. Changing only the generator prompt would leave generated objectives unsupported by evaluation and transport.
- Serial already has durable `SerialThread.state`, relationships/callbacks, episode briefs, authored arc stages, generated missions/scenes, and completion ownership. `SerialArcPlanner` reads durable state and authored arcs. After the available authored seasons, it falls back to interludes instead of creating a new main arc.
- Daily journey outcomes can update serial memory when bound, but `apply_journey_story_outcome` explicitly does not advance an episode or arc. The next-day callback gap in the independent review remains open.

Reuse and extend this existing story engine. Do not create a competing story, scheduler, transcript archive, or memory database for daily practice.

## Product behavior

The learner lives one ongoing French life with a stable cast. The next conversation follows from what has happened, what characters want, unresolved commitments, and the learner's demonstrated language needs. Not every day needs a plot twist; quiet scenes and revisiting a skill are valid when the situation makes sense.

Illustrative acceptance narrative, not a hardcoded new script:

1. The learner agrees to help Romy organize a small neighborhood event.
2. Their choice of venue creates a reason to ask Margaux about availability.
3. A constraint at the venue creates a new need to compare alternatives or negotiate a time.
4. The learner changes the arrangement; Romy responds to that actual decision.
5. The event concludes, resolving the commitment and leaving a plausible opening for a later chapter.

Declining to help must lead to another coherent path. Characters cannot remember conversations they did not witness or learn about. A grammar mistake must not arbitrarily sabotage the event. Visiting optional Stories or conversation screens must read the same world and cannot double-complete the same beat.

“Recognize opportunities” means detecting explicit proposals, choices, unresolved misunderstandings, commitments, and topic interests inside the learner's in-app interaction. It does not require surveillance, external accounts, or real-time news. Distinguish fictional roleplay facts from real learner biography. Proposed plans are not completed events. A passing mention is not a durable preference. Clarify ambiguous commitments; do not silently rewrite canon.

## WP-14A — Contract and continuity integration design

**Owner:** integration lead. **Dependencies:** inspect the committed functional implementation and NEXT-STEPS-REVIEW; all downstream modules use one frozen revision.

**Own:** shared journey contracts/schemas, contract documentation, migration allocation and file leases. Submit integration changes through current service owners.

**Deliver:**

- Separate stable learning capability IDs from generated situation/episode IDs. Keep historic progress and existing clients readable. A novel situation may exercise an existing capability; a new objective does not automatically invent a certified capability.
- Specify a typed story context: canonical episode/arc reference, revision, relevant known facts with provenance, participating character knowledge, open commitments, learner-declared choices, relevant learning targets, and recent semantic situation history.
- Specify a pinned scene plan: situation ID, objective/rubric version, premise and reason it follows, preconditions, bounded turn/time budget, allowed outcome operations, source references, and completion owner.
- Specify guarded state transitions: distinguish a daily side scene from an actual short episode. Completing a bound episode uses existing serial completion exactly once; an unrelated episode remains untouched.
- Plan compatibility for active V1 journeys and typed clients. Freeze any V2 wire changes before consumers implement them. Do not relabel deployed V1 structures without a coordinated migration.

**Acceptance:** every field has a producer, consumer, storage location, authority, and retry/rollback behavior. Generated prose is never the canonical state store. No second independently advancing episode cursor.

## WP-14B — Story planning, memory retrieval, and continuation

**Owner:** story-engine agent. **Dependencies:** 14A; grounded outcome fixes R-1/R-2 before final integration.

**Own:** an adapter such as `app/services/journey_story.py`; narrow changes to `serial.py` and `serial_arc_planner.py`, plus associated tests. Exclusive serial-service lease; coordinate with WP-06.

**Implement:**

- Build compact context from the existing canonical state and eligible past events, including authored/unbound journey history through a documented binding policy. Cover new learners with no serial thread through the normal thread initialization path.
- Select the next scene from unresolved commitments, causal consequences, current arc needs, relationship development, and relevant learning needs. Recency rotation alone is insufficient.
- Plan bounded chapters with setup, development, and resolution. Expand the near-term beat in detail and keep later plans provisional; invalidate future candidates when the learner makes a different choice. Do not pre-generate a large branching tree.
- After authored arcs are exhausted, propose and validate a new bounded arc consistent with the established cast/world. Keep provenance distinguishing established facts from proposed future events. Persist accepted plans through the existing story owner, with a coherent interlude fallback if generation fails.
- Retrieve relevant memory with character knowledge and temporal constraints. Update accepted outcomes atomically and deduplicate completion across daily/legacy routes.

**Acceptance:** the R-3 next-day callback requirement works as part of a causal continuation; optional screens share the same world; the story can reach and leave an arc ending without cycling finales or pretending a new arc was played. A short daily session can advance the story when it truly completes the bound beat.

## WP-14C — Generate materially new, learnable situations

**Owner:** content-generation agent. **Dependencies:** 14A, stable 14B context interface; may develop against agreed fixtures before 14B integrates.

**Own:** journey content adapter/prompts/validation and scenario fixtures. Coordinate changes to existing content files; do not independently mutate serial state.

**Implement:**

- Generate scene premises and communicative objectives from the story plan and learner context, beyond the three authored templates. Supported cast, location, time, and story constraints remain stable; generated situations need not invent a new person or place every day.
- Produce a usable objective, private semantic rubric, elicited facts, attainable endings, and optional assistance. The help response must satisfy that exact task without being leaked into its public setup.
- Validate causal fit, character knowledge, level, target relevance, objective solvability, outcome preconditions, and consistency among dialogue/help/recap. Use structured checks plus sampled semantic review; schema validity alone does not prove coherence.
- Detect repeated semantic situations using recent objectives, conflict/premise, and resolution patterns, not only text equality. Distinguish intentional spaced practice in a new context from accidental repetition.
- Pin content for resume; key generation caches by the relevant story revision, scene identity, learner context and prompt version. A cache keyed only by user and exercise family is insufficient.
- Bound cost, attempts, and latency using existing generation infrastructure. Generation is on demand or through existing bounded prefetch, not an unrequested always-running service. Authored content remains an honest fallback, and must fit current canon.

**Acceptance:** produce a coherent new situation absent from the authored catalog, with a new communicative need and validated outcome path. Changing wording around another coffee order does not meet this requirement. Reopening or retrying preserves the same approved scene.

## WP-14D — Semantic conversation and emerging opportunities

**Owner:** conversation/evidence agent. **Dependencies:** 14A, R-1/R-2 fixes; final integration with 14B/14C.

**Own:** `journey_conversation.py` and narrow learning-evidence changes. No parallel owner edits in those files.

**Implement:**

- Evaluate generated objectives against their versioned rubrics and current conversation context, including prior turns, negation, reference resolution, revised choices, and legitimate paraphrases. Do not treat unknown intents as successful merely because the answer contains several words.
- Extract candidate in-story choices, proposals, and unresolved needs from the exchange. Validate them against established facts and allowed operations before they affect future planning. Clarify consequential ambiguity; distinguish character speech, learner action, and hypothetical language.
- Adapt a current conversation to a relevant unexpected proposal where feasible. Preserve the short daily ending; let a larger new opportunity become a later scene instead of forcing extra tasks now. Existing optional longer conversation remains available.
- Separate linguistic quality from narrative choices. Successful communication of a refusal is valid behavior, even when it closes a different path than an invitation acceptance.
- Keep progression honest: reuse the existing evidence policy and capability registry; novel unsupported capabilities stay unknown rather than claiming mastery. Provider failure is unscored or a supported fallback, never fabricated semantic certainty.

**Acceptance:** an unanticipated but valid learner proposal can change a subsequent situation, with traceable provenance and coherent character response. No model reply overrides an established learner decision; no ambiguous/negated mention earns false evidence.

## WP-14E — Daily and optional surfaces share the story

**Owner:** daily-experience agent coordinated by integration lead. **Dependencies:** 14A–D integrated.

**Own:** daily orchestration through its existing owner and frontend journey controller/renderer; optional route changes through their owners.

**Implement:** connect the approved next story beat to the existing daily plan, contextual review, text/voice response, completion and resume. Read the same context from optional conversation/Stories routes. Use current presentation until Claude components are ready; no new design direction. Render enough context to understand today's need without a long recap dashboard.

**Acceptance:** one real authenticated daily journey consumes a generated situation and commits a grounded outcome; a later journey/optional story uses it, with no duplicate completion or progress from revisiting another surface.

## WP-14F — Longitudinal integration and generation review

**Owner:** independent QA agent; integration lead accepts evidence. **Dependencies:** 14B–E; test planning can start after 14A.

**Deliver and verify:**

- A controllable-clock sequence of at least 14 daily sessions per representative learner: A1, A2, and a higher-level learner to verify suitable content or an honest supported-level limit. Extend through an arc ending and the start of a new arc even if more than 14 sessions are needed.
- Demonstrate multiple materially different generated situations beyond the original three families, an explicit learner proposal affecting later planning, and at least one chain of three causally connected scenes. This is evidence coverage, not a novelty quota forced on real learners.
- Test refusal, changed plans, failed communication, a skipped day, abandoned drafts, concurrent optional/daily completion, stale generation, duplicate requests, absent memory, superseded facts, and another learner's data.
- Assert specific world invariants and provenance. A substring callback assertion or a different scenario key alone is insufficient.
- Run a bounded real-model sample and review coherence, natural French, level fit, useful correction, and novelty. Separate deterministic/mock results from actual provider quality. Record models, prompt/rubric versions, cost and latency; use synthetic accounts and keep ordinary tests provider-isolated.
- Report repetitive loops, unsupported inferences, invented past events, impossible knowledge, unclosed commitments, and failed outcome consistency. Keep unresolved failures visible; do not use expected-failure markers to declare the feature complete.

**Acceptance:** code, real API integration, longitudinal deterministic coverage, and reviewed generation samples support the claimed feature. No promise of indefinitely perfect or endlessly unique storytelling; report the tested horizon and remaining limits.

## Dispatch and release gate

One integration lead, up to three concurrent subagents when supported. Run 14A first; then 14B and 14C can develop with agreed interfaces while 14D handles semantic evaluation. Lease shared files explicitly and integrate in dependency order. Follow with 14E and independent 14F. No automatic production deployment or live-data migration testing.

This extends the accepted functional scope beyond the original WP-12 functional pass. WP-14 must pass before declaring the coherent continuously evolving experience ready. Final Claude UI, native/accessibility, learner validation and WP-13 rollout gates still apply. A repaired one-day callback or three rotating templates does not close WP-14.
