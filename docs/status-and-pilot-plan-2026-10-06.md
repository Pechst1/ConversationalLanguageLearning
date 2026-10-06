# App assessment and proposed personal pilot — 6 October 2026

> **Update 7 October 2026 (WP-138, branch `fix/1007-integration` on top of `release/rc-2026-10-06`).** Each point below was rechecked against the release candidate and fixed where it was still true:
>
> | Point | State on 7 October |
> |---|---|
> | 1 Release candidate | `release/rc-2026-10-06` exists, Ruff passes; this branch adds the fixes listed here. Pushing it is still the owner's call (E1-LANDING-PLAN). |
> | 2 Failed day keeps the story | Season learners already got the WP-124 re-read/bridge path. A learner on a generated serial that had already started now gets an honest "unavailable, retry" rather than an unrelated scene. Authored scenes exist up to B1; B2/C1 get B1. |
> | 3 Saved-word round trip | Fixed. Scene words no longer write a foreign gloss into the target-language column; lookup and keep share one row choice; refusals are structured (`code`, `retryable`) and localized. The walk syncs the core list and `keepAWord()` checks the save itself. Test: `tests/test_keep_word_round_trip.py`. |
> | 4 Letter grading | Fixed. An unused grammar or repair target no longer becomes an erratum or a "partial" verdict (`_separate_target_practice`, prompt `mission-correction-v2`). |
> | 5 Starting level | Already done: A1–C1 at signup, placement after day 1 or at any time from Settings. |
> | 6 Config and access | `.env.prod.example` matches `render.yaml` (cohort included). `REGISTRATION_OPEN` / `REGISTRATION_ALLOWED_EMAILS` restrict sign-up; Render sets sign-up closed. APNs production on API and worker. The Compose API port is bound to localhost. |
> | 7 Hosted verification | Owner action, not done. |
> | Week-one 2 drill size | Intended: 8 per session plus «Encore N mots» (WP-131 owner decision 9). |
> | Week-one 3 calibration | Already top-down (WP-127). |
> | Week-one 4 held grammar | Fixed. "Held" needs an unaided spaced item at least 20 h after the previous contact with the rule. |
> | Week-one 5 grammar review on milestone days | Already done (WP-129 tentpole review in context). |
> | Week-one 6 Lila reaction | Already authored (WP-132A); a regression test was added. The epilogue is still open. |
> | Next.js | 15.5.27; the 23 direct Next advisories are gone. Remaining audit items: next-auth, `@capacitor/ios` < 8.4.3, and smaller transitive packages. |
> | Artwork on account deletion | Fixed: best-effort S3 and local purge of the user's scene artwork. |
> | Walk French-only failures | Forge rule card now follows the Forge's language (product fix); Settings follows the native language by WP-46 (walk assertion fixed). |
> | Legal contact e-mail | Still open; the owner must supply it. |

**Assessment: a substantial, visually coherent app that needs a focused stabilization and deployment pass before a reliable personal production pilot.** Feature breadth is sufficient to start learning from daily use. The immediate priority is preserving story continuity, trustworthy grading, saved learning progress, and an appropriate level.

This assessment covers the current working tree, including its existing uncommitted fixes. It does not establish what is deployed. No application source was changed, no real learner data was changed, and no paid AI or email calls were made for this review.

**What is already present**

- A recurring cast and authored first season, consequential choices, generated intervening days, a daily learning journey, and a readable episode archive.
- Conversation, corrections, vocabulary memory and review, grammar practice, letters, notebook/progress, Anki import, and real-world rehearsal.
- Additional Revue, Radio, map, journal and before/after learning surfaces. These should be assessed for integration and discoverability before adding more destinations.
- A consistent mobile visual identity, light/dark presentation, and a Capacitor iPhone build/release path. Fresh first-day screenshots show a clear main action, readable story panels and a coherent recap.
- Persistent accounts and learning state; refresh-token rotation and revocation; password recovery with durable email retries; upload limits; rate limits; provider/cost safeguards; observability; worker health; migration checks; a restore verifier; and release workflows.

The existence of these features is stronger evidence than a roadmap entry, but it is not proof of their real-device or deployed-provider behavior.

**Fresh checks**

