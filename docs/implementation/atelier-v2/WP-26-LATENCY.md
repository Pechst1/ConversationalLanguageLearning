# WP-26 — Latency as a product feature

**Landed:** 2026-09-10. **Branch:** `codex/serial-season-engine-production`.

## The problem

The daily journey promises five minutes. The measured draft p50 was **20–22 s**
against a 25 s `REQUEST_TIMEOUT_SECONDS` (STATUS, commit `437cb01`). On a
five-minute session a twenty-second spinner is not a detail of the experience —
it is roughly seven percent of it, spent watching nothing, before the learner
has read a single word of French. And a p50 that close to the timeout means the
tail is not slow, it is *gone*.

The fix is not a faster prompt. A scene the learner waits for is a scene that
could have been generated before they arrived.

## What shipped

### 1. Ahead-of-time prefetch — `app/services/journey_latency.py`

A bounded Celery beat (`app/tasks/journey_prefetch.py`, scheduled 03:20 and
15:20 Europe/Berlin) generates the next scene for active pilot learners.

The **cache key** is the CONTINUOUS-STORY WP-14C rule in full — *"key generation
caches by the relevant story revision, scene identity, learner context and
prompt version. A cache keyed only by user and exercise family is
insufficient."*

| Component | Source |
|---|---|
| story revision | `living_story.story_revision()` — the same `_fingerprint` `_lock_context` refuses to publish against once it has moved |
| scene identity | the offer the day would resolve to (`story_next`) |
| learner context | level band, control language, address preference, input mode |
| prompt version | `living_story.VERSION` plus `ATELIER_STORY_MAX_ATTEMPTS` |

Everything in the key is cheap to recompute: the key costs one indexed thread
read and **never** a provider call.

**What the beat refuses before it pays.** `ATELIER_JOURNEY_PREFETCH_ENABLED`
off; `ATELIER_STORY_ENGINE_ENABLED` off (the authored path is a catalogue read —
there is no latency to remove); the learner outside `ATELIER_DAILY_JOURNEY_COHORT`
(`journey_enabled_for`, the same server-authoritative check the journey itself
uses); an open or already-prepared day; a live cache entry under the same key;
and a learner already at `PILOT_SERIAL_WEEKLY_COST_GUARDRAIL_USD`. The beat is
additionally bounded to `ATELIER_JOURNEY_PREFETCH_MAX_LEARNERS` *paid* calls per
run — candidates it refuses cheaply do not consume the budget.

**Idempotency is the key's job, not a lock's.** A second run inside the same
story revision and prompt version finds a live entry and returns `cached`,
having paid nothing. The tests pin `generated["count"] == 1` across three runs.

