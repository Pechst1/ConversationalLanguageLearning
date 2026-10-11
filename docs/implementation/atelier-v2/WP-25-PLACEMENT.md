# WP-25 — Honest placement in the first five minutes

Handoff for the next owner. Written from the code as landed on
`codex/serial-season-engine-production`, 2026-09-10.

## 1. The problem this closes

`app/services/cefr_progress.py` estimates a level from what the app has
**verified**: mastered words, mastered concepts, recent score, recent error
rate. A learner who signed up ten minutes ago has verified nothing, so the
threshold walk returns `A1.1` for everybody. The service already knew this and
worked around it — `DECLARED_LEVEL_EVIDENCE_ATTEMPTS = 40` lets the learner's
own signup dropdown act as a floor until forty in-app attempts exist.

That workaround is honest about its own uncertainty (`estimate_source:
"declared"`, `breakdown.status: "unverified"`) and still serves the wrong
material for roughly the first week, to exactly the learners most likely to
leave. There was no placement test of any kind.

## 2. What landed

### Backend

| File | What it is |
|---|---|
| `app/db/models/placement.py` | `placement_sessions`: one row per placement, holding the turns and the estimate |
| `alembic/versions/b8e8c24ffddf_add_placement_sessions.py` | Additive: one new table, no column on any existing one. Head was `a3b4c5d6e7f8` |
| `app/services/placement.py` | The ladder, the estimate math, the paid grading call, the cost row, and the prior the CEFR service reads |
| `app/api/v1/endpoints/placement.py` | `/api/v1/placement/{state,start,{id}/respond,{id}/finish,skip}` |
| `app/services/cefr_progress.py` | `placement_prior()` and a placement-aware `_estimate_with_declaration` |
| `app/schemas/progress.py` | `estimate_source`, `declared_level`, `placement` on `CEFRProgressResponse` |
| `scripts/pilot_digest.py` | `format_placement_line` — calls, learners, tokens, cost, cost per placed learner |

### Frontend

| File | What it is |
|---|---|
| `web-frontend/pages/placement.tsx` | The screen: offer → question ×4–6 → result, or «Niveau non évalué» |
| `web-frontend/pages/auth/signup.tsx` | The hand-off: a learner with no destination of their own lands on `/placement` after their first sign-in |
| `web-frontend/pages/settings.tsx` | «Bilan de niveau · Refaire le bilan» → `/placement?rerun=1` |
| `web-frontend/services/api.ts` | Five methods and the `PlacementEnvelope` / `PlacementPrior` types |

## 3. How the placement works

**The ladder.** Seven rungs, `A1.1 … B2.1`, one production prompt each
(`PROMPT_BANK`). It stops at B2.1 on purpose: no single paragraph in this bank
distinguishes B2.1 from B2.2, and pretending otherwise is the dishonesty the
package exists to remove.

The opening rung is **one below** the learner's declared level, floored at A1.2.
Failing question one is a demoralising first minute and the ladder climbs fast,
so the headroom costs at most one turn.

After each graded turn: `score ≥ 3.0` climbs a rung, `score ≤ 1.5` drops one,
anything between holds. **An ungraded turn holds the band in both directions** —
a missing measurement is not a bad one and must never demote a learner.

**Stopping.** Minimum four turns, maximum six, and it stops early at four or
five once confidence reaches `CONFIDENCE_TO_STOP = 0.7`. Six turns is the
five-minute promise at roughly 40 s of reading and writing per turn.

**The estimate.** Each graded turn yields a ladder position: the prompt's own
band, moved by the score (`+1` at ≥3.5, `0` at ≥2.5, `−0.5` at ≥1.5, `−1.5`
below), then averaged with the grader's independent read of the response
(`demonstrated_band`) when it gave one — so a learner writing far above the rung
they happen to be on is not capped by it. Positions are combined with weights
`1, 2, 3, …`: the ladder converges, so the last rung is the better evidence.

**Confidence is agreement, not volume.** `0.34 + 0.11·n − 0.20·spread`, clamped
to `[0.1, 0.92]`, where spread is the population standard deviation of the
positions. Four turns that agree beat six that do not.