| Check | Result |
|---|---|
| Frontend test suite | 887 passed |
| TypeScript without incremental output | Passed |
| Frontend lint | Passed with one notebook hook dependency warning |
| Isolated production web build | Passed; Next.js 14.2.35; 61 static pages generated |
| Focused experience, production auth/release/upload, journey capability and season tests | 150 passed, 1 intentionally skipped transcript-export test |
| Independent focused backend hardening checks | 60 passed; overlaps the 150-test selection, so do not add these counts |
| Repository-wide Python Ruff | Failed: 70 findings, mostly hygiene/test/script issues; not 70 functional defects |
| Full browser walk | Running at time of initial report; final result recorded below |
| Full backend suite, 15-life experience matrix, native archive/device smoke, live provider quality and deployed recovery | Not rerun/verified by this assessment |
| Full npm registry vulnerability audit | Unverified: automatic approval review rejected the network retry because it would send package metadata to npm without specific authorization |

The web build used a separate output directory, which was removed; tracked TypeScript configuration and dependency files remained unchanged. The focused 150-test run used the repository's `venv` (Python 3.14) and emitted its Pydantic compatibility warning; the project/CI target is Python 3.11, available locally in `.venv`. A release run should use that supported runtime consistently.

Local evidence: `/tmp/cll-assessment-frontend-test.log`, `/tmp/cll-assessment-build.log`, `/tmp/cll-assessment-ruff.log`, `/tmp/cll-status-backend-2026-10-06.log`, and `/tmp/cll-status-browser-2026-10-06/`.

**What I would do before personal daily use**

| Order | Work | Why / acceptance criterion |
|---|---|---|
| 1 | Preserve and identify one release candidate; resolve current release failures | Important fixes currently exist only in the working tree. Run release gates against one integrated candidate, including supported Python, browser behavior, PostgreSQL, and the selected web/native build. Do not equate older QA reports with current results. |
| 2 | Make a failed generated day preserve the ongoing story | Current fallback rotates generic scenes, capped at A2, with `bind_serial=False`. Offer an honest replay/recap of the last page and a recoverable continuation. Avoid duplicate learning credit or fabricated choices. Add an authored bridge if repeated failures would otherwise stall the season. |
| 3 | Correct letter grading | A missing target word currently produces an erratum and can downgrade an otherwise accepted reply. Separate successful communication, optional target practice and actual language errors. An unused target must not become a false grammar/vocabulary error. |
| 4 | Start the owner at the right level | Current signup offers only A1/A2/B1 starting points; placement waits for three completed days. For the owner pilot, an explicitly selected starting band and voluntary early placement are enough. Build the full bounded, top-down vocabulary calibration afterward. |
| 5 | Reconcile the production configuration and restrict pilot access | `.env.prod.example` omits the required journey cohort; Render and the runbook disagree on several defaults. Use one canonical deployment recipe. A journey cohort is not an invite gate: signup currently accepts arbitrary emails. Restrict registration/access to the owner and bound provider spending for the private service. |
| 6 | Verify the hosted app through a real device and recovery cycle | Check API readiness plus worker health, one real story/reply/correction/audio flow, actual password recovery, pause/reopen, offline/reconnect and next-day return. Restart/redeploy and confirm progress survives. Configure backups and restore a real pilot backup into an isolated database. |

Primary code evidence:

- Story fallback: `app/services/daily_journey.py:3482` (A2 ceiling and unbound fallback), called by `_serve_authored_fallback`.
- Letter assessment: `app/services/missions.py:3410` (negative event), `:3445` (accepted becomes partial).
- Signup bands: `app/schemas/user.py:111`; placement delay and same-band evidence: `app/services/placement.py:474` and `:514`.
- Missing production setting: `.env.prod.example`; enforced by `app/main.py:48`; Render specifies it at `render.yaml:143`.
- Registration versus journey cohort: `app/services/auth.py:98` and `app/services/daily_journey.py:349`.
- Publishing depends on the failing backend lint job: `.github/workflows/ci.yml:24` and `:101`.
- Deployed backup work remains explicit in `docs/production-hardening.md:90`.

**Changes to prioritize from the first week of use**

