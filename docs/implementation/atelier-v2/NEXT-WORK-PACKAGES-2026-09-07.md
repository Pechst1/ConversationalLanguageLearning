# Next work packages — 2026-09-07

State assessment of the whole app as of the evening of 2026-09-07, and the packages that
follow from it. Written from the code and the working tree, not from earlier status
claims; every "verified" line below was re-run today. Supersedes the "next" sections of
[STATUS.md](STATUS.md), [NEXT-STEPS-REVIEW.md](NEXT-STEPS-REVIEW.md) and
`docs/design-overhaul-2026-08-31.md` §"Still open" where they disagree.

## 1. Where the app stands

### Verified today

| Check | Result |
|---|---|
| Frontend `type-check`, `lint` | Pass |
| Nine node suites in CI (`atelier-next`, `journey`, `recovery`, `reader`, `atelier-ui`, `api-host`, `graphic-novel-images`, `native-env`, `story-model`) | Pass |
| `web-frontend/lib/seance-feedback.test.js` (new, Codex, not in `package.json` or CI) | Pass, run by hand |
| Backend `pytest` on the working tree | See §1.4 |

### 1.1 What a real learner actually sees

Every flag that matters is **off** for real users, in `.env` and in `render.yaml`:

- `ATELIER_DAILY_JOURNEY_ENABLED=false`, `ATELIER_DAILY_JOURNEY_COHORT=""`.
- `ATELIER_STORY_ENGINE_ENABLED=true`, but `living_story.py:370` also requires
  `journey_enabled_for(user)`, so it is unreachable.
- `GRAPHIC_NOVEL_IMAGE_GENERATION_ENABLED=false` in production (deterministic SVG panels).

