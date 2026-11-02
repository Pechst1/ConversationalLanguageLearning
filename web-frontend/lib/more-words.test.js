// node --test lib/more-words.test.js
//
// Owner request, 2 Nov 2026: more new words a day, and a short honest line on
// how much sooner they cover the goal's words. The figure is the server's
// (`goal_estimate.days_sooner`); this file only words it.

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

const mw = require('./more-words.ts');

test('the line says how much sooner, in weeks from two weeks on', () => {
  assert.equal(
    mw.goalLine('de', { words: 20, days_sooner: 21 }, 'A2.2'),
    'Mit 20 Wörtern am Tag hast du den Wortschatz für A2 etwa 3 Wochen früher.',
  );
  assert.equal(
    mw.goalLine('fr', { words: 20, days_sooner: 21 }, 'A2.2'),
    'Avec 20 mots par jour, tu as le vocabulaire du niveau A2 environ 3 semaines plus tôt.',
  );
  assert.equal(
    mw.goalLine('en', { words: 20, days_sooner: 21 }, 'A2.2'),
    'At 20 words a day, you’ll have the A2 vocabulary about 3 weeks sooner.',
  );
  assert.equal(mw.goalLine('de', { words: 25, days_sooner: 10 }, 'A2.1'),
    'Mit 25 Wörtern am Tag hast du den Wortschatz für A2.1 etwa 10 Tage früher.');
  assert.equal(mw.soonerLabel(1, 'de'), 'einen Tag');
});

test('no goal or no figure: no number, only that more words get there sooner', () => {
  assert.equal(mw.goalLine('de', { words: 25, days_sooner: 10 }, null), 'Mehr Wörter am Tag bringen dich schneller ans Ziel.');
  assert.equal(mw.goalLine('de', { words: 25, days_sooner: null }, 'A2.2'), 'Mehr Wörter am Tag bringen dich schneller ans Ziel.');
  assert.equal(mw.goalLine('fr', { words: 25 }, null), 'Plus de mots par jour te rapprochent plus vite de ton objectif.');
  assert.doesNotMatch(mw.goalLine('en', { words: 25, days_sooner: 0 }, 'A2.2'), /\d/);
});

test('the «Noch 5» offer, until the day’s extras are spent', () => {
  const pace = { step: 5, can_add_more: true, goal: 'A2.2', more: { words: 25, days_sooner: 14 } };
  assert.deepEqual(mw.extraWordsOffer(pace, 'de'), {
    label: 'Noch 5 neue Wörter',
    line: 'Mit 25 Wörtern am Tag hast du den Wortschatz für A2 etwa 2 Wochen früher.',
  });
  assert.equal(mw.extraWordsOffer(pace, 'fr').label, 'Encore 5 nouveaux mots');
  assert.equal(mw.extraWordsOffer({ ...pace, can_add_more: false }, 'de'), null);
  assert.equal(mw.extraWordsOffer(null, 'de'), null);
});

test('Réglages: only a faster choice speaks', () => {
  const pace = {
    words_per_day: 20,
    goal: 'A2.2',
    steps: [
      { words: 10, days_sooner: null },
      { words: 20, days_sooner: null },
      { words: 30, days_sooner: 17 },
    ],
  };
  assert.equal(mw.settingsGoalLine('de', 20, pace), null);
  assert.equal(mw.settingsGoalLine('de', 10, pace), null);
  assert.equal(mw.settingsGoalLine('de', 30, pace), 'Mit 30 Wörtern am Tag hast du den Wortschatz für A2 etwa 2 Wochen früher.');
  // A number of its own has no figure of the server's: no number is printed.
  assert.equal(mw.settingsGoalLine('de', 27, pace), 'Mehr Wörter am Tag bringen dich schneller ans Ziel.');
});
