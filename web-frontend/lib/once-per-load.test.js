// WP-43 — request coalescing for the Home rows (WP-39 D-4).
const test = require('node:test');
const assert = require('node:assert/strict');

require('../node_modules/sucrase/register/ts');
const { oncePerLoad, resetOncePerLoad } = require('./once-per-load.ts');

test.beforeEach(() => resetOncePerLoad());

test('concurrent identical calls reach the fetcher once and all get the answer', async () => {
  let calls = 0;
  const fetcher = () => {
    calls += 1;
    return Promise.resolve({ ok: true, n: calls });
  };
  const results = await Promise.all([
    oncePerLoad('rehearsals/state', fetcher),
    oncePerLoad('rehearsals/state', fetcher),
    oncePerLoad('rehearsals/state', fetcher),
  ]);
  assert.equal(calls, 1);
  assert.deepEqual(results, [{ ok: true, n: 1 }, { ok: true, n: 1 }, { ok: true, n: 1 }]);
});

test('different keys are different requests', async () => {
  let calls = 0;
  const fetcher = () => Promise.resolve((calls += 1));
  await Promise.all([oncePerLoad('a', fetcher), oncePerLoad('b', fetcher)]);
  assert.equal(calls, 2);
});

test('a settled answer is shared inside the window and refetched after it', async () => {
  let calls = 0;
  const fetcher = () => Promise.resolve((calls += 1));
  await oncePerLoad('words', fetcher);
  await oncePerLoad('words', fetcher, Date.now());
  assert.equal(calls, 1, 'a late duplicate inside the window shares the answer');
  await oncePerLoad('words', fetcher, Date.now() + 60_000);
  assert.equal(calls, 2, 'after the window the server is asked again');
});

test('a failure is shared, not retried five times in one burst', async () => {
  let calls = 0;
  const fetcher = () => {
    calls += 1;
    return Promise.reject(new Error('down'));
  };
  const outcomes = await Promise.allSettled([
    oncePerLoad('intake', fetcher),
    oncePerLoad('intake', fetcher),
  ]);
  assert.equal(calls, 1);
  assert.ok(outcomes.every((item) => item.status === 'rejected'));
});
