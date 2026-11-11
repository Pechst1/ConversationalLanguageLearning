// node --test e2e/lib/verdict-timeline.test.mjs
//
// `one-verdict-never-reversed` keys a verdict to the item it answers. The frames below are
// main's season walk of 10 Nov 2026 (season-en, day 2, d2-35 … d2-37): a miss on 12/13, its
// sheet still leaving while 13/13 was on screen, then 13/13 answered with help.
import assert from 'node:assert/strict';
import { test } from 'node:test';

import { itemCounter, reversed, trackVerdicts } from './verdict-timeline.mjs';

const walk = () => ({ day: 2, questionSig: '', questionCounter: null, stepCaptions: [], timelines: new Map() });
const frame = (text, states = []) => ({ text, graded: states.map((state) => ({ state, text: '' })), epFeedback: [] });

const Q12 = 'Step 11 of 11 12/13 Recall · Step 11 of 11 Once more offre Masculine or feminine? masculine feminine Check';
const Q13 = 'Step 11 of 11 13/13 Recall · Step 11 of 11 Once more une offre What does it mean? jewel Thursday offer Check';

function play(frames) {
  const w = walk();
  for (const f of frames) trackVerdicts(w, f, 'choice');
  return [...w.timelines.values()].map(reversed);
}

test('the item counter is read off the screen', () => {
  assert.equal(itemCounter(Q12), '12/13');
  assert.equal(itemCounter('Step 2 of 11 Le Mistral'), null);
});

test('a miss leaving the screen is not the next item’s verdict', () => {
  const timelines = play([
    frame(Q12),
    frame(`${Q12} Not yet`, ['wrong']),
    frame(`${Q13} Not yet`, ['wrong']), // the sheet of 12/13 still sliding out
    frame(`${Q13} Correct, with help`, ['supported']), // answered without a bare frame between
  ]);
  assert.ok(timelines.every((t) => !t.flips), JSON.stringify(timelines));
  assert.deepEqual(timelines.map((t) => t.distinct), [['wrong'], ['supported']]);
});

test('a verdict that really changes on one item is still caught', () => {
  const [timeline] = play([frame(Q12), frame(`${Q12} Not yet`, ['wrong']), frame(`${Q12} Correct`, ['correct'])]);
  assert.equal(timeline.flips, true);
});