So the learner's daily loop is still the **legacy** one: Home (av2) → legacy exercise
Séance (`SessionView` on the new Épreuve chrome, plus Codex's 2026-09-07 rework) →
legacy serial Feuilleton scenes → Studio → Courrier → Cahier. The entire Atelier V2
stack built between 2026-09-05 and 09-07 (daily journey WP-02…12, living-story engine
WP-14, immersive reader) is invisible to every learner. That is by design (default-off),
but it means three weeks of engineering has produced zero learner-facing change on the
core loop, and the two Séances are now diverging:

| | Legacy Séance (shipping) | V2 daily journey (dark) |
|---|---|---|
| Shape | Grammar-concept drills: notice → build → trap → repair → say → reply | Five-minute scene: read → 0–2 recalls → respond → resolution |
| Story | None (character decoration only) | Continuing personal world, commitments, chapters |
| Grading | Codex 09-07: AI assessment required, unassessed on failure | Grounded outcome + WP-05 evidence, R-1/R-2 fixed |
| Owner | Codex session | Claude sessions |
| Where it lives | `app/services/atelier.py` (6,333 lines), `pages/atelier.tsx` (6,872 lines) | `daily_journey.py`, `living_story.py`, `components/atelier-v2/journey` |

Both are good work. Both cannot be "the" daily séance. **Decision D-0 in §2 is the
first thing to settle.**

### 1.2 Uncommitted working tree (Codex's Séance rework, 2026-09-07)

Nine modified + seven new files, all Codex's, last touched 16:06 today. Contents per
[SEANCE-REWORK-2026-09-07.md](SEANCE-REWORK-2026-09-07.md): honest unassessed state,
whole-answer grading, 54-lesson curriculum (`seance_curriculum.py`,
`seance_challenges.txt`), repair → delayed-retrieval loop, frontend verdicts from the
assessment (`lib/seance-feedback.ts`). It also changes production defaults in
`app/config.py`: correction model `gpt-5-nano → gpt-5-mini`, timeout 25 → 60 s, output
cap 900 → 5,000 tokens, reasoning `minimal → low`. That is a cost and latency change on
the most-used endpoint and has no telemetry line item yet.

Do not `git checkout`/`stash` anything here; see the shared-checkout rule in
[BASELINE.md](BASELINE.md).

### 1.3 Open items carried forward (all still true today)

**Engine (WP-14):** the living-story-v2 confirmation run accepted 9/13 days but every
day was at Le Mistral with Lila in one chapter; real 14-day variety is not demonstrated.
The critic call is ~25 % of scene cost and caught nothing the deterministic guards did
not. Lila's register (`putain` to an A1 learner) is an unmade product decision. Panels
reuse location art (`setting_reference`); no per-panel illustration, no visual
continuity. Cost accounting for the engine is diagnostic usage metadata, not a ledger.

**Release engineering:** no `docs/implementation/atelier-v2/ROLLOUT.md` (WP-13 §6). No
`PrivacyInfo.xcprivacy` in `web-frontend/ios/App/App/` (ITMS-91053 bounce). No
`DEVELOPMENT_TEAM` in the Xcode project. Icon set is one `AppIcon-512@2x.png`. Crash
reporting is still first-party `window.onerror` only. Backend never deployed to Render.
`.env` still says `TTS_PROVIDER=elevenlabs` (402s; falls back to OpenAI).

**Frontend debt:** eleven pages are still off the av2 system and every one of them is
still linked from somewhere: `achievements`, `almanac`, `audio-session` (Studio, linked
from `atelier.tsx:1344`), `bibliotheque`, `daily-practice`, `dashboard`, `practice`,
`progress`, `sessions`, `stories`, `serial/episode`. Studio is the only one a learner is
sent to on purpose. `pages/atelier.tsx` is 6,872 lines and hosts both Séances.

**Language and data:** review-card visual-cue badge and mic/transcription toasts are
English; ~30 deterministic corrector strings are English-only; the authored fallback
erratum prose is English; POS heuristic is wrong for ~11 % of -er/-ir words; the Anki
deck has no real English glosses.

**Validation never done:** any physical device or simulator lifecycle run of V2; the
five-learner study (protocol ready in QA-REPORT §11); the journey conversation live-model
review (QA-REPORT §9; the *engine* prose was reviewed, the authored conversation path
was not).

### 1.4 Backend suite

`pytest` on the working tree (repo `.venv`, Python 3.11), run 2026-09-07 evening:
**1,547 passed, 1 xfail, 0 failed**, exit 0. The xfail is the authored-path D-1b marker;
the engine path replaces it. Codex's `tests/test_seance_contract.py` is included.

## 2. The decision the packages hinge on

**D-0 — one daily Séance.** Recommendation: **the V2 daily journey with the living-story
engine becomes the daily Séance for the pilot cohort, and the legacy exercise Séance
becomes the explicit "Plus de pratique" grammar activity** (which is exactly what
WORK-PACKAGES WP-04 §5 already reserves: "More practice is an explicit new activity").

Why this way round and not the other:

- The journey is where the story, the commitments, the honest evidence rubric and the
  reader all live, and it is the product concept the owner accepted in CONTINUOUS-STORY.
- Codex's rework makes the legacy Séance a very good *drill* loop, keyed by grammar
  concept. That is what a learner wants when they choose a concept from the Cahier, not
  what the daily five minutes should be.
- Keeping both as "daily" means two recaps, two streak sources, two correction policies
  and two model budgets on one screen.

The alternative (legacy Séance stays daily, engine only inside the Feuilleton) is
cheaper to ship but throws away the five-minute planner and the evidence rubric. If the
owner picks it, WP-16 changes shape and WP-17 shrinks; everything else stands.

## 3. Work packages

Numbering continues from WP-14. Each package names an owner role, the files it may
touch, and an acceptance line that an agent can check. Estimates are agent-days.

### WP-15 — Land the working tree and wire Codex's Séance into the checks (0.5 d)

**Owner:** integration owner. **Depends on:** nothing. **Do first.**

1. Review Codex's diff file by file, then commit in two passes: curriculum + backend
   grading, then frontend + tests. Do not include `.env`.
2. Add `"test:seance": "node --test lib/seance-feedback.test.js"` to `package.json` and
   to the CI node block; confirm `tests/test_seance_contract.py` runs in CI's pytest.
3. Record the config default change (gpt-5-mini, 5,000 tokens, 60 s) in
   `render.yaml` explicitly rather than by inheritance, and add its cost to
   `scripts/pilot_digest.py` as a line item. Attach the Séance rework's live-check
   numbers to STATUS.
4. Owner action: set `TTS_PROVIDER=openai` in `.env`; restart the backend on 8010.

**Acceptance:** `git status` clean apart from ignored files; CI green including the new
suite; the config change is visible in the deploy manifest and the digest.

### WP-16 — Converge on one daily Séance (D-0) (3 d)

**Owner:** daily-experience frontend lead + journey backend owner. **Depends on:** WP-15,
D-0 decided.

1. `resolveRecommendedNext` and `HomeScreen`: with the journey enabled, the one action
   is the journey; the legacy session is reachable only as "Plus de pratique" from Home's
   Séance tile secondary line and from a Cahier concept ("Composer à l'Atelier" already
   seats the concept).
2. Rename and scope the legacy loop: it starts from a chosen concept or from the
   errata queue, never from "today". Its recap feeds the same `LearningSession` /
   evidence records as the journey (WP-05 adapters), so streak, minutes, Le Relevé and
   capabilities have one source. Verify no double credit when a word appears in both.
3. One correction policy: the journey's foreground rule (one relevant correction,
   detailed view optional) applies to the drill loop's open-production rounds; Codex's
   "unassessed on provider failure" state becomes the shared infrastructure-failure
   state for both.
