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

// QA-FORGE (2026-10-03): the owner (German, A1) met «Correct» (English) and
// «À corriger» (French) as two drop zones holding «Hierhin». A judgement is now
// one question and two answers, both in the learner's language.
const { isJudgementLabels, judgementLabel, judgementQuestion } = require('./classification-copy.ts');

test('a judgement reads in one language: German, English, French', () => {
  assert.equal(judgementLabel('Correct', 'de'), 'Stimmt so');
  assert.equal(judgementLabel('À corriger', 'de'), 'Muss korrigiert werden');
  assert.equal(judgementLabel('Correct', 'en'), 'Correct');
  assert.equal(judgementLabel('À corriger', 'en'), 'Needs fixing');
  assert.equal(judgementLabel('Correct', 'fr'), 'Correcte');
  assert.equal(judgementLabel('À corriger', 'fr'), 'À corriger');
  assert.equal(judgementQuestion('de'), 'Ist der Satz richtig?');
  // The server's own table wins over the floor.
  assert.equal(judgementLabel('Correct', 'de', { de: { Correct: 'Passt' } }), 'Passt');
  assert.ok(isJudgementLabels(['Correct', 'À corriger']));
  assert.ok(!isJudgementLabels(['present condition', 'future result']));
});

test('the séance draws a judgement as answer buttons, never drop zones', () => {
  const fs = require('node:fs');
  const path = require('node:path');
  const page = fs.readFileSync(path.join(__dirname, '..', 'pages', 'atelier.tsx'), 'utf8');
  const panel = page.slice(page.indexOf('function RecognizePanel('), page.indexOf('function TransformPanel('));
  assert.doesNotMatch(panel, /EpCases/);
  assert.doesNotMatch(panel, /place_here/);
  assert.match(panel, /judgementLabel\(label, cueLanguage, item\.label_l10n\)/);
});
