/**
 * WP-26 — the wait, and the end of the wait.
 *
 * Same plain-node harness as `journey.test.js`. What matters here is not a
 * rendered pixel but a promise: a draft served from the server's prefetch must
 * never enter a wait state at all, a slow one must say so, and no path —
 * including a request that never answers — may leave the learner looking at a
 * spinner with no button to press.
 *
 * Run: `node components/atelier-v2/journey/journey-latency.test.js`
 */

const assert = require('node:assert/strict');
const path = require('node:path');
const Module = require('node:module');

const HERE = __dirname;
const WEB_ROOT = path.resolve(HERE, '../../..');

require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolveWithAlias(request, ...rest) {
  if (typeof request === 'string' && request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

// The transport is never exercised here; stubbing it keeps this suite free of
// the axios/auth module graph, exactly as `journey.test.js` does.
const apiPath = Module._resolveFilename('@/services/api', module, false);
require.cache[apiPath] = {
  id: apiPath,
  filename: apiPath,
  loaded: true,
  exports: { default: new Proxy({}, { get: () => () => Promise.resolve({ data: {} }) }) },
};

const {
  MUTATION_DEADLINE_MS,
  TIMEOUT_MESSAGE,
  WAIT_HINT_DELAY_MS,
  WARM_WAIT_HINT_DELAY_MS,
  isJourneyTimeout,
  planFailure,
  runMutation,
  runWithWaitHint,
  stageAttemptFeedback,
} = require('./journey-requests');
const {
  REPLY_REVEAL_MAX_MS,
  VERDICT_BEAT_MS,
  createReplySequencer,
  preparingLine,
  replyRevealMs,
  typedReply,
  typingLine,
  verdictDelayMs,
} = require('../../../lib/journey-reply-reveal');
const { journeyHeaderCaption, journeyProgress } = require('./journey-state');

// ---------------------------------------------------------------------------
// WP-76 fixtures — a three-step day, before and after the reply turn
// ---------------------------------------------------------------------------

const REPLY = 'Samedi, parfait ! Je garde deux cafés au Mistral pour nous.';

function day({ respondStatus = 'active', revision = 4 } = {}) {
  return {
    id: 'j-76',
    status: 'active',
    revision,
    current_step_id: 's-respond',
    estimated_active_seconds: 300,
    steps: [
      { id: 's-scene', kind: 'scene', status: 'completed', estimated_seconds: 75 },
      { id: 's-respond', kind: 'respond', status: respondStatus, estimated_seconds: 180 },
      { id: 's-resolution', kind: 'resolution', status: 'pending', estimated_seconds: 45 },
    ],
  };
}

function attemptResult(overrides = {}) {
  return {
    evidence_ref: 'ev-1',
    task_outcome: 'met',
    assistance_level: 'none',
    correction: null,
    character_reply_fr: REPLY,
    reply_source: 'model',
    next_turn: null,
    pending: false,
    journey: day({ respondStatus: 'completed', revision: 5 }),
    ...overrides,
  };
}

const stepOf = (position, total) => `Étape ${position} sur ${total}`;

let passed = 0;
const failures = [];

function test(name, fn) {
  try {
    const result = fn();
    if (result && typeof result.then === 'function') {
      return result.then(
        () => {
          passed += 1;
        },
        (error) => failures.push([name, error]),
      );
    }
    passed += 1;
    return Promise.resolve();
  } catch (error) {
    failures.push([name, error]);
    return Promise.resolve();
  }
}

/** A clock the test drives by hand, so nothing here waits on real time. */
function fakeClock() {
  let now = 0;
  let nextId = 1;
  const timers = new Map();
  return {
    setTimer(fn, ms) {
      const id = nextId++;
      timers.set(id, { at: now + ms, fn });
      return id;
    },
    clearTimer(id) {
      timers.delete(id);
    },
    async advance(ms) {
      now += ms;
      const due = [...timers.entries()]
        .filter(([, timer]) => timer.at <= now)
        .sort((a, b) => a[1].at - b[1].at);
      for (const [id, timer] of due) {
        timers.delete(id);
        timer.fn();
      }
      // Let every microtask the callbacks queued settle.
      await new Promise((resolve) => setImmediate(resolve));
    },
    pending: () => timers.size,
  };
}

async function main() {
  // -------------------------------------------------------------------------
  // 1. A prefetched draft shows no wait state at all
  // -------------------------------------------------------------------------

  await test('a fast (prefetched) draft never enters the wait state', async () => {
    const clock = fakeClock();
    const seen = [];
    const value = await runWithWaitHint(async () => 'warm', {
      onWait: (waiting) => seen.push(waiting),
      setTimer: clock.setTimer,
      clearTimer: clock.clearTimer,
    });
    assert.equal(value, 'warm');
    // `false` on exit is unconditional; `true` must never have been sent.
    assert.deepEqual(seen, [false]);
    assert.equal(clock.pending(), 0, 'no timer may outlive the request');
  });

  // -------------------------------------------------------------------------
  // 2. A slow draft gets the honest copy, then clears it
  // -------------------------------------------------------------------------

  await test('a slow draft raises the wait state and always lowers it', async () => {
    const clock = fakeClock();
    const seen = [];
    let release;
    const pending = runWithWaitHint(
      () => new Promise((resolve) => { release = resolve; }),
      {
        onWait: (waiting) => seen.push(waiting),
        setTimer: clock.setTimer,
        clearTimer: clock.clearTimer,
      },
    );
    await clock.advance(WAIT_HINT_DELAY_MS);
    assert.deepEqual(seen, [true], 'the hint fires once the request is slow');
    release('cold');
    assert.equal(await pending, 'cold');
    assert.deepEqual(seen, [true, false]);
    assert.equal(clock.pending(), 0);
  });

  // -------------------------------------------------------------------------
  // 3. A failure clears the wait state too — no permanent spinner
  // -------------------------------------------------------------------------

  await test('a rejected request still lowers the wait state', async () => {
    const clock = fakeClock();
    const seen = [];
    const pending = runWithWaitHint(
      async () => {
        throw new Error('transport');
      },
      {
        onWait: (waiting) => seen.push(waiting),
        setTimer: clock.setTimer,
        clearTimer: clock.clearTimer,
      },
    );
    await assert.rejects(pending, /transport/);
    assert.deepEqual(seen, [false]);
    assert.equal(clock.pending(), 0);
  });

  // -------------------------------------------------------------------------
  // 4. The timeout path is bounded, and is a retryable state — not a dead end
  // -------------------------------------------------------------------------

  await test('a request that never answers times out instead of hanging', async () => {
    const clock = fakeClock();
    const seen = [];
    // The handler is attached before the clock moves: a rejection nobody is
    // listening for yet would be an unhandled rejection, not a test failure.
    const pending = runWithWaitHint(() => new Promise(() => {}), {
      onWait: (waiting) => seen.push(waiting),
      setTimer: clock.setTimer,
      clearTimer: clock.clearTimer,
    }).then(
      (value) => ({ value }),
      (error) => ({ error }),
    );
    await clock.advance(WAIT_HINT_DELAY_MS);
    assert.deepEqual(seen, [true]);
    await clock.advance(MUTATION_DEADLINE_MS);
    const { error: caught } = await pending;
    assert.ok(caught, 'the deadline must reject');
    assert.ok(isJourneyTimeout(caught));
    assert.equal(caught.message, TIMEOUT_MESSAGE);
    assert.deepEqual(seen, [true, false], 'the spinner is lowered on timeout');
    assert.equal(clock.pending(), 0);
  });

  await test('a timeout plans as a retryable error, never as a verdict', () => {
    const plan = planFailure(null, new (require('./journey-requests').JourneyTimeoutError)());
    assert.equal(plan.kind, 'error');
    assert.equal(plan.retryable, true);
    assert.notEqual(plan.kind, 'disabled');
  });

  await test('the deadline can be switched off without losing the hint', async () => {
    const clock = fakeClock();
    const seen = [];
    let release;
    const pending = runWithWaitHint(
      () => new Promise((resolve) => { release = resolve; }),
      {
        onWait: (waiting) => seen.push(waiting),
        deadlineMs: 0,
        setTimer: clock.setTimer,
        clearTimer: clock.clearTimer,
      },
    );
    await clock.advance(WAIT_HINT_DELAY_MS * 100);
    assert.deepEqual(seen, [true]);
    release('eventually');
    assert.equal(await pending, 'eventually');
    assert.deepEqual(seen, [true, false]);
  });

  // -------------------------------------------------------------------------
  // 5. The bound itself
  // -------------------------------------------------------------------------

  await test('the deadline leaves room for the server budget but is finite', () => {
    // The server's generation claim is 90 s and its operation budget 75 s. A
    // client bound below the operation budget would give up on requests the
    // server is about to answer; one that never fires is the dead end.
    assert.ok(MUTATION_DEADLINE_MS > 75_000, "WP-69: above the server budget");
    assert.ok(MUTATION_DEADLINE_MS <= 90_000);
    assert.ok(WAIT_HINT_DELAY_MS > 0 && WAIT_HINT_DELAY_MS <= 1000);
  });

  // -------------------------------------------------------------------------
  // 8. WP-28 — warmth is told, not timed
  // -------------------------------------------------------------------------

  await test('a draft the server called warm holds the hint back, and still shows it', async () => {
    // `TodayEnvelope.is_warm` says a prefetched scene is waiting, so the copy
    // is delayed past the tens of milliseconds a served prefetch takes. It is
    // delayed, not removed: a warm scene whose preconditions changed is
    // discarded server-side and generated like any other, and that learner is
    // still told what is happening rather than left at a silent button.
    assert.ok(WARM_WAIT_HINT_DELAY_MS > WAIT_HINT_DELAY_MS);
    assert.ok(WARM_WAIT_HINT_DELAY_MS < MUTATION_DEADLINE_MS);

    const clock = fakeClock();
    const seen = [];
    let release;
    const pending = runWithWaitHint(
      () => new Promise((resolve) => { release = resolve; }),
      {
        onWait: (waiting) => seen.push(waiting),
        delayMs: WARM_WAIT_HINT_DELAY_MS,
        setTimer: clock.setTimer,
        clearTimer: clock.clearTimer,
      },
    );
    await clock.advance(WAIT_HINT_DELAY_MS);
    assert.deepEqual(seen, [], 'the cold delay must not fire on a warm draft');
    await clock.advance(WARM_WAIT_HINT_DELAY_MS - WAIT_HINT_DELAY_MS);
    assert.deepEqual(seen, [true], 'a warm draft that went cold still says so');
    release('late');
    assert.equal(await pending, 'late');
    assert.deepEqual(seen, [true, false]);
    assert.equal(clock.pending(), 0);
  });


  // -------------------------------------------------------------------------
  // WP-76 — reply first, verdict second (slow fake provider)
  // -------------------------------------------------------------------------

  await test('WP-76: a 12 s reply turn shows the reply before the verdict', async () => {
    const clock = fakeClock();
    const sequencer = createReplySequencer({
      setTimer: clock.setTimer,
      clearTimer: clock.clearTimer,
    });
    const timeline = [];
    let elapsed = 0;
    const apply = (feedback) => timeline.push({ at: elapsed, feedback });

    // The learner taps «Envoyer»: in flight, the character is typing.
    apply({ kind: 'submitting' });
    const inflight = runMutation({
      mutationId: 'm-76',
      invoke: () =>
        new Promise((resolve) => {
          clock.setTimer(() => resolve(attemptResult()), 12_600);
        }),
      sleep: (ms) => new Promise((resolve) => clock.setTimer(resolve, ms)),
    });
    await clock.advance(12_600);
    elapsed = 12_600;
    const outcome = await inflight;
    assert.equal(outcome.ok, true);
    stageAttemptFeedback(outcome.value, 'respond', sequencer, apply);

    // The instant the result lands: the reply is on screen, the verdict is not.
    const landed = timeline[timeline.length - 1];
    assert.equal(landed.feedback.kind, 'replying');
    assert.equal(landed.feedback.result.character_reply_fr, REPLY);
    assert.ok(
      typedReply(REPLY, 0, replyRevealMs(REPLY)).length > 0,
      'the first words are visible the moment the result arrives',
    );
    assert.ok(!timeline.some((entry) => entry.feedback.kind === 'graded'));

    // Halfway through the typing: still no verdict.
    const delay = verdictDelayMs(REPLY);
    await clock.advance(delay - 1);
    elapsed += delay - 1;
    assert.ok(!timeline.some((entry) => entry.feedback.kind === 'graded'));

    // Then the verdict joins the reply — the same result, the same verdict.
    await clock.advance(1);
    elapsed += 1;
    const verdict = timeline[timeline.length - 1];
    assert.equal(verdict.feedback.kind, 'graded');
    assert.equal(verdict.feedback.result, landed.feedback.result);
    assert.equal(verdict.feedback.verdict, landed.feedback.verdict);
    assert.deepEqual(
      timeline.map((entry) => entry.feedback.kind),
      ['submitting', 'replying', 'graded'],
    );
    assert.ok(delay <= REPLY_REVEAL_MAX_MS + VERDICT_BEAT_MS, 'a long reply never holds the verdict long');
    assert.equal(clock.pending(), 0);
  });

  await test('WP-76: recall, unscored and reduced-motion results are never staged', async () => {
    const seen = [];
    const sequencer = createReplySequencer({ setTimer: () => 1, clearTimer: () => {} });
    stageAttemptFeedback(attemptResult(), 'recall', sequencer, (f) => seen.push(f.kind));
    stageAttemptFeedback(
      attemptResult({ pending: true, task_outcome: 'unscored' }),
      'respond',
      sequencer,
      (f) => seen.push(f.kind),
    );
    stageAttemptFeedback(attemptResult({ character_reply_fr: null }), 'respond', sequencer, (f) =>
      seen.push(f.kind),
    );
    stageAttemptFeedback(attemptResult(), 'respond', sequencer, (f) => seen.push(f.kind), {
      reducedMotion: true,
    });
    assert.deepEqual(seen, ['graded', 'unscored', 'graded', 'graded']);
  });

  await test('WP-76: a newer attempt cancels the stale verdict', async () => {
    const clock = fakeClock();
    const sequencer = createReplySequencer({ setTimer: clock.setTimer, clearTimer: clock.clearTimer });
    const seen = [];
    stageAttemptFeedback(attemptResult(), 'respond', sequencer, (f) => seen.push(f.kind));
    sequencer.cancel(); // what `performAttempt` / `continueJourney` do first
    await clock.advance(10_000);
    assert.deepEqual(seen, ['replying']);
    assert.equal(clock.pending(), 0);
  });

  await test('WP-76: a replayed mutation stages to the same final feedback', async () => {
    const clock = fakeClock();
    const sequencer = createReplySequencer({ setTimer: clock.setTimer, clearTimer: clock.clearTimer });
    const sent = [];
    let calls = 0;
    const outcome = await runMutation({
      mutationId: 'm-replay',
      invoke: async (id) => {
        sent.push(id);
        calls += 1;
        // The first answer is the server's 202 `processing` for the same key.
        return calls === 1
          ? { detail: { code: 'processing', retry_after_seconds: 0 } }
          : attemptResult();
      },
      sleep: async () => undefined,
    });
    assert.deepEqual(sent, ['m-replay', 'm-replay'], 'the replay reuses the key');
    const finals = [];
    stageAttemptFeedback(outcome.value, 'respond', sequencer, (f) => finals.push(f));
    await clock.advance(verdictDelayMs(REPLY));
    stageAttemptFeedback(attemptResult(), 'respond', sequencer, (f) => finals.push(f));
    await clock.advance(verdictDelayMs(REPLY));
    const graded = finals.filter((f) => f.kind === 'graded');
    assert.equal(graded.length, 2);
    assert.deepEqual(graded[0].result, graded[1].result);
    assert.equal(graded[0].verdict, graded[1].verdict);
  });

  await test('WP-76: typed reply reveals whole words and ends complete', () => {
    const total = replyRevealMs(REPLY);
    assert.ok(total > 0);
    const early = typedReply(REPLY, 1, total);
    assert.equal(early, 'Samedi,', 'the first whole word at once');
    const mid = typedReply(REPLY, total / 2, total);
    assert.ok(REPLY.startsWith(mid) && mid.length < REPLY.length);
    assert.ok(mid === REPLY || REPLY[mid.length] === ' ', 'never half a word');
    assert.equal(typedReply(REPLY, total, total), REPLY);
    assert.equal(replyRevealMs(REPLY, { reducedMotion: true }), 0);
  });

  // -------------------------------------------------------------------------
  // WP-76 — the header counts steps, never a clock
  // -------------------------------------------------------------------------

  await test('WP-76: the header does not move while a request is in flight or when it lands', () => {
    const before = day();
    const inFlight = day(); // the snapshot does not change while the POST is open
    const after = attemptResult().journey; // respond completed, still on screen
    const captions = [before, inFlight, after].map((journey) => journeyHeaderCaption(journey, stepOf));
    assert.deepEqual(captions, ['Étape 2 sur 3', 'Étape 2 sur 3', 'Étape 2 sur 3']);
    // The bug it replaces: the plan's remaining estimate dropped 225 s → 45 s
    // the moment the server answered — the wait, charged to the learner.
    assert.equal(journeyProgress(before).remainingSeconds, 225);
    assert.equal(journeyProgress(after).remainingSeconds, 45);
    assert.ok(!/min|restant|\ds\b/.test(captions.join(' ')), 'no clock in the header');
    // Only the learner's own «Continuer» moves it.
    const advanced = {
      ...after,
      current_step_id: 's-resolution',
      steps: after.steps.map((step) =>
        step.id === 's-resolution' ? { ...step, status: 'active' } : step,
      ),
    };
    assert.equal(journeyHeaderCaption(advanced, stepOf), 'Étape 3 sur 3');
    assert.equal(journeyHeaderCaption(null, stepOf), undefined);
  });

  // -------------------------------------------------------------------------
  // WP-76 — the waits speak in the story, in the learner's language
  // -------------------------------------------------------------------------

  await test('WP-76: typing and preparing lines', () => {
    assert.equal(typingLine('Marin', 'fr'), 'Marin écrit…');
    assert.equal(typingLine('Marin', 'de'), 'Marin schreibt…');
    assert.equal(typingLine('Marin', 'en'), 'Marin is typing…');
    assert.equal(typingLine('', 'fr'), 'Réponse en cours…');
    assert.equal(preparingLine('Le Mistral', 'Marin', 'fr'), 'Le Mistral s’anime…');
    assert.equal(preparingLine('', 'Marin', 'fr'), 'Marin arrive…', 'the engine often ships no place');
    assert.equal(preparingLine(null, null, 'de'), 'Deine Szene wird vorbereitet…');
    assert.equal(preparingLine('Le Mistral', null, 'xx'), 'Le Mistral comes to life…');
    for (const line of [typingLine('Marin', 'fr'), preparingLine('Le Mistral', null, 'fr')]) {
      assert.ok(!/Envoi/.test(line));
    }
  });

  if (failures.length) {
    for (const [name, error] of failures) {
      console.error(`FAIL ${name}\n  ${error && error.stack ? error.stack : error}`);
    }
    console.error(`\n${passed} passed, ${failures.length} failed`);
    process.exit(1);
  }
  console.log(`journey-latency: ${passed} passed`);
}

main();
