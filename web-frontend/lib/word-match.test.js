// node --test lib/word-match.test.js
//
// #236 / #146 — the Courrier's word ribbon marked «vendre» as used for «Je préfère
// vendredi» (a substring test). A word is used when the learner wrote that word or a
// real inflection of it, never a longer word that starts the same way.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));

function load() {
  return require(path.join(WEB_ROOT, 'lib/word-match.ts'));
}

test('a longer word that starts like the target is not the target', () => {
  const { targetOccursIn } = load();
  assert.equal(targetOccursIn('vendre', 'Je préfère vendredi'), false);
  assert.equal(targetOccursIn('vendre', 'Bonjour, jeudi ce n\'est pas bon. Je préfère vendredi, parce que la bouillotte est cassée.'), false);
  assert.equal(targetOccursIn('lettre', 'Elle ouvre le lettrage.'), false);
});

test('the word and its regular inflections count', () => {
  const { targetOccursIn } = load();
  for (const text of ['je vends', 'elle a vendu', 'vous vendez', 'Je veux vendre le canapé.', 'Nous vendions des livres.']) {
    assert.equal(targetOccursIn('vendre', text), true, text);
  }
});

test('a noun counts with its article, in the plural and under any accent or case', () => {
  const { targetOccursIn } = load();
  assert.equal(targetOccursIn('la bouillotte', 'Ma BOUILLOTTE est cassée.'), true);
  assert.equal(targetOccursIn('la bouillotte', 'Deux bouillottes sont cassées.'), true);
  assert.equal(targetOccursIn('plusieurs', 'Plusieurs jour sans internet'), true);
  assert.equal(targetOccursIn('préférer', 'Je prefere vendredi'), true);
  assert.equal(targetOccursIn("l'eau", "Je bois de l’eau"), true);
});

test('a short derived form is never another word («être» is not «et»)', () => {
  const { targetOccursIn } = load();
  assert.equal(targetOccursIn('être', 'Pierre et Marie'), false);
  assert.equal(targetOccursIn('être', 'Être ou ne pas être'), true);
});

test('an empty label or text never matches', () => {
  const { targetOccursIn } = load();
  assert.equal(targetOccursIn('', 'bonjour'), false);
  assert.equal(targetOccursIn('vendre', ''), false);
  assert.equal(targetOccursIn(null, undefined), false);
});

test('the mission page asks the word matcher, not a substring', () => {
  const page = fs.readFileSync(path.join(WEB_ROOT, 'pages/missions.tsx'), 'utf8');
  assert.equal(/said\.includes\(/.test(page), false, 'missions.tsx still compares a target to the learner text with includes');
  assert.match(page, /targetOccursIn\(/);
});
