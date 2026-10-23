// node --test components/epreuve/finish-confirm.test.js
//
// #88 — «Stop here?» stays open until it is answered. It used to revert by
// itself after 4 s, so the second tap landed on the reverted button.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');

require(path.resolve(__dirname, '../../node_modules/sucrase/register/ts'));
const { nextFinishState } = require('./finish-confirm.ts');

const step = (state, event, partial = true) => nextFinishState(state, event, partial);

test('the first tap asks, the second answers, and nothing in between closes the ask', () => {
  let state = { confirming: false };
  ({ state } = step(state, 'tap'));
  assert.equal(state.confirming, true);
  // Re-renders and the séance moving on are not events that close the ask.
  for (let i = 0; i < 5; i += 1) ({ state } = step(state, 'partial_changed', true));
  assert.equal(state.confirming, true, 'still asking');
  const second = step(state, 'tap');
  assert.equal(second.finish, true, 'the second tap lands on the confirmation');
  assert.equal(second.state.confirming, false);
});

test('Escape or a séance that is no longer partial closes the ask without finishing', () => {
  const asking = { confirming: true };
  assert.deepEqual(step(asking, 'escape'), { state: { confirming: false }, finish: false });
  assert.deepEqual(step(asking, 'partial_changed', false), { state: { confirming: false }, finish: false });
});

test('a complete séance stops on the first tap', () => {
  assert.deepEqual(step({ confirming: false }, 'tap', false), { state: { confirming: false }, finish: true });
});

test('the top bar runs on that state machine and has no timer that closes the ask', () => {
  const source = fs.readFileSync(path.join(__dirname, 'Epreuve.tsx'), 'utf8');
  const topBar = source.slice(source.indexOf('export function EpTopbar'), source.indexOf('/* ---------- step label'));
  assert.match(topBar, /nextFinishState/);
  assert.doesNotMatch(topBar, /setTimeout/);
});
