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
