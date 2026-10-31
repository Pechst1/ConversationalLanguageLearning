/**
 * #386 — /api/auth/session must not 500, or hang, when the backend refresh
 * goes wrong.
 *
 * The defect: the jwt callback in lib/auth.ts guarded the transport of the
 * refresh call but trusted what came back and had no deadline. A 200 whose body
 * was `null` threw inside the callback, and NextAuth answers a throwing callback
 * with a 500; a backend that never answered kept the session read open forever,
 * so Home stayed on «Loading». lib/native-auth.ts already did both right.
 *
 * Runs the real lib/auth.ts with fetch replaced.  node --test lib/auth-session-refresh.test.js
 */
const assert = require('node:assert/strict');
const path = require('node:path');
const Module = require('node:module');
const { test, beforeEach, afterEach, mock } = require('node:test');

const WEB_ROOT = __dirname.replace(/\/lib$/, '');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));

const originalLoad = Module._load;
Module._load = function load(request, parent, isMain) {
  if (request.startsWith('@/')) {
    return originalLoad.call(this, path.join(WEB_ROOT, request.slice(2)), parent, isMain);
  }
  return originalLoad.call(this, request, parent, isMain);
};

const originalFetch = global.fetch;
const originalApiUrl = process.env.API_URL;
let counter = 0;

beforeEach(() => {
  process.env.API_URL = 'http://api.test';
});

afterEach(() => {
  global.fetch = originalFetch;
  if (originalApiUrl === undefined) delete process.env.API_URL;
  else process.env.API_URL = originalApiUrl;
  mock.timers.reset();
});

function loadJwt() {
  const p = path.join(WEB_ROOT, 'lib/auth.ts');
  delete require.cache[require.resolve(p)];
  return require(p).authOptions.callbacks.jwt;
}

// A fresh refresh token per test: refreshes in flight are shared by token.
function expiredToken() {
  counter += 1;
  return {
    accessToken: 'old-access',
    refreshToken: `refresh-${counter}`,
    accessTokenExpires: 1,
    id: 'learner-1',
  };
}

test('a refresh answered 200 with a null body keeps the session instead of throwing', async () => {
  global.fetch = async () => new Response('null', { status: 200 });
  const jwt = loadJwt();
  const token = expiredToken();

  let result;
  await assert.doesNotReject(
    async () => { result = await jwt({ token }); },
    'the jwt callback must not throw: NextAuth turns a throw into a 500 on /api/auth/session',
  );

  assert.equal(result.accessToken, 'old-access', 'the learner keeps the token they had');
  assert.equal(result.refreshToken, token.refreshToken);
  assert.equal(result.error, undefined, 'an unreadable answer is not a verdict on the session');
});

test('a refresh answered 200 without an access token does not wipe the session token', async () => {
  global.fetch = async () => new Response('{}', { status: 200 });
  const jwt = loadJwt();
  const token = expiredToken();

  const result = await jwt({ token });

  assert.equal(result.accessToken, 'old-access', 'an empty answer is not a new access token');
  assert.equal(result.refreshToken, token.refreshToken);
  assert.equal(result.error, undefined);
});

test('a refresh the backend never answers is given up on, so the session read returns', async () => {
  mock.timers.enable({ apis: ['setTimeout'] });
  // Honours the abort signal the way fetch does; without one it hangs for ever.
  global.fetch = (url, init = {}) =>
    new Promise((resolve, reject) => {
      if (init.signal) init.signal.addEventListener('abort', () => reject(new Error('aborted')));
    });
  const jwt = loadJwt();
  const token = expiredToken();

  let settled = null;
  jwt({ token }).then((value) => { settled = value; });
  mock.timers.tick(120_000);
  await new Promise((resolve) => setImmediate(resolve));

  assert.ok(settled, 'the session read must answer within a bounded time');
  assert.equal(settled.accessToken, 'old-access');
  assert.equal(settled.error, undefined);
});

test('a good refresh still replaces the tokens', async () => {
  global.fetch = async () =>
    new Response(JSON.stringify({ access_token: 'new-access', refresh_token: 'new-refresh', token_type: 'bearer' }), {
      status: 200,
    });
  const jwt = loadJwt();

  const result = await jwt({ token: expiredToken() });

  assert.equal(result.accessToken, 'new-access');
  assert.equal(result.refreshToken, 'new-refresh');
  assert.equal(result.error, undefined);
});

test('a refresh the server refuses still ends the session', async () => {
  global.fetch = async () => new Response('no', { status: 401 });
  const jwt = loadJwt();

  const result = await jwt({ token: expiredToken() });

  assert.equal(result.error, 'RefreshAccessTokenError');
});
