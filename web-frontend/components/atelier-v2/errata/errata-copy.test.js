// node --test components/atelier-v2/errata/errata-copy.test.js
//
// WP-82 — the repair card follows the one language rule: its chrome is the
// learner's language up to A2 and French from B1; the prompt and the learner's
// own sentence stay French. French wording is the table's, verbatim.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..', '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

const { ERRATA_COPY, errataCopy } = require('./errata-copy.ts');
const { chromeLanguage } = require('@/lib/language-rule.ts');

test('the three tables are complete', () => {
  const fr = ERRATA_COPY.fr;
  for (const language of ['en', 'de']) {
    const table = ERRATA_COPY[language];
    assert.deepEqual(Object.keys(table).sort(), Object.keys(fr).sort(), language);
    for (const [key, value] of Object.entries(table)) assert.ok(value.trim(), `${language}.${key} is empty`);
  }
});

test('A1 reads English, A2 German, B1 French', () => {
  assert.equal(errataCopy(chromeLanguage('en', 'A1')).send, 'Send correction');
  assert.equal(errataCopy(chromeLanguage('de', 'A2')).send, 'Korrektur senden');
  assert.equal(errataCopy(chromeLanguage('en', 'B1')).send, 'Envoyer la reprise');
});

test('the sheet reads its chrome from the table, in the chrome language', () => {
  const sheet = fs
    .readFileSync(path.join(__dirname, 'ErrataReviewSheet.tsx'), 'utf8')
    .replace(/\/\*[\s\S]*?\*\//g, '');
  assert.ok(sheet.includes("from './errata-copy'"));
  assert.ok(sheet.includes('useChromeLanguage()'));
  assert.ok(sheet.includes('language={language}'), 'the sheet primitives follow the same language');
  assert.ok(!sheet.includes('language="fr"'));
  for (const phrase of ['Tâche de reprise', 'Erreur mémorisée', 'Envoyer la reprise', 'Réponse visée', 'Fermer']) {
    assert.ok(!sheet.includes(phrase), `inline chrome: ${phrase}`);
  }
});
