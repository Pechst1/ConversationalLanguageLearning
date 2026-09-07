# Atelier V2 stabilization — 2026-09-06

Baseline: commit `04998ec` plus the existing uncommitted implementation. This pass
preserved those changes, repaired the remaining local checks and verified the assembled
completion flow. No production rollout or paid generation was performed.

## Changes completed in this pass

- **Invitation level:** `living_story.describe_next` and scene generation now share one
  level resolver. Invitations no longer label every learner A1. API regressions compare
  invitation and generated-scene bands for A1, A2, B1, B2 and the existing B2 ceiling for C1.
  Merely reading the invitation makes no director call.
- **Grammar summary:** Le Relevé now counts the same active curated catalog as the Cahier.
  It also initializes that catalog when opened first. Previously it counted an active
  Spanish concept left by an earlier full-suite test, producing 55 versus 54; this was a
  real query mismatch rather than the French-language alias archival defect suspected
  in older notes. Started, due, new and level counts now use the same scope. Regression
  coverage includes archived French progress and active Spanish progress, preserving
  both records while excluding them from the French summary.
- **Longitudinal QA:** repaired two incorrect test assumptions. A completed exchange
  still requires acknowledgment of the resolution before finish; the test now does this
  and checks the finish response before inspecting credit. Initial director contexts
  legitimately have null thread IDs, so isolation is asserted against distinct published
  threads, empty foreign history, archive exclusion, and cross-learner read/write 404s.
- **Recap layout:** restored padding inside the rounded recap header. Browser inspection
  found its text clipped against the left edge; the rebuilt page displays it fully.
- **Lint:** removed the unused old-scene local and cleaned the existing exploratory R-1
  probe's imports and statement formatting. The probe is exploratory, not acceptance
  coverage for the still-open authored-grader defect.

## Verification

| Check | Result |
|---|---|
| Targeted grammar, address preference and longitudinal API tests | 43 passed |
| Complete backend suite | **1,428 passed, 1 expected failure (D-1b), 254.36 seconds** |
| `ruff check .` and `git diff --check` | Pass |
| Frontend type check and lint | Pass |
| Journey, recovery, story-model, reader, UI, API-host, atelier-next, image-helper and native-environment suites | Pass |
| Production web build | Pass; isolated copy, explicit API host |
| Native static build | Pass with CI's explicit placeholder API override; not a device test |
| PostgreSQL migration cycle | Pass, including seeded legacy-row checks and downgrade to base |
| Authenticated browser daily flow | Pass with fake provider and a disposable database |

### Migration evidence

Used only PostgreSQL database `atelier_stabilization_20260906`, created for this pass.
Provider credentials were replaced with obvious fake values before application imports.

1. Upgrade an empty database to head `a3b4c5d6e7f8`.
2. Insert a synthetic learner with streak 7, longest streak 19, last grammar review
   2026-09-05, XP 1234 and feminine address preference.
3. Downgrade to `c5d6e7f8a9b0`, below the settings migration. Streaks, review date and XP
   remain exactly unchanged. This validates the existing migration ownership repair.
4. Upgrade to head. Legacy values remain unchanged; the newly introduced address
   column reads `neutral` for the existing row.
5. Downgrade to base, verify the users table is absent, then upgrade to head again.

### Browser evidence

An isolated production frontend on port 3011 used `scripts/dev_story_engine_server.py`
on port 8011, with the fake provider and the disposable database. The user's existing
servers on 3000/8010 were not modified. A synthetic B1.2 learner signed in normally.

- Start today → generated scene → panel 3 of 3.
- Reload → Continue today → panel 3 of 3 restored.
- Continue → type a response → send → character feedback → resolution → Continue.
- The final advance and finish both return 200; no stale-revision 409.
- Recap displays **Scene finished**, measured duration, character name and saved callback.
- Database: journey `completed`, revision 7, no current step, recap completion kind
  `complete`; its daily learning session is also `completed`.
- Reload shows **Today's scene is done**. Continue reopens the saved recap.
- Final recap padding visually checked after rebuilding. At the narrowed browser size,
  measured viewport and document width were both 582 CSS pixels, with no horizontal
  overflow. The browser did not expose the requested 390-pixel width; this is not evidence
  for a physical phone or the 320/390-pixel release gates.

Transient execution logs are in `/tmp/atelier-stabilization-*`; the evidence and limits
above are retained here because those temporary logs may be cleared.

## Still open

- Authored compatibility path: R-1 negation grading and D-1b next-day grounding. D-1b
  remains an explicit expected failure; the engine's longitudinal tests do not close it.
- WP-14F bounded real-provider longitudinal review, especially situation variety,
  level fit, natural French, corrections and register. Scripted 14-day sequences across
  A1/A2/B1 validate state, not prose quality.
- Pre-hydration authentication form behavior and explicit API/seeder alignment in the
  mobile capture harness.
- Full responsive/accessibility/theme coverage, real voice, simulator/physical-device
  lifecycle checks, learner study, Docker build and controlled rollout.
- Distinct generated panel illustrations and demonstrated visual continuity.
- Review and commit the accumulated working-tree changes. No commit or deployment was
  made by this pass; production feature flags remain unchanged.
