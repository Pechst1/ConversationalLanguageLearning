// The walk server runs with production's story flags (render.yaml), so CI exercises the
// scene record, the day contract, its re-ask and the stand-in page as production does.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import test from 'node:test';

import { REPO_ROOT, productionStoryFlags, walkApiEnv } from './stack.mjs';

const manifest = readFileSync(path.join(REPO_ROOT, 'render.yaml'), 'utf8');

// Read here on its own terms, not through the parser under test: every STORY_* key the
// manifest names, anywhere, with the literal on the line after it.
function storyKeysInManifest() {
  const found = {};
  const re = /key:\s*(STORY_[A-Z0-9_]+)\s*\n\s*value:\s*"?([^"\n]*)"?/g;
  for (const m of manifest.matchAll(re)) found[m[1]] = m[2].trim();
  for (const m of manifest.matchAll(/\bSTORY_[A-Z0-9_]+\b/g)) if (!(m[0] in found)) found[m[0]] = undefined;
  return found;
}

test('the walk API is started with every STORY_* flag render.yaml sets, at its value', () => {
  const expected = storyKeysInManifest();
  assert.ok(Object.keys(expected).includes('STORY_SCENE_RECORD'), 'render.yaml no longer names STORY_SCENE_RECORD');
  const env = walkApiEnv({ dbUrl: 'postgresql+psycopg2://x/atelier_walk_1', web: 'http://localhost:21001', base: {} });
  for (const [key, value] of Object.entries(expected)) {
    assert.ok(key in env, `render.yaml sets ${key}; the walk stack does not pass it on`);
    assert.equal(env[key], value, `${key}: production «${value}», the walk «${env[key]}»`);
  }
});

test("production's flags win over a shell that set them otherwise", () => {
  const env = walkApiEnv({ dbUrl: 'x', web: 'http://localhost:1', base: { STORY_SCENE_RECORD: 'false', OTHER: '1' } });
  assert.equal(env.STORY_SCENE_RECORD, 'true');
  assert.equal(env.OTHER, '1');
});

test('a manifest whose services disagree on a story flag is refused', () => {
  const two = '  - key: STORY_X\n    value: "true"\n  - key: STORY_X\n    value: "false"\n';
  assert.throws(() => productionStoryFlags(two), /STORY_X/);
  assert.deepEqual(productionStoryFlags('  - key: STORY_Y\n    value: medium\n'), { STORY_Y: 'medium' });
});

// Integration 2026-11-22: a walk made one real speech call — the environment's proxy injects a
// real credential even when the stack sets a fake key. The walk API speaks to a local fake and
// has no proxy to reach a provider through.
test('the walk API synthesises speech on a local fake and has no proxy to a provider', () => {
  const base = { HTTPS_PROXY: 'http://proxy:1', https_proxy: 'http://proxy:1', HTTP_PROXY: 'http://proxy:1', http_proxy: 'x', ALL_PROXY: 'x', all_proxy: 'x', NO_PROXY: 'example.org', TTS_PROVIDER: 'elevenlabs' };
  const env = walkApiEnv({ dbUrl: 'x', web: 'http://localhost:1', base, speech: 'http://127.0.0.1:23456' });
  assert.equal(env.OPENAI_API_BASE, 'http://127.0.0.1:23456/v1');
  assert.equal(env.TTS_PROVIDER, 'openai');
  assert.equal(env.ELEVENLABS_API_KEY, '');
  for (const key of ['HTTPS_PROXY', 'https_proxy', 'HTTP_PROXY', 'http_proxy', 'ALL_PROXY', 'all_proxy']) assert.ok(!(key in env), key);
  assert.match(env.NO_PROXY, /127\.0\.0\.1/);
  assert.match(env.no_proxy, /localhost/);
});

test('the fake speech server answers a line with a short MP3 and nothing else', async () => {
  const { startFakeSpeech } = await import('./stack.mjs');
  const fake = await startFakeSpeech();
  try {
    const spoken = await fetch(`${fake.url}/v1/audio/speech`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ input: 'Bonjour.', voice: 'nova', model: 'x' }) });
    assert.equal(spoken.status, 200);
    assert.equal(spoken.headers.get('content-type'), 'audio/mpeg');
    const bytes = new Uint8Array(await spoken.arrayBuffer());
    assert.ok(bytes.length > 100 && bytes[0] === 0xff && (bytes[1] & 0xe0) === 0xe0, 'an MPEG audio frame');
    const other = await fetch(`${fake.url}/v1/chat/completions`, { method: 'POST', body: '{}' });
    assert.equal(other.status, 404);
    assert.equal(fake.calls(), 1);
  } finally {
    await fake.stop();
  }
});
