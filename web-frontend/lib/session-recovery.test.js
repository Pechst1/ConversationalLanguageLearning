const { test } = require('node:test');
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
let reads = 0;
let session = { accessToken: 'fresh' };
function stub(name, exports) {
  const filename = require.resolve(name);
  require.cache[filename] = { id: filename, filename, loaded: true, exports };
}
stub('next-auth/react', { getSession: async () => { reads++; return session; } });
stub('@/lib/app-auth', { getAppAccessToken: async () => 'expired' });
stub('@/lib/native-platform', { isNativePlatform: () => false });
const axios = require('axios');
const api = require('../services/api.ts').default;
const { webSessionRecovery } = require('./session-recovery.ts');

for (const url of ['/daily-journeys/day/attempts', '/atelier/sessions/forge/answer', '/missions/letter/turns']) {
  test(`401 refreshes and replays the same mutation once: ${url}`, async () => {
    reads = 0;
    session = { accessToken: 'fresh' };
    const seen = [];
    const body = { client_mutation_id: 'stable-id', text: 'Si je finis tôt, je viendrai.' };
    const result = await api.post(url, body, { suppressGlobalError: true, adapter: async (config) => {
      seen.push({ token: config.headers.Authorization, data: config.data });
      if (seen.length === 1) throw new axios.AxiosError('expired', 'ERR_BAD_REQUEST', config, null, { status: 401, data: {} });
      return { status: 200, data: { accepted: true }, headers: {}, config };
    } });
    assert.deepEqual(result, { accepted: true });
    assert.equal(reads, 1);
    assert.deepEqual(seen.map((r) => r.token), ['Bearer expired', 'Bearer fresh']);
    assert.equal(seen[0].data, seen[1].data);
    assert.equal(JSON.parse(seen[1].data).client_mutation_id, 'stable-id');
  });
}

test('an unsuccessful refresh never loops or replays', async () => {
  reads = 0; session = { error: 'RefreshAccessTokenError', accessToken: 'expired' };
  let calls = 0;
  await assert.rejects(api.post('/daily-journeys/day/attempts', {}, {
    suppressGlobalError: true, adapter: async (config) => {
      calls++;
      throw new axios.AxiosError('expired', 'ERR_BAD_REQUEST', config, null, { status: 401, data: {} });
    },
  }));
  assert.equal(reads, 1);
  assert.equal(calls, 1);
});

test('a second 401 after refresh is terminal', async () => {
  reads = 0; session = { accessToken: 'fresh' }; let calls = 0;
  await assert.rejects(api.get('/missions', { suppressGlobalError: true, adapter: async (config) => {
    calls++;
    throw new axios.AxiosError('expired', 'ERR_BAD_REQUEST', config, null, { status: 401, data: {} });
  } }));
  assert.equal(reads, 1); assert.equal(calls, 2);
});

test('concurrent failures share one session refresh', async () => {
  let finish; let calls = 0;
  const refresh = webSessionRecovery(() => { calls++; return new Promise((r) => { finish = r; }); });
  const first = refresh(); const second = refresh();
  finish({ accessToken: 'fresh' });
  assert.deepEqual(await Promise.all([first, second]), ['fresh', 'fresh']);
  assert.equal(calls, 1);
});
