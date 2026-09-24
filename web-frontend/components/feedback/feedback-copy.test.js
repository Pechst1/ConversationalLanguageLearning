// node --test components/feedback/feedback-copy.test.js
//
// 2026-09-24 — the one-language rule, swept: the feedback panel (English for
// everyone before) and Home's last French leftovers (yesterday's sentence, the
// art fallback, the settled Séance tile) follow the learner's chrome language.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '../..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

const { FEEDBACK_COPY, FEEDBACK_CATEGORIES, feedbackCopy } = require('./feedback-copy.ts');
const { chromeLanguage } = require('../../lib/language-rule.ts');
const { atelierCopy } = require('../../lib/atelier-v2-copy.ts');

const flat = (value, prefix = '') =>
  typeof value === 'string'
    ? [[prefix, value]]
    : Object.entries(value).flatMap(([k, v]) => flat(v, prefix ? `${prefix}.${k}` : k));

test('the feedback tables are complete in en, de and fr', () => {
  const fr = flat(FEEDBACK_COPY.fr).map(([key]) => key).sort();
  for (const language of ['en', 'de', 'fr']) {
    const table = flat(FEEDBACK_COPY[language]);
    assert.deepEqual(table.map(([key]) => key).sort(), fr, language);
    for (const [key, value] of table) assert.ok(value.trim(), `${language}.${key} is empty`);
    for (const category of FEEDBACK_CATEGORIES) assert.ok(FEEDBACK_COPY[language].categories[category]);
  }
});

test('A1 reads English, A2 German, B1 French', () => {
  assert.equal(feedbackCopy(chromeLanguage('en', 'A1')).title, 'What is off?');
  assert.equal(feedbackCopy(chromeLanguage('de', 'A2')).send, 'Senden');
  assert.equal(feedbackCopy(chromeLanguage('en', 'B1')).sent, 'Avis envoyé.');

  assert.equal(atelierCopy(chromeLanguage('en', 'A1')).home_phrase, 'Yesterday’s sentence');
  assert.equal(atelierCopy(chromeLanguage('de', 'A2')).home_day_settled, 'Tag geschafft');
  assert.equal(atelierCopy(chromeLanguage('de', 'B1')).home_art_soon, 'Illustration à paraître');
  assert.match(atelierCopy(chromeLanguage('en', 'A1')).home_because, /^This scene picks up a mistake you made: \{label\}$/);
  assert.match(atelierCopy(chromeLanguage('de', 'C1')).home_because, /^Cette scène reprend une faute notée/);
});

test('the widget and Home carry no inline chrome any more', () => {
  const widget = fs.readFileSync(path.join(__dirname, 'FeedbackWidget.tsx'), 'utf8');
  assert.ok(widget.includes('useChromeLanguage()'));
  for (const phrase of ["'Feedback sent.'", "'Could not send feedback.'", '>What is off?<', 'label="Send feedback"', "label: 'Broken link'"]) {
    assert.ok(!widget.includes(phrase), `inline chrome: ${phrase}`);
  }
  const home = fs.readFileSync(path.join(WEB_ROOT, 'components/atelier-v2/home/HomeScreen.tsx'), 'utf8');
  for (const phrase of ['La phrase d’hier', 'Illustration sous presse', 'Illustration à paraître', "'Journée bouclée'"]) {
    assert.ok(!home.includes(phrase), `inline French on Home: ${phrase}`);
  }
});
