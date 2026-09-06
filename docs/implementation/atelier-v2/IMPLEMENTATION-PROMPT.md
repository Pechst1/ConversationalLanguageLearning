# Copyable implementation prompt

You are the lead implementation agent for Atelier, an existing French language-learning app. Start implementing the accepted work packages now. Deliver working, tested code; do not stop at another plan.

Repository: `/Users/vincentpechstein/Downloads/Pixel-lab/ConversationalLanguageLearning` (use the equivalent checkout path if your environment differs).

## Source of truth

Read applicable repository instructions and these files before editing:

- `docs/implementation/atelier-v2/README.md`
- `docs/implementation/atelier-v2/CONTRACTS.md`
- `docs/implementation/atelier-v2/WORK-PACKAGES.md`
- `docs/implementation/atelier-v2/DELIVERY-PHASES.md`
- `docs/implementation/atelier-v2/STATUS.md`
- `docs/implementation/atelier-v2/NEXT-STEPS-REVIEW.md`
- `docs/implementation/atelier-v2/CONTINUOUS-STORY.md`

Inspect actual code and current status; the specifications describe proposed contracts, not already implemented APIs. Resume verified completed work rather than repeating it. Resolve genuine code/spec incompatibilities through one documented contract revision, coordinated with all affected agents.

The owner accepts the functional concepts and rejects the earlier Codex visual proposal. Do not implement `docs/atelier-redesign/` styling or invent a replacement visual direction. The selected UI reference is:

https://claude.ai/design/p/5ed85a9c-deef-4594-a0f4-8cad9ca1894e?file=Atelier+Home+Directions.dc.html&via=share

This link previously redirected to sign-in; its content has not been inspected. Record the actual version/variant when accessible. Missing design access must not block functional work.

## Scope and implementation order

Your objective is to finish the functional foundation, close the independent review findings, and implement **WP-14A–F: generated new situations within one coherent continuing story**, behind the default-off feature flag, using existing UI components. Final Claude visual implementation is a subsequent milestone. Keep controllers, state transitions, and API calls separate from presentation so the design can be integrated without rewriting behavior.

The original foundation was committed as `b0f3602`. Verify current status and reuse completed work. Steps 1–5 below describe prerequisites, not instructions to redo completed packages. Continue with the R-1/R-2 fixes, then the WP-14 contract freeze and its dependency-ordered implementation. The existing callback fix R-3 is part of this larger requirement.

1. Complete WP-00 first: preserve the current working state, establish a reproducible baseline, inspect migrations and existing failures, freeze contract fixtures, and allocate file ownership. The worktree contains substantial uncommitted work; never reset, clean, overwrite, or silently omit it. Exclude credentials, databases, and caches from baseline artifacts.
2. Implement WP-02 and WP-03 concurrently where independent.
3. After WP-02, implement WP-05 and start WP-11. WP-07 may prepare its hook/client against fixtures, but mocks are not completion.
4. After WP-03/05, implement WP-04 and WP-06. Integrate WP-07 functional and prove **one café journey end to end** before expanding the remaining scenario families.
5. Complete the three scenario families, WP-09 functional, WP-10, WP-11, and WP-12 functional. Follow the exact acceptance criteria and tests in the package documents.

The café flow must use real authenticated APIs: start → contextual recall → purposeful text/voice response → grounded consequence → completion → persisted evidence, including refresh/retry recovery. Keep final visual work (WP-01, WP-07 visual, WP-08, WP-09 visual) pending in this implementation pass. Record accessible Claude design information for the later handoff. WP-13 rollout readiness requires WP-14 and final QA; do not enable production.

## Subagent execution

Use subagents for concrete implementation and review tasks. You remain the integration owner, responsible for dependencies, shared contracts, integration, tests, and the final result. Use up to three concurrent subagents plus yourself, bounded by available capacity. If subagents are unavailable, execute the same sequence locally.

- After WP-00, assign one agent WP-02 and another WP-03; perform useful integration/fixture work yourself. Do not fill slots with dependent tasks just to maximize concurrency.
- Reassign available agents as dependencies land: WP-05, WP-11, then WP-04/WP-06 and WP-07 functional. Keep each task bounded to a package or explicitly named milestone.
- For every assignment provide the baseline, prerequisite status, exact package/milestone, allowed files, interfaces, acceptance tests, and required handoff. Require agents to read the shared documents.
- Prefer isolated checkouts based on the preserved working-state baseline, including relevant uncommitted files. A checkout of old HEAD alone is insufficient. In a shared checkout, record exclusive file leases in STATUS before editing. Never allow concurrent edits to the same file.
- Follow the shared-file ownership table. Route registration, migration, orchestration, and shared-service changes go through their assigned owner. A dependency does not grant permission to edit another agent’s files.
- Integrate in dependency order. Inspect changes and run relevant tests yourself; do not accept an agent’s completion claim without evidence. Have an agent review functional integration independently where possible.
- Require handoffs listing changed files, interfaces, actual test commands/results, remaining gaps, and compatibility impact. Update STATUS after every integrated milestone. Subagents must not recursively delegate without your coordination.

## Non-negotiable behavior

Reuse existing SRS, learning evidence, error memory, story state, audio, and telemetry services. Preserve authentication, ownership checks, learner history, legacy sessions, and optional tools. No parallel scheduler or character-memory store. Distinguish assistance from independent production. Make retries and completion idempotent. Never present scripted dialogue, fabricated progress, or mock data as real functionality.

Use targeted behavioral tests while developing, then the documented assembled functional checks. Test migrations only on disposable databases. Verify the actual connected frontend flow. Report pre-existing failures separately; mark unavailable model/device/learner checks pending. Functional completion does not imply final visual or launch readiness.

Make routine implementation decisions autonomously. If one task is blocked, continue independent authorized work and report the specific blocker. Keep updates concise. Do not deploy, publish, contact others, remove live data, or mark unexecuted gates passed.

Start with repository/status inspection and verification of the preserved baseline; resume from actual completed milestones. WP-14 uses the same exclusive file ownership and integration rules. The story and content agents may develop against frozen interfaces concurrently, while conversation/evidence has one owner. Finish with a concise report of integrated milestones, actual verification, unresolved blockers, and the next visual milestone.
