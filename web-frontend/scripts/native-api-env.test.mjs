import assert from 'node:assert/strict';
import test from 'node:test';

import { resolveNativeApiEnvironment } from './native-api-env.mjs';

test('derives a secure WebSocket origin from the hosted API', () => {
  const resolved = resolveNativeApiEnvironment({
    NEXT_PUBLIC_API_BASE_URL: 'https://atelier.onrender.com/api/v1',
  });

  assert.equal(resolved.NEXT_PUBLIC_API_BASE_URL, 'https://atelier.onrender.com/api/v1');
  assert.equal(resolved.NEXT_PUBLIC_WS_URL, 'wss://atelier.onrender.com');
});

test('rejects a stale local WebSocket override for a device build', () => {
  assert.throws(
    () => resolveNativeApiEnvironment({
      NEXT_PUBLIC_API_BASE_URL: 'https://atelier.onrender.com/api/v1',
      NEXT_PUBLIC_WS_URL: 'ws://localhost:8000',
    }),
    /must use WSS/,
  );
});

test('allows explicit local networking only for simulator development', () => {
  const resolved = resolveNativeApiEnvironment({
    ALLOW_LOCAL_NATIVE_API: 'true',
    NEXT_PUBLIC_API_URL: 'http://localhost:8000/api/v1',
  });

  assert.equal(resolved.NEXT_PUBLIC_WS_URL, 'ws://localhost:8000');
});

test('rejects placeholder hosts unless an explicit rehearsal flag is set', () => {
  assert.throws(
    () => resolveNativeApiEnvironment({
      NEXT_PUBLIC_API_BASE_URL: 'https://api.example.com/api/v1',
    }),
    /placeholder, not a deployable host/,
  );

  assert.deepEqual(
    resolveNativeApiEnvironment({
      NEXT_PUBLIC_API_BASE_URL: 'https://api.example.com/api/v1',
      ALLOW_PLACEHOLDER_NATIVE_API: 'true',
    }),
    {
      NEXT_PUBLIC_API_BASE_URL: 'https://api.example.com/api/v1',
      NEXT_PUBLIC_API_URL: 'https://api.example.com/api/v1',
      NEXT_PUBLIC_WS_URL: 'wss://api.example.com',
    },
  );
});

test('an unset API host is a configuration error, never a guessed port', () => {
  assert.throws(
    () => resolveNativeApiEnvironment({}),
    (error) => {
      assert.match(error.message, /missing NEXT_PUBLIC_API_BASE_URL/);
      // Port 8000 belongs to a different application; the native client
      // (lib/native-auth.ts) refuses it too rather than defaulting.
      assert.doesNotMatch(error.message, /localhost:8000/);
      return true;
    },
  );
});

test('the native runtime client agrees with this build-time guard', async () => {
  const { createRequire } = await import('node:module');
  const path = await import('node:path');
  const { fileURLToPath } = await import('node:url');

  const webRoot = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
  const require = createRequire(import.meta.url);
  require(path.join(webRoot, 'node_modules/sucrase/register/ts'));

  const previous = {
    base: process.env.NEXT_PUBLIC_API_BASE_URL,
    url: process.env.NEXT_PUBLIC_API_URL,
  };
  delete process.env.NEXT_PUBLIC_API_BASE_URL;
  delete process.env.NEXT_PUBLIC_API_URL;
  try {
    const nativeAuthPath = path.join(webRoot, 'lib/native-auth.ts');
    delete require.cache[require.resolve(nativeAuthPath)];
    const { nativeApiBaseUrl } = require(nativeAuthPath);
    assert.throws(() => nativeApiBaseUrl(), /NEXT_PUBLIC_API_BASE_URL is not set/);
  } finally {
    if (previous.base === undefined) delete process.env.NEXT_PUBLIC_API_BASE_URL;
    else process.env.NEXT_PUBLIC_API_BASE_URL = previous.base;
    if (previous.url === undefined) delete process.env.NEXT_PUBLIC_API_URL;
    else process.env.NEXT_PUBLIC_API_URL = previous.url;
  }
});
