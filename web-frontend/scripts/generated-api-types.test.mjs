import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { checkFreshness, exportSchema, renderTypes } from './generate-api-types.mjs';

test('a new backend field makes the committed types stale until regenerated', async () => {
  const schema = exportSchema();
  const committed = readFileSync(new URL('../types/generated/api.ts', import.meta.url), 'utf8');
  checkFreshness(await renderTypes(schema), committed);
  schema.components.schemas.TodayEnvelope.properties.e5_new_backend_field = { type: 'string' };
  const changed = await renderTypes(schema);
  assert.match(changed, /e5_new_backend_field/);
  assert.throws(() => checkFreshness(changed, committed), /stale/);
});
