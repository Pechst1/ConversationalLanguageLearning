// node --test lib/day-session.test.js
//
// Round 3 (owner, 2026-10-14): the day as one sequence — Szene, Wörter,
// Grammatik, Fertig — and the Tempo sheet's rows.

const assert = require('node:assert/strict');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

const ds = require('./day-session.ts');
const dp = require('./day-plan.ts');

function session(states, overrides = {}) {
  const [scene, words, grammar, finish] = states;
  return {
    pace: 'normal',
    steps: [
      { kind: 'scene', state: scene, minutes: scene === 'done' ? 0 : 8, href: null },
      { kind: 'words', state: words, minutes: words === 'done' ? 0 : 8, href: '/vocabulary/review?day=1', count: 32, new_left: 20, reviews: 12 },
      { kind: 'grammar', state: grammar, minutes: grammar === 'done' ? 0 : 5, href: '/atelier?mode=forge&from=day', count: 12 },
      { kind: 'finish', state: finish, minutes: 0, href: '/fertig' },
    ],
    next_kind: ['scene', 'words', 'grammar'].find((kind, index) => states[index] === 'next') ?? null,
    minutes_left: 21,
    done: finish === 'done',
    tally: { scenes: 1, words: 20, exercises: 12 },
    more_words: 10,
    more_minutes: 4,
    more_href: '/vocabulary/review?more=10',
    ...overrides,
  };
}

test('the programme is four rows with their minutes, in the learner’s language', () => {
  const rows = ds.sessionRows(session(['next', 'todo', 'todo', 'todo']), 'de');
  assert.deepEqual(rows.map((row) => [row.label, row.meta]), [
    ['Szene', '8 Min.'],
    ['32 Wörter', '20 neu · 12 zum Wiederholen · 8 Min.'],
    ['Grammatik', '5 Min.'],
    ['Fertig', ''],
  ]);
  assert.deepEqual(rows.map((row) => row.shape), ['story', 'reward', 'action', 'done']);
  assert.equal(ds.sessionRows(session(['next', 'todo', 'todo', 'todo']), 'fr')[1].label, '32 mots');
});

test('a news day opens with Le Papier', () => {
  const rows = ds.sessionRows(session(['next', 'todo', 'todo', 'todo']), 'de', { papier: true });
  assert.equal(rows[0].label, 'Le Papier');
});

test('a done step drops its minutes', () => {
  const rows = ds.sessionRows(session(['done', 'next', 'todo', 'todo']), 'de');
  assert.equal(rows[0].meta, '');
});

test('the journey card starts the scene; after it the one button names the next step', () => {
  assert.equal(ds.sessionNextAction(session(['next', 'todo', 'todo', 'todo']), 'de'), null);
  assert.deepEqual(ds.sessionNextAction(session(['done', 'next', 'todo', 'todo']), 'de'), {
    kind: 'words',
    label: 'Weiter: 32 Wörter',
    meta: '20 neu · 12 zum Wiederholen · 8 Min.',
    href: '/vocabulary/review?day=1',
  });
  assert.equal(ds.sessionNextAction(session(['done', 'done', 'next', 'todo']), 'en').label, 'Next: grammar');
  assert.equal(ds.sessionNextAction(session(['done', 'done', 'done', 'done']), 'de'), null);
});

test('only a finished day offers ten more words', () => {
  assert.equal(ds.sessionMore(session(['done', 'next', 'todo', 'todo']), 'de'), null);
  assert.deepEqual(ds.sessionMore(session(['done', 'done', 'done', 'done']), 'de'), {
    label: 'Noch 10 Wörter',
    meta: '4 Min.',
    href: '/vocabulary/review?more=10',
  });
});

test('the mark’s four shapes are the four steps', () => {
  const mark = ds.sessionMarkState(session(['done', 'next', 'todo', 'todo']), 'de');
  assert.deepEqual(mark.groups, { scene: 'done', recall: 'active', respond: 'todo', resolution: 'todo' });
  assert.equal(mark.done, 1);
  assert.equal(mark.total, 4);
});

test('the Tempo sheet says what each pace holds, costs and reaches', () => {
  const options = [
    { pace: 'ruhig', words: 10, rules_per_week: 3, exercises: 12, minutes_today: 18, minutes_week_8: 21, reviews_week_8: 28, goal_weeks: 15.1 },
    { pace: 'normal', words: 20, rules_per_week: 5, exercises: 12, minutes_today: 23, minutes_week_8: 28, reviews_week_8: 57, goal_weeks: 10.5 },
    { pace: 'schnell', words: 40, rules_per_week: 8, exercises: 17, minutes_today: 35, minutes_week_8: 43, reviews_week_8: 114, goal_weeks: 8.1 },
  ];
  const rows = ds.paceRows(options, 'A1.2', 'de');
  assert.deepEqual(rows.map((row) => row.name), ['Ruhig', 'Normal', 'Schnell']);
  assert.equal(rows[1].detail, '20 Wörter · 5 Regeln pro Woche');
  assert.equal(rows[1].minutes, '≈ 23 Min.');
  assert.equal(rows[0].goal, 'A1 in ≈ 3½ Monaten');
  assert.equal(rows[1].goal, 'A1 in ≈ 11 Wochen');
  assert.equal(rows[2].goal, 'A1 in ≈ 8 Wochen');
  assert.equal(ds.paceNote(options, 'de'), 'Wörter kommen zur Wiederholung zurück. Nach 8 Wochen dauert ein Tag etwa 3 bis 8 Min. länger.');
});

test('the scene’s ending hands on to the words, La Forge’s recap to the words or Fertig', () => {
  const afterScene = dp.handOnAfterScene(session(['next', 'todo', 'todo', 'todo']), 'de');
  assert.equal(afterScene.label, 'Weiter: 32 Wörter');
  assert.equal(afterScene.href, '/vocabulary/review?day=1');
  assert.equal(dp.handOnAfterScene(session(['done', 'done', 'next', 'todo']), 'de').label, 'Weiter: Grammatik');
  assert.equal(dp.handOnAfterGrammar(session(['done', 'next', 'todo', 'todo']), 'de').kind, 'words');
  const finish = dp.handOnAfterGrammar(session(['done', 'done', 'next', 'todo']), 'de');
  assert.deepEqual([finish.kind, finish.label, finish.href], ['finish', 'Fertig für heute', '/fertig']);
});

test('#279 · a deck of new words and reviews names its two halves; one half alone needs no split', () => {
  const both = ds.sessionRows(session(['done', 'next', 'todo', 'todo']), 'en')[1];
  assert.equal(both.label, '32 words');
  assert.equal(both.meta, '20 new · 12 to review · 8 min');
  const only = (words) => {
    const base = session(['done', 'next', 'todo', 'todo']);
    base.steps[1] = { ...base.steps[1], ...words };
    return ds.sessionRows(base, 'fr')[1].meta;
  };
  assert.equal(only({ count: 12, new_left: 0, reviews: 12 }), '8 min');
  assert.equal(only({ count: 20, new_left: 20, reviews: 0 }), '8 min');
});