4. Split `pages/atelier.tsx`: journey shell, legacy session shell, today view, each its
   own file; no behaviour change, source-scanning backend tests re-pinned.
5. Backend: `today()` envelope gains `practice_href` and the journey recap gains a
   "continue practising this" pointer into the drill loop for the scene's targets.

**Acceptance:** a cohort learner opens the app, sees one primary action, finishes the
journey in ≤ 5 min estimated, and can then choose extra practice that lands on Codex's
loop for a concept the journey surfaced; Le Relevé shows both; streak increments once.
Legacy learners (flag off) see exactly today's behaviour.

### WP-17 — WP-14G: real variety on living-story-v2 (2 d + ≈ US$1 in calls)

**Owner:** story-engine agent; independent QA accepts. **Depends on:** WP-15. Runs in
parallel with WP-16.

1. Paid run: `scripts/longitudinal_story_review.py` 14 days × A1 and A2 on v2, owner
   consent recorded, cost ceiling set beforehand (`--max-requests`).
2. Variety fixes the run will need: rotate location and character explicitly in the
   director context (world bible has more than Le Mistral and Lila); chapter turnover
   after N resolved commitments; premise-overlap check per *location + character +
   objective*, not only content words.
3. Critic decision: A/B ten scenes with and without the critic call; keep it only if it
   rejects something the deterministic guards miss. Record the answer either way.
4. Register: apply the owner's decision on Lila's *putain* (recommend: strip below B1
   via the existing level guidance); align narration *vous* with dialogue *tu*.
5. Cost: write one row per scene into the pilot cost ledger (`PilotEvent.cost_usd`)
   from the usage metadata already collected, so the weekly guardrail
   (`PILOT_SERIAL_WEEKLY_COST_GUARDRAIL_USD`) actually covers the engine.

**Acceptance:** ≥ 11/14 accepted days at each level; ≥ 3 distinct locations and ≥ 3
characters across the run; ≥ 2 chapters; median request < 12 s; cost per learner-day
recorded in the ledger; report in ENGINE-IMPLEMENTATION.md with the same table format as
14F.

### WP-18 — Pilot enablement runbook and first deploy (WP-13, scoped) (2 d)

**Owner:** integration owner. **Depends on:** WP-16, WP-17. Owner performs the deploy.

1. Write `ROLLOUT.md`: exact keys (`ATELIER_DAILY_JOURNEY_ENABLED`, `_COHORT`,
   `ATELIER_STORY_ENGINE_ENABLED`, `ATELIER_STORY_MAX_ATTEMPTS`, image flag, correction
   model), health queries, cost queries, drain procedure, rollback (creation off, active
   journeys keep draining), who flips what.
2. Prove the drain on a disposable PostgreSQL: cohort learner mid-journey, flag off,
   learner finishes; flag back on, next day resumes the same thread.
3. Render deploy of the backend (owner runs it; agent prepares and checks `/health`,
   `/ready`, migration to head, `pilot_digest` for the first day).
4. Cohort: owner's own account first; then the five study accounts (WP-22).

**Acceptance:** the owner can enable and disable the pilot from the runbook alone; the
first digest shows engine cost and journey completion for the owner's account.

### WP-19 — Native release readiness and lifecycle QA (2 d)

**Owner:** resilience/native agent. **Depends on:** WP-15; can run alongside WP-16/17.

1. `PrivacyInfo.xcprivacy` in `web-frontend/ios/App/App/` with the actual API
   categories used (UserDefaults, file timestamp, system boot time via Capacitor).
2. `DEVELOPMENT_TEAM` via `xcconfig` read from env (never committed); full AppIcon set
   generated from the 1024 source.
