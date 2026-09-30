const { test } = require('node:test');
const assert = require('node:assert/strict');
require('sucrase/register/ts');
const { classificationCopy, classificationGoal } = require('./classification-copy.ts');

test('B1 classification labels and quoted correction keys display in French', () => {
  assert.equal(classificationCopy('future result', 'fr'), 'conséquence au futur');
  assert.equal(classificationCopy('Vous avez choisi « present condition » ; la réponse est « future result ».', 'fr'),
    'Vous avez choisi « condition au présent » ; la réponse est « conséquence au futur ».');
});

test('display localization keeps stored grading keys and French sentences intact', () => {
  const key = 'imperative result';
  assert.equal(classificationCopy(key, 'fr'), 'conséquence à l’impératif');
  assert.equal(key, 'imperative result');
  assert.equal(classificationCopy('prends ton manteau', 'fr'), 'prends ton manteau');
  assert.equal(classificationCopy(key, 'en'), key);
});

test('classification asks for a category rather than a cloze completion', () => {
  assert.equal(classificationGoal('fr'), 'Classez cette forme.');
});