**Dimensions.** `range`, `accuracy`, `coherence`, `task`, each 0–4, averaged
across graded turns and carried in the result with French labels. Fluency and
pronunciation are absent because a written turn cannot evidence them.

## 4. The honesty rules, and where they are enforced

1. **A provider that does not answer yields no level.** `_grade` returns `None`
   on a provider error, an unparseable body, or a body that fails
   `normalize_grading`; `estimate_from_turns` with zero gradings returns
   `status="unassessed"`, `level=None`. The session is stored that way and the
   screen says «Niveau non évalué».
2. **An unusable grading raises, it does not score zero.** A zero would walk the
   ladder *down* on a provider hiccup and end the placement a band too low.
3. **A low-confidence placement is not a prior.** `latest_placement_prior`
   returns `None` below `MIN_PRIOR_CONFIDENCE = 0.45`; the declaration stands.
4. **A prior is a floor, never a ceiling.** Same rule the declaration always
   had: it applies only when it sits above the measurement.
5. **A placement is not in-app verification.** `breakdown.status` stays
   `"unverified"` for `estimate_source == "placement"` — the learner's French was
   measured, their in-app counters are still zero, and the Cahier must not draw
   them as a verified level.

## 5. Resumability and idempotence

`start()` returns the open session rather than creating a second one, so two
taps produce one placement and a learner who closed the app resumes with their
graded turns intact. `respond()` takes a `turn_index`; an index that already
exists returns the session untouched, so a retried POST makes **no paid call and
writes no cost row**. Only `start(restart=True)` — the Réglages re-run — opens a
second session, and it marks the old one `abandoned`.

## 6. Cost

One `PilotEvent` of type `placement_grading` per real grading call, priced from
the provider's own usage metadata, written through the caller's transaction and
never committed there, with every telemetry failure swallowed — the policy
`atelier_correction_cost` established. A placement is at most six calls, once per
learner, on `ATELIER_CORRECTION_LLM_MODEL`.

`scripts/pilot_digest.py` prints `Placements: N gradings · N learner(s) · N
tokens · $X · $Y/learner · model`. Cost **per placed learner** is the number that
decides whether this is affordable at cohort scale.

## 7. Tests

| File | Covers |
|---|---|
| `tests/test_placement.py` | ladder escalation/hold/de-escalation, the ungraded-turn hold, estimate weighting, confidence-vs-agreement, the four-to-six turn budget, grading validation, off-task handling, provider-failure honesty, resumability, idempotence, cost rows, and the CEFR prior handover |
| `tests/test_placement_api.py` | the five routes end to end with a fake grader: auth on every route, the offer made once, one prompt at a time, the level reaching `GET /progress/cefr` as `"placement"`, a replayed response neither re-grading nor re-billing, the Réglages re-run, the unassessed screen, and one learner's session being invisible to another |
| `tests/test_placement_onboarding_surface.py` | source-scanning: the signup redirect, the route's absence from `PUBLIC_PATHNAMES`, the skip and what it costs, the unassessed copy, the estimate framing, the Réglages entry, av2 + French, one primary action per state, and the client sending `turn_index` |

## 8. Open items

* **No live-model run.** Every test uses a fake grader. The prompt bank and the
  grading system prompt have never been judged by a real model against real
  learner French, so the *calibration* of the ladder is unproven — the mechanism
  is proven, the numbers are not. This is the same gate the journey conversation
  waited on, and it needs the same kind of bounded paid run.
* **`MIN_PRIOR_CONFIDENCE = 0.45` and `CONFIDENCE_TO_STOP = 0.7` are reasoned,
  not fitted.** They should be revisited once real placements exist.
* **No spoken turn.** The placement is written only, so it measures nothing about
  speaking. The dimensions say so; the copy does not yet.
* **Home does not surface it.** `GET /progress/cefr` carries
  `estimate_source: "placement"` and the `placement` block, and Le Relevé already
  branches on `estimate_source === 'declared'`. Extending that branch to say
  «niveau estimé (placement)» with its date is a one-line change in
  `components/releve/Releve.tsx`, which belongs to another lease and was left
  alone.
* **The offer is made once, and only at signup.** An existing learner is never
  offered it; they must find it in Réglages. If the pilot cohort predates this
  package, that is everybody.
