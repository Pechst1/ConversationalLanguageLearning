// WP-73 — client error tracking: capture carries the request id and no PII.
const test = require('node:test');
const assert = require('node:assert/strict');

require('../node_modules/sucrase/register/ts');
const obs = require('./observability.ts');

const LEARNER_TEXT = "Je voudrais un croissant, s'il vous plaît";

function fakeSentry() {
  const calls = { init: [], captured: [], users: [], tags: [] };
  return {
    calls,
    init: (options) => calls.init.push(options),
    captureException: (error, hint) => calls.captured.push({ error, hint }),
    setUser: (user) => calls.users.push(user),
    setTag: (k, v) => calls.tags.push([k, v]),
  };
}

test.afterEach(() => {
  obs.__setSentryForTests(null);
  delete process.env.NEXT_PUBLIC_SENTRY_DSN;
});

test('no DSN: nothing loads, capture is a no-op', async () => {
  let loaded = false;
  const result = await obs.initObservability(async () => { loaded = true; return fakeSentry(); });
  assert.equal(result, null);
  assert.equal(loaded, false);
  obs.captureClientError(new Error('x'));
});

test('with a DSN the SDK is initialised without default PII and scrubbing hooks', async () => {
  process.env.NEXT_PUBLIC_SENTRY_DSN = 'https://public@o0.ingest.sentry.io/1';
  const sdk = fakeSentry();
  obs.setObservabilityUser('user-42');
  assert.equal(await obs.initObservability(async () => sdk), sdk);
  const options = sdk.calls.init[0];
  assert.equal(options.sendDefaultPii, false);
  assert.equal(typeof options.beforeSend, 'function');
  assert.deepEqual(sdk.calls.users.at(-1), { id: 'user-42' });
});

test('a failed API call reaches the capture function with its request id and no body', () => {
  const sdk = fakeSentry();
  obs.__setSentryForTests(sdk);
  const axiosError = {
    isAxiosError: true,
    message: 'Request failed with status code 500',
    response: { status: 500 },
    config: { data: JSON.stringify({ text: LEARNER_TEXT }), headers: { Authorization: 'Bearer secret' } },
  };
  obs.captureClientError(axiosError, { requestId: 'abc123def456', route: '/atelier/submit?token=reset-9' });
  assert.equal(sdk.calls.captured.length, 1);
  const { error, hint } = sdk.calls.captured[0];
  assert.equal(hint.tags.request_id, 'abc123def456');
  assert.equal(hint.tags.route, '/atelier/submit');
  assert.ok(error instanceof Error);
  const blob = JSON.stringify({ message: error.message, hint });
  assert.ok(!blob.includes(LEARNER_TEXT));
  assert.ok(!blob.includes('secret'));
  assert.ok(!blob.includes('reset-9'));
});

test('beforeSend strips bodies, query strings, cookies, auth headers and non-id user fields', () => {
  const event = obs.scrubClientEvent({
    request: {
      url: 'capacitor://localhost/auth/reset?code=123456',
      data: LEARNER_TEXT,
      cookies: 'a=b',
      headers: { Authorization: 'Bearer secret', 'User-Agent': 'ua' },
    },
    user: { id: 7, email: 'learner@example.com', ip_address: '1.2.3.4' },
    breadcrumbs: [
      { category: 'console', message: LEARNER_TEXT },
      { category: 'ui.input', message: 'textarea' },
      { category: 'fetch', data: { url: '/api/v1/x?token=t', body: LEARNER_TEXT } },
    ],
  });
  assert.equal(event.request.url, 'capacitor://localhost/auth/reset');
  assert.deepEqual(event.request.headers, { 'User-Agent': 'ua' });
  assert.deepEqual(event.user, { id: '7' });
  assert.equal(event.breadcrumbs.length, 1);
  assert.equal(event.breadcrumbs[0].data.url, '/api/v1/x');
  assert.ok(!JSON.stringify(event).includes(LEARNER_TEXT));
});

test('request ids are 32 hex characters, accepted by the API pattern', () => {
  const id = obs.newRequestId();
  assert.match(id, /^[0-9a-f]{32}$/);
  assert.notEqual(id, obs.newRequestId());
});
