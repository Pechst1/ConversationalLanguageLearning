// node --test lib/forge-items.test.js
//
// La Forge (WP-S2 × WP-S3): a bank top-up arrives with the forge's `next`
// after the page loaded the séance; it is seated in the page's copy of the set
// and the drill points at it. The séance page wires it (one coherent Épreuve).

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));

const { seatForgeItem, scopeOutputItem, isForgeOutputRound } = require('./forge-items.ts');

const sets = [
  {
    concept_id: 7,
    payload: {
      recognize: { fill: { items: [{ id: 'f1' }, { id: 'f2' }, { id: 'f3' }] }, classify: { items: [] }, word_bank: { items: [] } },
      transform: { items: [{ id: 't1' }] },
      output_ladder: { sentence: { items: [{ id: 's1', example_answer: 'A.' }] } },
    },
  },
];

test('an item already in the set is pointed at, the set untouched', () => {
  const out = seatForgeItem(sets, { concept_id: 7, round: 'recognize', mode: 'fill', item_id: 'f2', item_index: 1 });
  assert.equal(out.sets, sets);
  assert.equal(out.index, 1);
});

test('a bank top-up is appended to its container and pointed at', () => {
  const item = { id: 'f4', prompt: 'Il ___ au café.', correct_answer: 'va' };
  const out = seatForgeItem(sets, { concept_id: 7, round: 'recognize', mode: 'fill', item_id: 'f4', item_index: 3, item });
  assert.notEqual(out.sets, sets, 'a new array: React sees the change');
  assert.deepEqual(out.sets[0].payload.recognize.fill.items.map((i) => i.id), ['f1', 'f2', 'f3', 'f4']);
  assert.equal(out.index, 3);
  assert.equal(sets[0].payload.recognize.fill.items.length, 3, 'the old state is not mutated');

  const sentence = seatForgeItem(sets, {
    concept_id: 7, round: 'sentence', mode: 'sentence', item_id: 's2', item: { id: 's2', example_answer: 'B.' },
  });
  assert.deepEqual(sentence.sets[0].payload.output_ladder.sentence.items.map((i) => i.id), ['s1', 's2']);
  assert.equal(sentence.index, 1);
});

test('without the item (an older server) the server index stands', () => {
  const out = seatForgeItem(sets, { concept_id: 7, round: 'transform', mode: 'rewrite', item_id: 't9', item_index: 4 });
  assert.equal(out.sets, sets);
  assert.equal(out.index, 4);
});

test('an output rung beyond the first item renders that item alone', () => {
  const payload = { output_ladder: { sentence: { items: [{ id: 's1' }, { id: 's2' }] } } };
  assert.equal(scopeOutputItem(payload, 'sentence', 0), payload);
  assert.deepEqual(scopeOutputItem(payload, 'sentence', 1).output_ladder.sentence.items, [{ id: 's2' }]);
  assert.equal(scopeOutputItem(payload, 'recognize', 1), payload);
  assert.equal(isForgeOutputRound('conversation'), true);
});

test('the séance page seats the forge item and scopes output items to their id', () => {
  const page = fs.readFileSync(path.join(WEB_ROOT, 'pages', 'atelier.tsx'), 'utf8');
  assert.match(page, /seatForgeItem\(/);
  assert.match(page, /scopeOutputItem\(/);
  // A forge output rung posts its item id, so each top-up is its own drill.
  assert.match(page, /forgeOutputItemId/);
});
