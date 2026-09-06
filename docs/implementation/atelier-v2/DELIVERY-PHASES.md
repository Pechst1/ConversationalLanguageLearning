# Functional foundation first; Claude Design for the UI

**Scope update — 2026-09-06:** the owner requires new generated situations within one coherent continuing story. [WP-14](CONTINUOUS-STORY.md) extends the initial functional foundation and is a prerequisite for final product/rollout readiness, alongside the visual and QA gates below. R-1/R-2 correctness fixes precede its final integration. Design mapping can proceed independently; three rotating templates or a single callback fix do not complete this extension.

## Owner decision — 2026-09-05

The owner likes the conceptual direction and implementation packages, rejects the earlier Codex visual vision, and wants to use their promising Claude Design version for the UI.

Consequences:

- Keep the connected daily situation, short-session planning, shared learning evidence, grounded character continuity, capability progress, and reliability work.
- Archive the Codex visual proposal as non-authoritative. Do not port its CSS, font choices, button style, flower, or navigation composition.
- Implement backend and presentation-independent client behavior first. Validate it through existing components before the new design is integrated.
- Use Claude Design for final screens, components, and interaction presentation. Do not claim that the unseen design covers every required state.

## Claude source-of-truth record

| Field | Status |
|---|---|
| Exact artifact link / repository path | [Atelier Home Directions.dc.html — Claude Design](https://claude.ai/design/p/5ed85a9c-deef-4594-a0f4-8cad9ca1894e?file=Atelier+Home+Directions.dc.html&via=share), supplied by the owner on 2026-09-05 |
| Access check | 2026-09-05 (planning): opened the exact link; redirected to Claude sign-in. 2026-09-05 (implementation pass): re-checked through two channels — the artifact reader rejects it (`not an artifact URL`; a `claude.ai/design/p/<uuid>` project is not a `claude.ai/code/artifact/<uuid>` artifact), and the `DesignSync` design-system API returns **`DesignSync needs design-system authorization`**. No design content inspected |
| Unblocking action (owner) | Run **`/design-login`** once from an interactive `claude` terminal session on this machine, then re-run `DesignSync list_projects`. Alternatively use Claude Design's **"Send to Claude Code Web"** to seed the project into the workspace, or drop a local export of `Atelier Home Directions.dc.html` into `docs/design-reference/claude/`. Note `list_projects` returns only projects the account can **write** to, so a view-only share link may still not appear — a local export is the most reliable route |
| Artifact version / export date | Not recorded |
| Selected variant | Not recorded |
| Inspected screens and interactions | Not inspected |
| Reusable code/assets and font licenses | Not inspected |
| Light/dark/responsive/state coverage | Not inspected |

Existing files under `docs/design-reference/` must not be assumed to be the newly selected version. Once authenticated access or a local export is available, the integration/UI owner records the inspected version and maps it below. The filename alone does not establish which screens or variants exist. Backend work does not wait for this record to be complete.

## Phase 1 — functional contracts and backend

Order: **WP-00 → WP-02 + WP-03 → WP-05 → WP-04 + WP-06**. WP-11 event infrastructure can start after WP-02. Use one integration owner and the established file leases.

Preserve the existing database/services; add journey coordination. Prove one café scenario end to end before widening content to the other two scenario families. This limits the cost of discovering a wrong interface after many screens are built.

Deliverable: authenticated real APIs and stable typed client contracts for creation, help, attempts, consequences, resume, and completion. No new visual-system dependency.

## Phase 2 — real connected flow in the existing UI

**WP-07 functional** builds `useDailyJourney`, typed state selectors/actions, request identity/error handling, and a thin renderer using the current app’s components. It consumes real WP-02/04/06 responses. It may introduce the minimum missing behavior needed to exercise the new flow, but does not redesign global styles, change navigation, or create another visual concept.

**WP-09 functional** builds capability evidence/reward services, real endpoints, and tests. Existing summary/list components may expose this data for QA; its final notebook layout waits for Claude Design.

**WP-10**, **WP-11**, and **WP-12 functional** validate interruptions, idempotency, timing, learning credit, character outcomes, and the complete loop. Do not mark a whole package complete if its visual milestone is pending.

Keep hooks/services separate from presentational React components. The later UI migration must reuse the same requests, evidence policy, and state transitions rather than implement another flow.

Deliverable: a feature-flagged, functionally tested experience with current styling. It is not the final UI or a production-launch declaration.

## Phase 3 — Claude Design integration

This can begin as soon as the linked artifact is accessible, inspected, and mapped; the backend need not be entirely finished. Freeze interface contracts early, then refine UI mapping in parallel.

1. WP-01 inventories the actual design and maps tokens/assets/components to semantic app states.
2. WP-07 visual replaces the temporary daily-flow renderer with Claude’s composition.
3. WP-08 migrates companion screens and navigation; WP-09 visual migrates notebook/progress.
4. Revalidate WP-10/11 seams and run WP-12 final visual/native/accessibility checks. WP-13 final rollout remains after the final gates.

The design mapping must cover: recommended activity, active/resumed session, scene reading, recall, open response, voice/text switch, help, pending evaluation, correction, supported success, independent success, partial ending, full completion, unavailable generation, offline/unsynced draft, permission failure, version conflict, legacy resume, and empty progress. Also map existing optional tools/deep links and large-text/dark/keyboard-open states.

If a design screen is missing, record the gap and implement a coherent extension from its actual primitives. A layout may change; false completion, hidden data loss, or inaccurate learning credit may not be introduced to make a mockup easier to reproduce.

## Milestone identifiers and gates

These suffixes identify milestones within existing packages; they do not create competing file owners.

| Milestone | Hard dependencies | Exit condition |
|---|---|---|
| WP-07 functional | 02,04,06 | Real daily flow works with existing presentation |
| WP-09 functional | 05,06 | Evidence/reward APIs and data tests pass |
| WP-12 functional | 02–06,07 functional,09 functional,10,11 | Functional integration/recovery gate passes |
| WP-01 | 00 + mapped Claude artifact | Design-derived primitives and state mapping ready |
| WP-07 visual | 01,07 functional | Final daily renderer uses Claude system |
| WP-08 | 01,06,07 visual | Companion screens and preserved routes integrated |
| WP-09 visual | 01,09 functional | Final notebook/progress UI integrated |
| WP-12 final | 12 functional,07 visual,08,09 visual | Final design, native, accessibility, and learner gates evaluated |
| WP-13 final | 00,12 final | Rollout/rollback readiness; deployment is separate |

The functional gate excludes WP-01/WP-08/final visual milestones. The final release gate includes them. WP-10’s recovery and WP-11’s events must be retested after the final UI changes; they do not block backend work on missing design assets.