3. Crash reporting decision: keep first-party `client_crash` and prove it in a private
   build (checklist §2), or add Sentry. Recommend first-party until there are learners.
4. Push for the daily journey: "Votre scène du jour est prête" at the learner's
   morning slot, deep link `/atelier`; reuse `serial_notifications.py` scheduling.
5. Simulator walk of V2 with the iOS Simulator tool: kill mid-draft, kill after attempt
   before receipt, airplane cold start, keyboard over the response field, mic permission
   denied → text; 390 pt and large text. This is the WP-10 recheck WORK-PACKAGES
   requires after the visual migration.

**Acceptance:** `bundle exec fastlane ios archive` succeeds locally; every WP-10
acceptance line reproduced on the simulator with screenshots in
`docs/mobile-visual-checks/`; no new "pending" for a gate that can run locally.

### WP-20 — Assembled V2 browser QA and legacy-page disposition (2 d)

**Owner:** independent QA agent (WP-12 final). **Depends on:** WP-16.

1. Walk every authenticated route on the av2 system at 320/390/768, light and dark,
   large text, reduced motion, keyboard only; log defects with the D-n format.
2. Disposition list for the eleven off-system pages: delete (`practice`,
   `daily-practice`, `sessions`, `dashboard`, `stories`, `achievements`, `almanac`,
   `progress`), migrate (`audio-session` = Studio, `bibliotheque`, `serial/episode`).
   Remove the deleted pages and every inbound link in the same change; keep the APIs.
3. Sweep the remaining neo-brutal shadows and legacy resets that only those pages used.

**Acceptance:** zero pages outside `av2` reachable from the shell; `next build` route
count drops accordingly; QA report separates automated, browser, device and learner
evidence per WP-12.

### WP-21 — Language and data debt (1.5 d)

**Owner:** content agent. **Depends on:** nothing; fits between other packages.

1. Localize the ~30 English corrector strings, the fallback erratum prose, the visual-cue
   badge labels and the mic/transcription toasts across en/de/fr through the existing
   copy resolver; re-pin `test_frontend_vocabulary_biography`.
2. POS: replace the -er/-ir heuristic with the spaCy tag where available and a
   curated override file for the ~11 % known-wrong set; add a report script.
3. Anki deck English glosses: bounded LLM backfill (`scripts/backfill_anki_examples.py`
   pattern), owner consent and cost ceiling recorded.

**Acceptance:** `grep` for the listed English strings in learner-facing code returns
none; POS audit script shows < 2 % mismatch on the sample; deck rows have distinct
English and German columns.

### WP-22 — Five-learner study (owner-run, 1 week elapsed)

**Owner:** the owner, with the QA agent preparing accounts and reading results.
**Depends on:** WP-18 (cohort live), WP-19 (a build to hand out).

Run QA-REPORT §11 exactly: two true beginners, seeded due words, consent script,
tasks read verbatim. Measure the WP-12 first-action time, completion without skips,
voluntary retry rate, and delayed-retrieval accuracy on day 2. Feed findings into a
short defect list; do not start WP-23 before this exists.

### WP-23 — Generated panel illustrations with continuity (deferred; ≥ 4 d + storage)

Product bet, not pilot-blocking: durable S3-compatible storage, per-panel image
generation with cast/location reference sheets, continuity checks, cost ledger. Start
only if WP-22 says the `setting_reference` panels hurt engagement.

## 4. Sequence

```
WP-15 ──► D-0 ──► WP-16 ──┐
              ├──► WP-17 ──┼──► WP-18 ──► WP-22 ──► (WP-23)
              └──► WP-19 ──┘        ▲
                    WP-20 ──────────┘  (after WP-16)
WP-21 anywhere in the gaps
```

Three concurrent agents at most, leases per STATUS.md; the Codex session keeps
`app/services/atelier.py`, `grammar_feedback.py`, `seance_curriculum.py` and
`pages/atelier.tsx`'s legacy branch until WP-16 §4 splits the file, at which point the
split is negotiated with Codex first.

## 5. What this plan does not do

- It does not enable anything in production. Every flag stays as it is until WP-18's
  runbook exists and the owner flips it.
- It does not re-open the WON'T-DO list (pronunciation, mascots, social features).
- It does not schedule the delayed-episode / season-3 serial issues separately: with
  D-0 as recommended, the engine replaces authored serial episodes for cohort learners,
  and the legacy serial keeps its 2026-08-31 fixes for everyone else.
