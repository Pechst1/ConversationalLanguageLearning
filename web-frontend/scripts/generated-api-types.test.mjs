import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { checkFreshness, exportSchema, renderTypes } from './generate-api-types.mjs';

test('a new backend field makes the committed types stale until regenerated', async (t) => {
  let schema;
  try {
    schema = exportSchema();
  } catch (error) {
    // The frontend CI job has no backend Python; the OpenAPI job runs this
    // freshness check there with the real environment.
    if (/ModuleNotFoundError|ENOENT|No module named/.test(String(error?.message ?? error))) {
      t.skip(`no backend Python here (${String(error?.message ?? error).split('\n')[0]})`);
      return;
    }
    throw error;
  }
  const committed = readFileSync(new URL('../types/generated/api.ts', import.meta.url), 'utf8');
  checkFreshness(await renderTypes(schema), committed);
  schema.components.schemas.TodayEnvelope.properties.e5_new_backend_field = { type: 'string' };
  const changed = await renderTypes(schema);
  assert.match(changed, /e5_new_backend_field/);
  assert.throws(() => checkFreshness(changed, committed), /stale/);
});
