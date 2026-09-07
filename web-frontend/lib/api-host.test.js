/**
 * The backend host must never be guessed.
 *
 * Regression guard for a real defect: lib/auth.ts defaulted to
 * http://localhost:8000, and next.config.js baked that same default into
 * env.API_URL. On a machine where another project owns port 8000, a bare
 * `npm run dev` would POST a learner's email and password to that other service.
 */
const assert = require('node:assert/strict');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = __dirname.replace(/\/lib$/, '');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
// services/api.ts reaches lib/app-auth.tsx through the `@/` alias.
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));

function loadApiHost() {
  const p = path.join(WEB_ROOT, 'lib/api-host.ts');
  delete require.cache[require.resolve(p)];
  return require(p);
}

test('an unset API_URL is a clear error, not a guessed port', () => {
  const previous = process.env.API_URL;
  delete process.env.API_URL;
  try {
    const { requireApiHost } = loadApiHost();
    assert.throws(() => requireApiHost('authentication'), (error) => {
      assert.match(error.message, /API_URL is not set/);
      assert.match(error.message, /authentication/);
      // The message must not suggest a port to guess at.
      assert.doesNotMatch(error.message, /localhost:8000/);
      return true;
    });
  } finally {
    if (previous === undefined) delete process.env.API_URL;
    else process.env.API_URL = previous;
  }
});

test('a blank or whitespace API_URL is treated as unset', () => {
  const previous = process.env.API_URL;
  process.env.API_URL = '   ';
  try {
    const { requireApiHost } = loadApiHost();
    assert.throws(() => requireApiHost('authentication'), /API_URL is not set/);
  } finally {
    if (previous === undefined) delete process.env.API_URL;
    else process.env.API_URL = previous;
  }
});

test('a configured API_URL is returned without a trailing slash', () => {
  const previous = process.env.API_URL;
  process.env.API_URL = 'http://localhost:8010//';
  try {
    const { requireApiHost } = loadApiHost();
    assert.equal(requireApiHost('authentication'), 'http://localhost:8010');
  } finally {
    if (previous === undefined) delete process.env.API_URL;
    else process.env.API_URL = previous;
  }
});