**Storage** is the existing `pilot_events` ledger — no migration, and append-only
rows are the safe shape under the concurrent writers this checkout has. Three
event types: `journey_scene_prefetched` (`entity_id` = cache key, payload carries
the serialized brief), `journey_scene_prefetch_consumed` and
`journey_scene_prefetch_discarded` (both keyed by the prefetch row's id).

**Money never escapes the guardrail.** A consumed prefetch is billed exactly as
before, by `bind_journey`'s `journey_story_scene_cost` row. A prefetch nobody
consumed — stale, superseded, unreadable or expired — is billed on its *discard*
row instead, so an ahead-of-time call that turned out to be wasted is still
visible to the weekly rollup rather than lost with the failed attempt.

### 2. The hot path — `daily_journey._run_generation`

Before asking the content adapter for anything, `take_prefetched_scene` is
consulted. A valid warm scene is served as-is and the adapter is **never**
called; the test asserts `adapter_calls["count"] == 0`. Anything whose cache key
no longer matches the current one is discarded inside that call rather than
handed back — *"never serve a scene whose preconditions changed"* is enforced at
serve time, not at write time, so a story that moved overnight cannot be served a
stale morning.

The consume row is added to the **caller's** transaction. A create that later
rolls back returns the scene to the cache untouched rather than burning it. A
scene is served at most once: the second `take_prefetched_scene` returns `None`.

`_run_generation` still bails out early when `journey.steps` exists, so a
generation retry re-serves the persisted plan and nothing is ever generated
twice.

### 3. Telemetry and the release gate

`measure_phase` wraps the three requests the learner actually waits on —
`create_journey`/`retry_journey` (**draft**), `submit_attempt` (**respond**),
`finish` (**recap**) — and persists one `journey_latency` row each with wall
seconds, outcome, and (for the draft) `prefetch_hit`. Failures are recorded as
`outcome: "failed"` and re-raised unchanged. Telemetry never breaks a request:
every write is wrapped, and a failed write rolls back only itself.

The gate constants live in `journey_latency`:

```
DRAFT_P95_GATE_SECONDS   = 8.0    # with prefetch working
RESPOND_P95_GATE_SECONDS = 20.0   # still pays a provider call
RECAP_P95_GATE_SECONDS   = 3.0    # assembled from persisted state, never generated
PREFETCH_HIT_RATE_GATE   = 0.7
GATE_MIN_SAMPLES         = 10
```

`evaluate_gate()` returns `pass`, `fail` or `insufficient_data`. **Thin data is
never a pass** — a gate that green-lights on three samples is not a gate.

Read it with:

```bash
python scripts/pilot_digest.py --day 2026-09-10 --latency-only
python scripts/pilot_digest.py --day 2026-09-10 --gate    # exit 1 unless it passes
```

The full digest prints the same section at the end of every run.

### 4. Frontend — no spinner for a warm draft, no dead end for a lost one

`runWithWaitHint` in `journey-requests.ts`, used by `start` and `retryGeneration`
in `useDailyJourney`:

* the wait state is **delayed** by `WAIT_HINT_DELAY_MS` (400 ms). A prefetched
  draft answers in tens of milliseconds and therefore never enters it — no
  spinner, no 40 ms stutter. A cold draft still gets the existing honest wait
  copy within half a second.
* every mutation is bounded by `MUTATION_DEADLINE_MS` (60 s — above the server's
  75 s operation budget's useful window, below forever). Crossing it produces a
  `JourneyTimeoutError`, which `planFailure` routes to
  `{kind: 'error', retryable: true}` — a retryable state with a button, never a
  verdict and never a permanent spinner. The mutation id is unchanged, so the
  server's receipt de-duplicates the retry.
* `onWait(false)` is guaranteed on every exit — resolve, reject, timeout.

The controller exposes `waiting` alongside `busy`. `busy && !waiting` *is* the
warm path. `JourneySteps.tsx` and `HomeScreen.tsx` were not touched; the step UI
can adopt `waiting` when its owner chooses.

## Settings added (all additive, all defaulted safe)

| Setting | Default | Meaning |
|---|---|---|
| `ATELIER_JOURNEY_PREFETCH_ENABLED` | `True` | Off means the previous behaviour exactly |
| `ATELIER_JOURNEY_PREFETCH_TTL_SECONDS` | `93600` (26 h) | Covers a late session after an overnight run |
| `ATELIER_JOURNEY_PREFETCH_MAX_LEARNERS` | `25` | Paid calls per beat run |
| `ATELIER_JOURNEY_PREFETCH_ACTIVE_DAYS` | `7` | Activity window for candidacy |

## Tests

* `tests/test_journey_latency.py` — 22 tests: cache-key derivation (revision,
  prompt version, learner context, engine off), flag/cohort/engine/budget
  gating, idempotency, stale discard, superseded discard, served-exactly-once,
  expiry sweep and billing, unreadable payloads, provider-unavailable, the hot
  path through `DailyJourneyService`, telemetry rows on success and failure,
  percentiles, the hit rate, the digest line, and all three gate verdicts.
* `web-frontend/components/atelier-v2/journey/journey-latency.test.js` — 7
  tests on a hand-driven clock: no wait state for a warm draft, the hint for a
  slow one, the hint cleared on failure, the bounded timeout, the timeout's
  failure plan, the disabled deadline, and the bound itself. Wired as
  `npm run test:journey-latency` and into CI.

## Open items

1. **No measured production numbers yet.** Everything above is structural. The
   gate exists precisely so the first real pilot day answers the question rather
   than an estimate. Run `--gate` after a day with ≥10 drafts.
2. **The prefetch is a per-learner single slot.** One scene ahead, not a queue.
   Enough for a daily session; a learner who does two journeys in a day pays for
   the second as before.
3. **`today()` does not yet advertise warmth.** The envelope has no
   `available.is_warm` field, so the client learns the draft was warm by it being
   fast rather than by being told. Adding it means touching
   `schemas/daily_journey.py`, which is another agent's file this week.
4. **The activity window reads `pilot_events` with a `LIKE 'journey_%'` scan.**
   Fine at pilot size; it wants a proper index or a last-seen column before the
   cohort grows past a few hundred.
5. **Respond and recap are measured but not optimised.** The reply turn still
   pays a full provider call. If its p95 lands near the 20 s gate, the same
   prefetch trick does not apply — the learner's answer is the input — and the
   next lever is streaming, not caching.
