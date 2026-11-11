import assert from 'node:assert/strict';
import test from 'node:test';

import { dayPlanVerdict, HAND_ON } from './day-plan.mjs';

const plan = (states, done = false) => ({
  done,
  next_kind: done ? null : 'grammar',
  steps: Object.entries(states).map(([kind, state]) => ({ kind, state })),
});
const fresh = plan({ scene: 'next', grammar: 'todo', words: 'todo', finish: 'todo' });
const doneDay = plan({ scene: 'done', grammar: 'done', words: 'done', finish: 'done' }, true);

test('a day that played every planned step and ended at /fertig passes', () => {
  const v = dayPlanVerdict({ plan: fresh, last: doneDay, played: new Set(['scene', 'grammar', 'words', 'finish']), dayEnd: 'fertig' });
  assert.equal(v.ok, true, v.detail);
});

test('a day that stopped at «Scène terminée · Suite : grammaire» fails, naming the steps', () => {
  const v = dayPlanVerdict({ plan: fresh, last: plan({ scene: 'done', grammar: 'next', words: 'todo', finish: 'todo' }), played: new Set(['scene']), dayEnd: 'recap' });
  assert.equal(v.ok, false);
  assert.match(v.detail, /not played: grammar, words, finish/);
  assert.match(v.detail, /not done \(next: grammar\)/);
});

test('steps already done when the day opened are not owed again', () => {
  const resumed = plan({ scene: 'done', grammar: 'done', words: 'next', finish: 'todo' });
  const v = dayPlanVerdict({ plan: resumed, last: doneDay, played: new Set(['words', 'finish']), dayEnd: 'fertig' });
  assert.equal(v.ok, true, v.detail);
});

test('no plan, or no end, is a failure', () => {
  assert.equal(dayPlanVerdict({ plan: null, last: null, played: new Set(), dayEnd: null }).ok, false);
  assert.equal(dayPlanVerdict({ plan: fresh, last: doneDay, played: new Set(['scene', 'grammar', 'words', 'finish']), dayEnd: null }).ok, false);
});

test('the hand-on reads in the three chrome languages, French spacing included', () => {
  for (const label of ['Suite : grammaire', 'Suite : 20 mots', 'Weiter: 20 Wörter', 'Next: grammar']) assert.match(label, HAND_ON);
  for (const label of ['Continuer', 'Next', 'Fertig für heute', 'Suivant']) assert.doesNotMatch(label, HAND_ON);
});
