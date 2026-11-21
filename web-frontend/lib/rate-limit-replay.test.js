/**
 * #770, #771, #847: a learner's answer refused with «You are going a little fast» is sent
 * again once the server's Retry-After has passed, whatever its method.
 *
 * The defect: the API's `rate_limited` 429 is raised by a router dependency before the
 * route runs (app/core/rate_limit.py), so nothing of the request happened and it can be
 * sent again as is. The client replayed it only for a GET. A refused POST (a journey
 * step's answer, a La Forge check or repair) went straight to the screen's catch, which
 * said «could not be sent» and, on a «Before the scene» choice, left no way forward: main's
 * season walk (run 43970276441, day 6) stood on step 2 of 9 after one 429 with
 * `retry_after_seconds: 38`.
 *
 * Runs the real services/api.ts with the transport replaced.
 *   node --test lib/rate-limit-replay.test.js
 */
const { test, mock, afterEach } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const Module = require('node:module');
require('sucrase/register/ts');
require('sucrase/register/tsx');
const root = path.resolve(__dirname, '..');
const resolve = Module._resolveFilename;
Module._resolveFilename = function (name, ...args) {
  return resolve.call(this, name.startsWith('@/') ? path.join(root, name.slice(2)) : name, ...args);
};
function stub(name, exports) {
  const filename = require.resolve(name);
  require.cache[filename] = { id: filename, filename, loaded: true, exports };
}
stub('next-auth/react', { getSession: async () => ({ accessToken: 'token' }) });
stub('@/lib/app-auth', { getAppAccessToken: async () => 'token' });
stub('@/lib/native-platform', { isNativePlatform: () => false });
const axios = require('axios');
const api = require('../services/api.ts').default;

afterEach(() => mock.timers.reset());

function refused(config, code, retryAfter) {
  const detail = { code, message: 'You are going a little fast. Please wait a moment and try again.', retry_after_seconds: retryAfter };
  return new axios.AxiosError('Too Many Requests', 'ERR_BAD_REQUEST', config, null, {
    status: 429,
    data: { detail },
    headers: { 'retry-after': String(retryAfter) },
    config,
  });
}

/** Send `url` through the real interceptors; the first `refusals` answers are 429s. */
async function send(url, { code = 'rate_limited', retryAfter = 1, refusals = 1 } = {}) {
  mock.timers.enable({ apis: ['setTimeout'] });
  const seen = [];
  const body = { client_mutation_id: 'answer-1', answer: { choice: 1 } };
  const pending = api
    .post(url, body, {
      suppressGlobalError: true,
      adapter: async (config) => {
        seen.push(config.data);
        if (seen.length <= refusals) throw refused(config, code, retryAfter);
        return { status: 200, data: { accepted: true }, headers: {}, config };
      },
    })
    .then((data) => data, (error) => ({ refused: error.response?.status }));
  // Let the refusal reach the interceptor, then let the server's wait pass.
  for (let i = 0; i < 20; i += 1) await Promise.resolve();
  mock.timers.tick(retryAfter * 1000);
  return { result: await pending, seen };
}

for (const url of [
  '/daily-journeys/j1/steps/s2/attempts',
  '/atelier/sessions/forge/attempts',
  '/atelier/attempts/a1/repair',
]) {
  test(`a rate-limited POST is sent again after Retry-After: ${url}`, async () => {
    const { result, seen } = await send(url, { retryAfter: 38 });
    assert.deepEqual(result, { accepted: true }, 'the refused answer must be sent again once the wait has passed, not reach the screen as a failure');
    assert.equal(seen.length, 2);
    assert.equal(seen[0], seen[1], 'the same body, client_mutation_id included');
  });
}

test('a second refusal reaches the screen: one replay, never a loop', async () => {
  const { result, seen } = await send('/daily-journeys/j1/steps/s2/attempts', { refusals: 5 });
  assert.deepEqual(result, { refused: 429 });
  assert.equal(seen.length, 2);
});

test('the day’s spend cap is not replayed: its wait is until tomorrow', async () => {
  const { result, seen } = await send('/daily-journeys/j1/steps/s2/attempts', { code: 'daily_budget_reached', retryAfter: 3600 });
  assert.deepEqual(result, { refused: 429 });
  assert.equal(seen.length, 1);
});
