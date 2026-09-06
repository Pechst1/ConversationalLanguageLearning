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
