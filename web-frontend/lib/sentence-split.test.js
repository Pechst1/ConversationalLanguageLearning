// node --test lib/sentence-split.test.js
//
// #896: one sentence splitter, on the server and on the device, pinned by one fixture
// (`tests/fixtures/sentence_split_cases.json`, also read by
// `tests/test_sentence_split_896.py`). #893 (walk 18 Nov): La Forge's judge miss read
// «„Tu est française, Margaux ? “ stimmt nicht; richtig ist „Tu es française, Margaux ?»:
// the note splitter cut at every «?», even inside a quotation, and the closing «“.»
// folded to nothing and was dropped.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (typeof request === 'string' && request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const { dedupeNotes, forgeCorrectionNotes } = require('./correction-notes.ts');

const FIXTURE = path.resolve(WEB_ROOT, '..', 'tests', 'fixtures', 'sentence_split_cases.json');
const fixtureCases = () => JSON.parse(fs.readFileSync(FIXTURE, 'utf8')).cases;

// atelier.judgement.should_be (app/services/learner_copy.py), filled with a question.
const SHOULD_BE = {
  de: '„Tu est française, Margaux ?“ stimmt nicht; richtig ist „Tu es française, Margaux ?“.',
  en: '“Tu est française, Margaux ?” is not right; it should be “Tu es française, Margaux ?”.',
  fr: '« Tu est française, Margaux ? » n’est pas correcte ; il faut « Tu es française, Margaux ? ».',
};

test('#896: the device splitter reads every fixture line as the server does', () => {
  const { splitSentences } = require('./sentence-split.ts');
  const cases = fixtureCases();
  assert.ok(cases.length >= 10);
  for (const { text, sentences, why } of cases) {
    assert.deepEqual(splitSentences(text), sentences, why);
  }
});

test('#893/#896: a note is never cut inside its sentences (every fixture line comes back whole)', () => {
  for (const { text, why } of fixtureCases()) {
    assert.deepEqual(dedupeNotes([text]), [text], why);
  }
});

test('#893: a judge miss on a question comes back as sent, closing quote and full stop included', () => {
  for (const [lang, line] of Object.entries(SHOULD_BE)) {
    assert.deepEqual(dedupeNotes([line]), [line], lang);
    assert.deepEqual(forgeCorrectionNotes({ notes_native: [line] }), [line], lang);
    assert.deepEqual(forgeCorrectionNotes({ errata: [{ why_wrong: line }, { why_wrong: line }] }), [line], lang);
  }
});

test('#893: La Forge\'s miss card prints the judge line whole', () => {
  // ExerciseFeedbackMoment (pages/atelier.tsx) puts the first of
  // dedupeNotes([...why.split('\n'), hint]) on the card as its `why`
  // (pinned in components/epreuve/forge-reading.test.js).
  const Ep = require('@/components/epreuve/Epreuve.tsx');
  const line = SHOULD_BE.de;
  const [reason, ...rest] = dedupeNotes([...line.split('\n'), '']);
  assert.deepEqual(rest, []);
  const html = renderToStaticMarkup(
    React.createElement(
      Ep.EpShell,
      { language: 'de' },
      React.createElement(Ep.EpGalley, { why: reason }, React.createElement(Ep.EpFix, { old: 'Stimmt so', fix: 'Stimmt nicht' })),
    ),
  );
  const why = /<p class="ep-why">([\s\S]*?)<\/p>/.exec(html);
  assert.ok(why, 'the card has its reason');
  const text = why[1].replace(/&quot;/g, '"').replace(/&#x27;/g, "'").replace(/&amp;/g, '&');
  assert.equal(text, line);
});
