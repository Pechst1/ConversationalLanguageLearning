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
  isJourneyTimeout,
  planFailure,
  runWithWaitHint,
} = require('./journey-requests');

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
    assert.ok(MUTATION_DEADLINE_MS >= 45_000);
    assert.ok(MUTATION_DEADLINE_MS <= 90_000);
    assert.ok(WAIT_HINT_DELAY_MS > 0 && WAIT_HINT_DELAY_MS <= 1000);
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
