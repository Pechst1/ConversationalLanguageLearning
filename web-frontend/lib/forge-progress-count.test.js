// node --test lib/forge-progress-count.test.js
// Walk #90: the séance count stays on the item on screen while it is retried.
const assert = require('node:assert/strict');
const { test } = require('node:test');
require('sucrase/register/ts');
const { seanceCount } = require('./forge-progress.ts');

test('the item on screen is counted, not the one the server names next', () => {
  const forge = { length: 12, answered: 1, next: { position: 1, length: 12, item_id: 'b' } };
  // On item «a» (its feedback, or «Try again»): still 1 of 12.
  assert.deepEqual(seanceCount(forge, 'a'), { n: 1, total: 12 });
  // On the next item: 2 of 12.
  assert.deepEqual(seanceCount(forge, 'b'), { n: 2, total: 12 });
  // Without an item id, the old count stands.
  assert.deepEqual(seanceCount(forge), { n: 2, total: 12 });
  assert.deepEqual(seanceCount({ ...forge, next: { position: 1, length: 12 } }, 'a'), { n: 2, total: 12 });
});
