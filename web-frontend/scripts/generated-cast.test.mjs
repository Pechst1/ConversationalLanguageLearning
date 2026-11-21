import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { checkFreshness, exportCast, renderCast } from './generate-cast.mjs';

test('a changed name in the registry makes the committed cast stale until regenerated', (t) => {
  let cast;
  try {
    cast = exportCast();
  } catch (error) {
    // The frontend CI job has no backend Python; the generated-types job runs this
    // freshness check there with the real environment.
    if (/ModuleNotFoundError|ENOENT|No module named/.test(String(error?.message ?? error))) {
      t.skip(`no backend Python here (${String(error?.message ?? error).split('\n')[0]})`);
      return;
    }
    throw error;
  }
  const committed = readFileSync(new URL('../lib/generated/cast.ts', import.meta.url), 'utf8');
  checkFreshness(renderCast(cast), committed);
  const renamed = {
    people: cast.people.map((person) => (person.id === 'margaux_barman' ? { ...person, name: 'Margot' } : person)),
  };
  const changed = renderCast(renamed);
  assert.match(changed, /margaux_barman: 'Margot'/);
  assert.throws(() => checkFreshness(changed, committed), /stale/);
});

test('the render quotes an apostrophe, and a person with no address says null', () => {
  const rendered = renderCast({
    people: [{
      id: 'x_y',
      name: "L'ami",
      fullName: "L'ami",
      spokenName: "L'ami",
      address: null,
      hasDrawnFace: false,
      firstDay: [1, 'a'],
      tokens: ['ami'],
      spellings: ["L'ami"],
    }],
  });
  assert.match(rendered, /name: 'L\\'ami'/);
  assert.match(rendered, /address: null/);
});
