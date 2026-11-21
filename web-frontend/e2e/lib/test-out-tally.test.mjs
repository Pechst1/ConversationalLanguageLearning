// node --test e2e/lib/test-out-tally.test.mjs
//
// #954: the frames of the walk of 20 Nov 2026 (a1-de-fresh, day 2): items 1 and 2 right,
// the own sentence «Noch nicht», then «3 von 3 richtig, der eigene Satz inklusive».
import assert from 'node:assert/strict';
import { test } from 'node:test';

import { newTestOutTally, readTestOut, resultCount } from './test-out-tally.mjs';

const item = (verdict) => ({ testOut: true, forgeHead: 1, forgeResult: '', epFeedback: verdict ? [{ verdict }] : [] });
const result = (text) => ({ testOut: false, forgeHead: 0, forgeResult: text, epFeedback: [] });
const seance = (verdict) => ({ testOut: false, forgeHead: 1, forgeResult: '', epFeedback: verdict ? [{ verdict }] : [] });

function play(frames) {
  const tally = newTestOutTally();
  return frames.map(([s, key]) => readTestOut(tally, s, key)).filter(Boolean);
}

test('the result count is read in every chrome language', () => {
  assert.deepEqual(resultCount('3 von 3 richtig, der eigene Satz inklusive.'), [3, 3]);
  assert.deepEqual(resultCount('2 of 3 right. Your practice picks up at level 3.'), [2, 3]);
  assert.deepEqual(resultCount('2 sur 3. Ton entraînement reprend au niveau 3.'), [2, 3]);
});

test('an item shown «not yet» counted in «3 von 3 richtig» is a finding', () => {
  const checks = play([
    [item(), 'Tu es sérieuse ?'], [item('correct'), 'Tu es sérieuse ?'],
    [item(), 'Je es français.'], [item('correct'), 'Je es français.'],
    [item(), 'Sie (alle) sind müde.'], [item('wrong'), 'Sie (alle) sind müde.'],
    [result('3 von 3 richtig, der eigene Satz inklusive.'), ''],
  ]);
  assert.equal(checks.length, 1);
  assert.equal(checks[0].ok, false);
  assert.match(checks[0].detail, /Sie \(alle\) sind müde/);
});

test('the same miss counted as a miss is consistent', () => {
  const checks = play([
    [item('correct'), 'a'], [item('correct'), 'b'], [item('wrong'), 'c'],
    [result('2 von 3 richtig. Dein Training geht auf Stufe 5 weiter.'), ''],
  ]);
  assert.deepEqual(checks.map((c) => c.ok), [true]);
});

test('a séance miss before the rule check is not one of its items', () => {
  const checks = play([
    [seance('wrong'), 'x'],
    [item('correct'), 'a'], [item('correct'), 'b'], [item('correct'), 'c'],
    [result('3 von 3 richtig, der eigene Satz inklusive.'), ''],
    [result('3 von 3 richtig, der eigene Satz inklusive.'), ''],
  ]);
  assert.deepEqual(checks.map((c) => c.ok), [true], 'checked once per result');
});

test('an item keeps its first verdict (a mended line stays the miss it was)', () => {
  const checks = play([
    [item('wrong'), 'c'], [item('correct'), 'c'], [item('correct'), 'a'], [item('correct'), 'b'],
    [result('3 von 3 richtig'), ''],
  ]);
  assert.equal(checks[0].ok, false);
});
