// node --test components/epreuve/forge-word-ceiling-853.test.js
//
// #853 (live walk 17 Nov, A1.1 day 36): La Forge's sentence item «4–10 words». A
// 12-word line read «12 of 4–10 words», Check stayed disabled (#574: the ceiling is a
// rule, lib/word-range.ts) and nothing said to shorten the sentence. Where the ceiling
// holds Check (sentence, conversation), the counter says why; where none holds (the
// produce paragraph, a spoken line) it says nothing (review of #861).

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

const copyModule = require('./epreuve-copy.ts');
const wordRange = require('@/lib/word-range.ts');

const { epreuveCopy, wordRangeState, wordRangeText } = copyModule;
const LINE = 'J emporte un livre, une pomme et des clés pour la sortie.';
const PARAGRAPH = Array.from({ length: 150 }, () => 'mot').join(' ');
const PAGE = fs.readFileSync(path.join(WEB_ROOT, 'pages/atelier.tsx'), 'utf8');

/** What the sentence item's counter reads: the count, then why Check waits (if it does). */
function sentenceCounter(lang, round, text, min, max) {
  const copy = epreuveCopy(lang);
  const count = wordRange.wordsOf(text);
  const over = typeof copyModule.wordCeilingText === 'function' ? copyModule.wordCeilingText(copy, round, text, max) : '';
  return `${wordRangeText(copy, count, min, max)}${over ? ` · ${over}` : ''}`;
}

const slice = (from, to) => PAGE.slice(PAGE.indexOf(from), PAGE.indexOf(to, PAGE.indexOf(from)));

test('#853 · «12 of 4–10 words» with Check held says to shorten the sentence', () => {
  assert.equal(wordRange.withinWordRange(LINE, 10), false, 'Check waits for the line to be under the ceiling');
  const en = sentenceCounter('en', 'sentence', LINE, 4, 10);
  assert.match(en, /^12 of 4–10 words/, 'the counter itself stays');
  assert.match(en, /Max 10 words/, `the counter gives no reason Check is disabled: «${en}»`);
  assert.match(en, /shorten/i);
  assert.match(sentenceCounter('de', 'sentence', LINE, 4, 10), /Höchstens 10 Wörter/);
  assert.match(sentenceCounter('fr', 'sentence', LINE, 4, 10), /10 mots au plus/);
  assert.match(sentenceCounter('en', 'conversation', LINE, 4, 10), /Max 10 words/, 'a conversation line is held the same way');
  assert.equal(wordRangeState(12, 4, 10), 'over', 'and it is drawn emphatic');
  assert.equal(wordRangeState(12, null, 10), 'over', 'a ceiling without a floor holds Check too');
});

test('#853 · the sentence item\'s counter and Check read one ceiling rule', () => {
  const ladder = slice('function OutputLadderPanel(', 'function ProducePanel(');
  assert.match(ladder, /wordCeilingText\(t, round, answer, item\.max_words\)/, 'the sentence counter never says why Check is disabled');
  const gate = slice('function drillAnswerIsReady(', '\n}\n');
  assert.match(gate, /heldByCeiling\(round, String\(currentAnswers\.text \|\| ''\), item\.max_words\)/, 'Check and the counter read one rule');
});

test('#853 · no rule is said where none holds: the produce paragraph, a spoken line, inside the range', () => {
  const words = (n) => Array.from({ length: n }, () => 'mot').join(' ');
  assert.equal(sentenceCounter('en', 'produce', PARAGRAPH, 60, 140), '150 of 60–140 words', 'produce has no ceiling: Check stays enabled');
  assert.equal(sentenceCounter('en', 'speak', LINE, 4, 10), '12 of 4–10 words', 'a spoken line is the recogniser\'s');
  for (const n of [10, 7, 0]) assert.equal(sentenceCounter('en', 'sentence', words(n), 4, 10), `${n} of 4–10 words`);
  assert.equal(sentenceCounter('en', 'sentence', words(30), null, null), '30 words', 'no ceiling, nothing to say');
  const produce = slice('function ProducePanel(', '\n}\n');
  assert.doesNotMatch(produce, /wordCeilingText/, 'the paragraph counter is only a count');
});
