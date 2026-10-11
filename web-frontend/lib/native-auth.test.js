/**
 * WP-71 — the native app stays signed in.
 *
 * The defect: every API request asked for an access token on its own. After the
 * token expired, ten requests fired ten refreshes with the same rotating refresh
 * token; the losers got 401 and each 401 wiped the keychain. A dropped network
 * during a refresh was treated the same way. Both signed the learner out.
 *
 * Runs the real lib/native-auth.ts with the secure-storage plugin and fetch
 * replaced by in-memory fakes.  node --test lib/native-auth.test.js
 */
const assert = require('node:assert/strict');
const path = require('node:path');
const Module = require('node:module');
const { test, beforeEach } = require('node:test');

const WEB_ROOT = __dirname.replace(/\/lib$/, '');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));

// --- fakes -----------------------------------------------------------------

const keychain = new Map();
const SecureStoragePlugin = {
  async get({ key }) {
    if (!keychain.has(key)) throw new Error('Item with given key does not exist');
    return { value: keychain.get(key) };
  },
  async set({ key, value }) {
    keychain.set(key, value);
    return { value: true };
  },
  async remove({ key }) {
    if (!keychain.has(key)) throw new Error('Item with given key does not exist');
    keychain.delete(key);
    return { value: true };
  },
};

const originalLoad = Module._load;
Module._load = function load(request, parent, isMain) {
  if (request === 'capacitor-secure-storage-plugin') return { SecureStoragePlugin };
  return originalLoad.call(this, request, parent, isMain);
};

globalThis.window = globalThis.window || {};
globalThis.window.atob = (value) => Buffer.from(value, 'base64').toString('binary');
process.env.NEXT_PUBLIC_API_BASE_URL = 'https://api.example.test';

const nativeAuth = require(path.join(WEB_ROOT, 'lib/native-auth.ts'));

function jwt(expSecondsFromNow, marker) {
  const header = Buffer.from(JSON.stringify({ alg: 'HS256', typ: 'JWT' })).toString('base64url');
  const payload = Buffer.from(
    JSON.stringify({ exp: Math.floor(Date.now() / 1000) + expSecondsFromNow, m: marker }),
  ).toString('base64url');
  return `${header}.${payload}.sig`;
}

let refreshCalls = 0;
let serverBehaviour = 'rotate';
let rotation = 0;

function jsonResponse(status, body) {
  return {
    ok: status >= 200 && status < 300,
    status,
    async json() {
      return body;
    },
  };
}

globalThis.fetch = async (url, init) => {
  assert.match(String(url), /\/auth\/refresh$/);
  refreshCalls += 1;
  const { refresh_token: presented } = JSON.parse(init.body);
  // Let every concurrent caller pile up before the "server" answers.
  await new Promise((resolve) => setTimeout(resolve, 20));
  if (serverBehaviour === 'offline') throw new TypeError('Network request failed');
  if (serverBehaviour === 'server-error') return jsonResponse(503, { detail: 'down' });
  if (serverBehaviour === 'reject') return jsonResponse(401, { detail: 'Invalid refresh token' });
  // A rotating server: the presented token must be the live one.
  if (presented !== `refresh-${rotation}`) return jsonResponse(401, { detail: 'Invalid refresh token' });
  rotation += 1;
  return jsonResponse(200, {
    access_token: jwt(3600, `access-${rotation}`),
    refresh_token: `refresh-${rotation}`,
    token_type: 'bearer',
  });
};

function seedExpiredSession() {
  keychain.clear();
  keychain.set('atelier.accessToken', jwt(-60, 'expired'));
  keychain.set('atelier.refreshToken', `refresh-${rotation}`);
  keychain.set('atelier.user', JSON.stringify({ id: 'u1', email: 'a@example.com' }));
}

beforeEach(() => {
  refreshCalls = 0;
  serverBehaviour = 'rotate';
  seedExpiredSession();
});

// --- tests -----------------------------------------------------------------

test('ten parallel requests after expiry share one refresh and stay signed in', async () => {
  const tokens = await Promise.all(
    Array.from({ length: 10 }, () => nativeAuth.getNativeAccessToken()),
  );

  assert.equal(refreshCalls, 1, 'one rotation for ten callers');
  assert.equal(new Set(tokens).size, 1);
  assert.ok(tokens[0], 'every caller got a token');
  assert.equal(keychain.get('atelier.refreshToken'), `refresh-${rotation}`);
  assert.ok(keychain.has('atelier.user'));
});

test('ten 401 retries share one refresh too', async () => {
  const rejected = keychain.get('atelier.accessToken');
  const results = await Promise.all(
    Array.from({ length: 10 }, () => nativeAuth.recoverNativeAccessToken(rejected)),
  );

  assert.equal(refreshCalls, 1);
  assert.ok(results.every((result) => result.status === 'refreshed'));
});

test('a 401 on a token that was already replaced reuses the new one', async () => {
  const stale = keychain.get('atelier.accessToken');
  await nativeAuth.getNativeAccessToken();
  assert.equal(refreshCalls, 1);

  const result = await nativeAuth.recoverNativeAccessToken(stale);
  assert.equal(result.status, 'refreshed');
  assert.equal(refreshCalls, 1, 'no second rotation');
});

test('a network error during refresh keeps the tokens', async () => {
  serverBehaviour = 'offline';
  const before = new Map(keychain);

  const result = await nativeAuth.refreshNativeSession();

  assert.equal(result.status, 'unreachable');
  assert.deepEqual(new Map(keychain), before);
});

test('a server error during refresh keeps the tokens', async () => {
  serverBehaviour = 'server-error';
  const result = await nativeAuth.refreshNativeSession();
  assert.equal(result.status, 'unreachable');
  assert.ok(keychain.has('atelier.refreshToken'));
});

test('an offline launch an hour later keeps the session', async () => {
  serverBehaviour = 'offline';
  const session = await nativeAuth.loadNativeAuthSession();

  assert.ok(session, 'still signed in');
  assert.equal(session.refreshToken, `refresh-${rotation}`);
  assert.equal(session.user.id, 'u1');
  assert.ok(keychain.has('atelier.accessToken'));
});

test('only a definitive 401 from the refresh endpoint clears the keychain', async () => {
  serverBehaviour = 'reject';
  const results = await Promise.all(
    Array.from({ length: 5 }, () => nativeAuth.refreshNativeSession()),
  );

  assert.equal(refreshCalls, 1);
  assert.ok(results.every((result) => result.status === 'signed-out'));
  assert.equal(keychain.size, 0);
  assert.equal(await nativeAuth.getNativeAccessToken(), null);
});

test('a fresh access token is used without any refresh', async () => {
  keychain.set('atelier.accessToken', jwt(3600, 'fresh'));
  const tokens = await Promise.all(
    Array.from({ length: 10 }, () => nativeAuth.getNativeAccessToken()),
  );
  assert.equal(refreshCalls, 0);
  assert.equal(new Set(tokens).size, 1);
});

test('the API client routes a 401 through the shared recovery, not a keychain wipe', () => {
  const fs = require('node:fs');
  const source = fs.readFileSync(path.join(WEB_ROOT, 'services/api.ts'), 'utf8');
  assert.match(source, /recoverNativeAccessToken\(/);
  assert.doesNotMatch(source, /clearNativeAuthSession/);
  assert.doesNotMatch(source, /refreshNativeAccessToken\(/);
});
