# WP-28 — the hooks four packages owed each other

2026-09-10. WP-24, WP-25, WP-26 and WP-27 landed the same week under disjoint
file leases. Each stopped at a file it did not own and wrote down what it could
not wire. This package is those seams, and nothing else: no new capability, no
new prompt surface, no new paid call.

Four inheritances, and what each one is now.

| | Left as | Now |
|---|---|---|
| **WP-24 §5** | The planner could rank a learner's due errata, stamp the plan with them and produce a because payload. Nothing called it, so Home's French line was unreachable code | `daily_journey` reads the errata, plans with them, stores the payload with the plan, and `GET /atelier/today` serves it. Home prints it |
| **WP-24 §5 (quality half)** | The director never learned what the learner gets wrong, so a scene targeting an erratum only exercised it by luck | The erratum's label, «faux → juste» and stored explanation are in the scene-draft context |
| **WP-26 open item 3** | `today()` did not advertise warmth; the client learned a draft was prefetched by it being fast | `TodayEnvelope.is_warm`, read by `useDailyJourney` |
| **WP-27 §4** | The controller kept a whole second microphone — `VoiceState`, `startRecording`, `stopRecording`, `resetVoice` and their recorder refs — that nothing called | Gone. The respond step's `useVoiceAnswer` is the only capture path |
| **WP-25 open item** | Le Relevé branched on `estimate_source === 'declared'` only, so a placement was printed in the words of a self-declaration | «Niveau estimé (placement)», with its date |

## 1. The because-line, end to end

```
record_erratum → errata_targets_for_user → plan_journey(errata_targets=…)
              → plan_because → journey.plan_selection["because"]
              → TodayEnvelope.because → journeyBecause() → <HomeScreen because={…}>
```

Three decisions inside that chain are worth stating, because each one had a
cheaper wrong answer:

* **The payload is persisted with the plan, not recomputed on read.** The line
  claims something about *the scene the learner has* — that it reprises a
  mistake. Recomputing it on every `GET /today` would let a mistake recorded
  *after* the scene was planned claim credit for a scene that never targeted
  it. `test_the_because_line_is_read_from_the_plan_not_recomputed_from_the_queue`
  pins that.
* **It is offered only where it is true.** With no journey there is no plan, so
  there is no line: the envelope's `because` is `null` until today's scene
  exists. A prospective "today's scene will pick up…" would be a promise the
  planner has not yet made.
* **The seam stays a seam.** `plan_because` and `merge_errata_candidates` are
  resolved through the planner *adapter*, the way `PlanUnavailable` already
  was; the state machine gains no domain import. A planner without them simply
  produces no line.

Reading the errata queue can fail — it is a database read on the day's hot
path — and when it does, the day still happens: `_errata_targets` logs and
returns `[]`, which is byte-for-byte the pre-WP-24 plan.

### The wire

`TodayEnvelope` gains one nullable object. `contract_version` is unchanged, as
`practice_href` was before it.

```json
"because": { "kind": "erratum", "reason": "erratum:2f9c…",
             "label": "l’accord du participe passé",
             "example": "une homme → un homme" }
```

Structured, never a sentence: `kind` is the only field a renderer may branch
on, and an unknown kind prints nothing rather than inventing French for it. The
payload is validated against `JourneyBecause` at *write* time, so a malformed
one is dropped once instead of 500-ing every subsequent read.

## 2. The director is told what the learner gets wrong

`living_story.errata_context()` gives the scene draft three fields per due
mistake — label, «faux → juste», why — and the DIRECTOR prompt asks for a
situation whose objective genuinely *needs* the repaired form, with four
explicit refusals: never quote the learner's error, never name the rule, never
correct anyone, never let a character allude to the learner having got
something wrong. An erratum no natural situation needs is ignored rather than
forced.

It is added in `generate_scene`, not in `story_context`, because `_turn_payload`
builds the actor's context from the same function. **The actor is never told
what the learner is expected to get wrong**: it has to grade what was actually
said, and a grader primed with an expected error is not a grader.
`test_the_story_director_is_told_what_the_learner_gets_wrong` pins the absence.

`VERSION` is deliberately **not** bumped: this is an additive prompt clause, the
same call the 2026-09-07 register fixes made ("revision stays living-story-v2"),
and bumping it would re-date every episode every learner has.

## 3. The prefetch key carries the errata

WP-14C keys a prefetched scene on story revision + scene identity + **learner
context** + prompt version. The moment the director drafts *for* a learner's
mistakes, those mistakes are learner context — so `scene_cache_key` now includes
the due errata's ids.

