// node --test components/epreuve/forge-word-ceiling-853.test.js
//
// #853 (live walk 17 Nov, A1.1 day 36): La Forge's sentence item «4–10 words». A
// 12-word line read «12 of 4–10 words», Check stayed disabled (#574: the ceiling is a
// rule, lib/word-range.ts) and nothing said to shorten the sentence. The counter is the
// one place the rule speaks: above the ceiling it says what to do, in every language.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (typeof request === 'string' && request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

const { epreuveCopy, wordRangeState, wordRangeText } = require('./epreuve-copy.ts');
const { withinWordRange } = require('@/lib/word-range.ts');

const LINE = 'J emporte un livre, une pomme et des clés pour la sortie.';
const PAGE = fs.readFileSync(path.join(WEB_ROOT, 'pages/atelier.tsx'), 'utf8');

test('#853 · «12 of 4–10 words» with Check held says to shorten the sentence', () => {
  // The walk's line: 12 words for a 4–10 item, which the page refuses to check.
  assert.equal(withinWordRange(LINE, 10), false, 'Check waits for the line to be under the ceiling');
  const en = wordRangeText(epreuveCopy('en'), 12, 4, 10);
  assert.match(en, /^12 of 4–10 words/, 'the counter itself stays');
  assert.match(en, /Max 10 words/, `the counter gives no reason Check is disabled: «${en}»`);
  assert.match(en, /shorten/i);
  assert.match(wordRangeText(epreuveCopy('de'), 12, 4, 10), /Höchstens 10 Wörter/);
  assert.match(wordRangeText(epreuveCopy('fr'), 12, 4, 10), /10 mots au plus/);
  assert.equal(wordRangeState(12, 4, 10), 'over', 'and it is drawn emphatic');
});

test('#853 · an item with a ceiling and no floor says it too', () => {
  const en = wordRangeText(epreuveCopy('en'), 12, null, 10);
  assert.match(en, /Max 10 words/, `a ceiling without a floor still holds Check: «${en}»`);
  assert.equal(wordRangeState(12, null, 10), 'over');
});

test('#853 · inside the range, or at the ceiling, the counter is only a count', () => {
  for (const [count, max] of [[10, 10], [7, 10], [0, 10]]) {
    const en = wordRangeText(epreuveCopy('en'), count, 4, max);
    assert.equal(en, `${count} of 4–${max} words`);
  }
  assert.equal(wordRangeText(epreuveCopy('en'), 30, null, null), '30 words', 'no ceiling, nothing to say');
});

test('#853 · both of La Forge\'s counters are drawn from wordRangeText', () => {
  assert.match(PAGE, /\{wordRangeText\(t, wordCount\(answer\), item\.min_words, item\.max_words\)\}/);
  assert.match(PAGE, /\{wordRangeText\(t, wordCount\(answer\), produce\.min_words, produce\.max_words\)\}/);
});