1. Fit the complete recommended routine to the chosen time budget, including practice. Current timing has a page-reading multiplier, but level-specific calibration still needs human evidence. The October 4 simulations suggest beginner overload and advanced underfill; those are modeled findings, not measured human durations.
2. Make advanced practice useful and new-word targets achievable. The normal vocabulary drill still requests eight new words regardless of the higher rhythm allowances (`web-frontend/pages/vocabulary/review.tsx:108`). Contextual word selection should support the current scene and the learner's interests.
3. Shorten calibration. Vocabulary checks still work through lower bands in ascending order (`app/services/band_check.py:157`), making an advanced learner's assessment unnecessarily long. Keep inferred knowledge distinct from demonstrated recall.
4. Make progress understandable. Align the notebook's labels with the level view, and deliberately schedule delayed independent reuse. Preserve the evidence required for retained grammar rather than granting mastery for elapsed time (`app/services/concept_life.py:15`).
5. Put a short contextual grammar review back into authored milestone days. The current daily journey suppresses that review and sends it to optional Forge (`app/services/daily_journey.py:3217`, `:3896`).
6. Finish the missing immediate reaction to Lila's affirmative key choice and the eventual season epilogue. The early reaction is small and visible; the epilogue can be completed before the owner reaches it.

These findings align with the existing October 4 proposed work packages. Use that backlog instead of starting a second overlapping implementation plan: `docs/implementation/atelier-v2/WORK-PACKAGES-2026-10-04-experience.md`. Personal testing can begin after the release and core-flow work above; the entire longer-term backlog need not precede it.

**The additions I would find most fun and valuable**

| Idea | Concrete experience | Reuse what already exists |
|---|---|---|
| Speaking inside the story | Hear a character, answer aloud for 20–30 seconds, hear a response that acknowledges the meaning, and optionally repeat one useful line | Audio, voice composition and shadowing foundations already exist. Bring them into the core daily flow and verify real-device behavior. |
| A weekly personal keepsake | A small edition containing an actual sentence you can now say, a retained skill and a story choice that mattered; optionally compare two real recordings | Use the journal, stored evidence and existing before/after Relecture. Add earlier, concrete proof of progress without invented scores. |
| A real-world payoff | After practicing a skill, offer a relevant rehearsal such as booking a table, then return for a short debrief after trying it outside the app | Répétition and outcome reporting already exist. Connect them to demonstrated skills rather than building another mode. |
| Visible character consequences | A brief reaction when you make a choice, followed by a later callback that respects the saved story state | Extend existing choices and character memory. Start with the missing Lila reaction. |

My first choice is the spoken story exchange, after the reliability work. It strengthens the app's central experience and makes the existing cast more memorable.

**Before inviting other testers or opening a public website**

- Upgrade the public web runtime from Next.js 14 to a supported, patched release and rerun the applicable dependency/security checks. The official [support policy](https://nextjs.org/support-policy) lists 14.x as unsupported; the [30 September security release](https://nextjs.org/blog/september-2026-security-release) provides patches on the 15 and 16 lines. This is not a claim that every listed vulnerability applies to this Pages Router app or its static iPhone bundle.
- Complete the legal contact field (`app/data/legal/legal_content.json:5` still contains `[contact e-mail]`) and review the actual data handling.
- Add external artwork cleanup to the account-deletion lifecycle before personalized S3 artwork is broadly enabled. The current account-deletion method deletes relational data; no external object deletion path was found (`app/services/users.py:68`, `app/services/graphic_novel_image_storage.py:218`).
- For TestFlight, verify production push configuration on both API and worker. Render currently sets sandbox APNs on both; the repository's release checklist requires the production setting for TestFlight.
- Verify deployed monitoring, backup retention, access restrictions and rollback. Repository manifests alone cannot establish that hosting account settings are applied.
- Sample real generated days at the levels actually offered, including provider failure. Scripted walks cannot certify prose quality, correction accuracy, voice quality or desire to return tomorrow.

**Proposed sequence and decision rule**

Assemble and fix the candidate → deploy privately → complete one real end-to-end device day and recovery test → use it for seven actual days → prioritize improvements from the observed friction → widen the pilot.

During those seven days record five things: completion, real minutes, grading disagreements, interruptions/fallbacks and whether you wanted to return. Also inspect generation latency and spend in the existing pilot tools. The pilot is successful enough to expand when the daily loop is dependable, saved progress survives interruptions, corrections are trustworthy, and the difficulty feels appropriate. A feature count or simulated pass rate cannot substitute for those observations.
