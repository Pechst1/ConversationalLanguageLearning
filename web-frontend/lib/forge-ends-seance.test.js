// node --test lib/forge-ends-seance.test.js
// #443: «Finish» is the primary only on the séance's last item.
const assert = require('node:assert/strict');
const { test } = require('node:test');
require('sucrase/register/ts');
const { endsTheSeance } = require('./forge-progress.ts');

test('an item with another ahead is never ended by its primary', () => {
  const mid = { mode: 'seance', length: 17, answered: 1, finished: false, next: { position: 1, length: 17 } };
  assert.equal(endsTheSeance(mid), false);
  // Whatever else the view says, a named next item means «Continue».
  assert.equal(endsTheSeance({ ...mid, finished: true }), false);
});

test('the last item, and only it, ends the séance', () => {
  assert.equal(endsTheSeance({ mode: 'seance', length: 17, answered: 17, finished: true, next: null }), true);
  assert.equal(endsTheSeance({ mode: 'seance', finished: false, next: null }), false);
  assert.equal(endsTheSeance({ mode: 'test_out', finished: true, next: null }), false);
  assert.equal(endsTheSeance(null), false);
});