Without it the failure is quiet and exactly backwards: a learner who repairs a
mistake overnight is served, the next morning, the scene generated to make them
repeat it. Ids only, sorted — the ranking's ordering moves with the clock, its
membership does not, so the key is stable while the target set is
(`test_the_prefetch_key_changes_when_the_errata_targets_change`).

The read is inside the existing fail-closed `try`: a queue that cannot be read
returns `None`, which callers already treat as "no prefetch, generate as
before". Failing *open* would have served a scene whose preconditions were
unknown.

## 4. Warmth is told, not timed

`TodayEnvelope.is_warm` is one indexed read of the pilot ledger
(`has_live_prefetch`) on a route that must never pay for generation. It is
`False` whenever today already has a journey: the field describes the draft the
learner is about to ask for, and there isn't one.

`useDailyJourney` exposes `warm` and uses it to pick the wait-hint delay —
`WARM_WAIT_HINT_DELAY_MS` (2 s) instead of `WAIT_HINT_DELAY_MS` (400 ms). The
copy is **delayed, never suppressed**: a warm scene whose preconditions changed
is discarded server-side and generated like any other, and that learner still
gets told what is happening rather than a silent disabled button. The old
`busy && !waiting` heuristic — warmth inferred after the fact from a fast
answer — is gone from the controller's contract.

## 5. Le Relevé names a placement

`estimate_source === 'placement'` gets its own sentence, «Niveau estimé
(placement), 10 septembre.», and joins `declared` in a single `unverified`
predicate that keeps the gauges and the forecast away — the learner's in-app
counters are still zero either way, and a gauge against an untested level reads
as "vous savez 0 mot". The declared sentence is untouched: it is still the
honest line for a learner who only ever told us.

The other CEFR surfaces (Home's edition folio, the Cahiers masthead) print the
level without claiming a source, so they needed no change.

## 6. What was already done

`tests/test_core_mobile_user_flows.py::test_public_onboarding_moves_from_minimal_account_creation_to_daily_atelier`
was reported as broken by the placement hand-off. It is not: WP-25 re-pinned it
to the new flow in `5f465ff` (signup → `/auth/signin` with
`PLACEMENT_AFTER_SIGNUP` → placement), and it passes unmodified. Nothing was
weakened; nothing needed to be.

## 7. Tests

| File | Covers |
|---|---|
| `tests/test_wp28_integration.py` (12) | the because-line from a recorded mistake to the envelope; no line without a due erratum; the line read from the plan and not the queue; the director's errata context and the actor's ignorance of it; the cache key moving with the target set and back again when one is repaired; `is_warm` true only with a live prefetch and no journey; and four source scans — the because wiring, the warmth wiring, the dead voice fields' absence, the placement label |
| `web-frontend/lib/atelier-next.test.js` (+8 assertions) | `journeyBecause`: nothing off-flag, nothing for an unknown kind, nothing without a label, and a half-recorded example that still prints |
| `web-frontend/components/atelier-v2/journey/journey-latency.test.js` (7 → 8) | a warm draft holds the hint back past the cold delay and still raises it if the draft turns cold |

**Verification.** Backend `1887 passed, 1 skipped`; twelve node suites green;
`type-check`, `lint` and `next build` clean (32 routes). **US$0.00 spent — no
model call was made.**

## 8. Open items

1. **The because-line has never been read by a learner.** Every link is pinned
   by a test and none has been walked in a browser or on the simulator.
2. **The director's errata clause is unmeasured.** Whether a scene that is
   *told* about a mistake actually elicits the repaired form more often than one
   that is not is a question for a paid A/B, not for a prompt review. The clause
   is additive and can be removed in one line if it costs variety.
3. **`is_warm` is a promise about the cache, not the wire.** A discarded key
   still means a cold generation behind a `true`. The 2 s delay is the honest
   consequence of that, and it is a guess until the first pilot day's
   `--gate` numbers exist.
4. **`GET /today` costs one more query** (`has_live_prefetch`) and journey
   creation two (the errata read, plus the errata inside the cache key). Fine at
   pilot size; the `pilot_events` `LIKE 'journey_%'` scan WP-26 flagged as
   open item 4 is the one that will hurt first.
5. **Home's because-line is only reachable through a journey.** A learner
   looking at today's scene *before* starting it is told nothing, because the
   plan does not exist yet. Saying something honest there needs a planner that
   can answer "what would today target?" without generating — which is a
   package, not a hook.