test('next.config.js never manufactures a backend host', () => {
  const configPath = path.join(WEB_ROOT, 'next.config.js');
  const source = require('node:fs').readFileSync(configPath, 'utf8');
  assert.doesNotMatch(
    source,
    /API_URL\s*\|\|\s*['"]http/,
    'next.config.js must not fall back to a hardcoded host: that default made the ' +
      'fail-fast in lib/api-host.ts unreachable.',
  );
});

test('the credential paths use the required host, not a fallback', () => {
  const fs = require('node:fs');
  for (const file of ['lib/auth.ts', 'lib/learning-entry.ts']) {
    const source = fs.readFileSync(path.join(WEB_ROOT, file), 'utf8');
    assert.match(source, /requireApiHost\(/, `${file} must use requireApiHost`);
    assert.doesNotMatch(
      source,
      /localhost:8000/,
      `${file} must not fall back to a guessed port`,
    );
  }
});

/*
 * The rest of this file guards the same defect in the four other places that
 * used to hardcode port 8000: the stories proxy, the browser API client, the
 * WebSocket client, the native auth client and the mobile capture harness.
 */

const fs = require('node:fs');
const { spawnSync } = require('node:child_process');

// `@/...` is a tsconfig path alias. node:test resolves modules itself, so map it
// to the frontend root for the duration of a load.
function withPathAliases(fn) {
  const originalResolve = Module._resolveFilename;
  Module._resolveFilename = function patched(request, ...rest) {
    if (!request.startsWith('@/')) return originalResolve.call(this, request, ...rest);
    const base = path.join(WEB_ROOT, request.slice(2));
    // sucrase compiles TypeScript on require, but the alias carries no extension.
    for (const candidate of [base, `${base}.ts`, `${base}.tsx`, path.join(base, 'index.ts')]) {
      try {
        return originalResolve.call(this, candidate, ...rest);
      } catch {
        // try the next candidate
      }
    }
    return originalResolve.call(this, base, ...rest);
  };
  try {
    return fn();
  } finally {
    Module._resolveFilename = originalResolve;
  }
}

function loadFresh(relativePath) {
  const p = path.join(WEB_ROOT, relativePath);
  delete require.cache[require.resolve(p)];
  return require(p);
}

function withEnv(values, fn) {
  const previous = {};
  for (const [key, value] of Object.entries(values)) {
    previous[key] = process.env[key];
    if (value === undefined) delete process.env[key];
    else process.env[key] = value;
  }
  try {
    return fn();
  } finally {
    for (const [key, value] of Object.entries(previous)) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
  }
}

test('no credentialed path falls back to a guessed port', () => {
  const files = [
    'pages/api/proxy/stories/[...params].ts',
    'services/api.ts',
    'services/websocket.ts',
    'lib/native-auth.ts',
    'scripts/capture-mobile-states.mjs',
  ];
  for (const file of files) {
    const source = fs.readFileSync(path.join(WEB_ROOT, file), 'utf8');
    assert.doesNotMatch(
      source,
      /(\|\||return|=)\s*['"`](?:https?|wss?):\/\/localhost:8000/,
      `${file} must not default to port 8000, which belongs to a different application`,
    );
  }
});

test('the stories proxy requires a configured host', () => {
  const source = fs.readFileSync(
    path.join(WEB_ROOT, 'pages/api/proxy/stories/[...params].ts'),
    'utf8',
  );
  assert.match(source, /requireApiHost\(/);
});

test('an unconfigured browser bundle talks to this origin, not port 8000', () => {
  withEnv(
    { NEXT_PUBLIC_API_BASE_URL: undefined, NEXT_PUBLIC_API_URL: undefined },
    () => {
      const { resolveBrowserApiBaseUrl } = withPathAliases(() => loadFresh('services/api.ts'));
      assert.equal(resolveBrowserApiBaseUrl(), '/api/backend');
    },
  );
});

test('an unconfigured WebSocket follows this page, and says so off-browser', () => {
  withEnv(
    {
      NEXT_PUBLIC_WS_URL: undefined,
      NEXT_PUBLIC_API_BASE_URL: undefined,
      NEXT_PUBLIC_API_URL: undefined,
    },
    () => {
      const { resolveWebSocketBaseUrl } = withPathAliases(() => loadFresh('services/websocket.ts'));

      assert.throws(() => resolveWebSocketBaseUrl(), (error) => {
        assert.match(error.message, /No WebSocket host is configured/);
        assert.doesNotMatch(error.message, /localhost:8000/);
        return true;
      });

      globalThis.window = { location: { protocol: 'https:', host: 'atelier.example' } };
      try {
        assert.equal(resolveWebSocketBaseUrl(), 'wss://atelier.example');
      } finally {
        delete globalThis.window;
      }
    },
  );
});

test('native authentication refuses an unset host instead of guessing one', () => {
  withEnv(
    { NEXT_PUBLIC_API_BASE_URL: undefined, NEXT_PUBLIC_API_URL: undefined },
    () => {
      const { nativeApiBaseUrl } = withPathAliases(() => loadFresh('lib/native-auth.ts'));
      assert.throws(() => nativeApiBaseUrl(), (error) => {
        assert.match(error.message, /NEXT_PUBLIC_API_BASE_URL is not set/);
        assert.doesNotMatch(error.message, /localhost:8000/);
        return true;
      });
    },
  );
  withEnv(
    { NEXT_PUBLIC_API_BASE_URL: 'http://localhost:8010', NEXT_PUBLIC_API_URL: undefined },
    () => {
      const { nativeApiBaseUrl } = withPathAliases(() => loadFresh('lib/native-auth.ts'));
      assert.equal(nativeApiBaseUrl(), 'http://localhost:8010/api/v1');
    },
  );
});

/*
 * QA defect D-8: `capture:mobile` used to register a learner against port 8000
 * and seed a database chosen independently from .env. Authenticated capture now
 * requires both targets explicitly; CI's public static capture requires neither.
 */
function runCapture(env) {
  return spawnSync(process.execPath, [path.join(WEB_ROOT, 'scripts/capture-mobile-states.mjs')], {
    cwd: WEB_ROOT,
    encoding: 'utf8',
    timeout: 30000,
    env: {
      ...process.env,
      API_URL: undefined,
      CAPTURE_DATABASE_URL: undefined,
      // Never let a guard regression actually start a browser from this test.
      CHROME_PATH: path.join(WEB_ROOT, 'no-such-chrome-binary'),
      CAPTURE_DIR: path.join(require('node:os').tmpdir(), `api-host-test-${Date.now()}`),
      ...env,
    },
  });
}

test('an authenticated capture refuses to guess the backend', () => {
  const result = runCapture({});
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /API_URL is not set/);
});

test('an authenticated capture refuses an implicit seeder database', () => {
  const result = runCapture({ API_URL: 'http://localhost:8010' });
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /CAPTURE_DATABASE_URL is not set/);
});

test('the public static capture still runs without either target', () => {
  const result = runCapture({ CAPTURE_FRAMES: 'mobile-primitives-static' });
  // It gets past both guards and dies on the deliberately missing browser.
  assert.doesNotMatch(result.stderr, /API_URL is not set/);
  assert.doesNotMatch(result.stderr, /CAPTURE_DATABASE_URL is not set/);
  assert.match(result.stderr, /no-such-chrome-binary/);
});
