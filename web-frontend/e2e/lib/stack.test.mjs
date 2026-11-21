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
