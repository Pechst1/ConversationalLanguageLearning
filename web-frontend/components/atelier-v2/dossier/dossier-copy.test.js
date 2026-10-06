// node --test components/atelier-v2/dossier/dossier-copy.test.js
//
// WP-82 — «Votre dossier» follows the one language rule: the chrome is the
// learner's language up to A2 and French from B1; what the server sends as
// French content stays French. French wording is the table's, verbatim.

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

const { DOSSIER_COPY, dossierCopy, longDate, shortDate } = require('./dossier-copy.ts');
const state = require('./dossier-state.ts');
const { chromeLanguage } = require('@/lib/language-rule.ts');

const holes = (s) => (s.match(/\{\w+\}/g) || []).sort().join(',');
const code = (file) =>
  fs
    .readFileSync(path.join(WEB_ROOT, file), 'utf8')
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/^\s*\/\/.*$/gm, '');

test('the three tables are complete and fill the same placeholders', () => {
  const fr = DOSSIER_COPY.fr;
  for (const language of ['en', 'de']) {
    const table = DOSSIER_COPY[language];
    assert.deepEqual(Object.keys(table).sort(), Object.keys(fr).sort(), language);
    for (const [key, value] of Object.entries(table)) {
      assert.ok(value.trim(), `${language}.${key} is empty`);
      assert.equal(holes(value), holes(fr[key]), `${language}.${key}`);
    }
  }
});

test('A1 reads English, A2 German, B1 French', () => {
  assert.equal(dossierCopy(chromeLanguage('en', 'A1')).level_title, 'Your level');
  assert.equal(dossierCopy(chromeLanguage('de', 'A2')).level_title, 'Ihr Niveau');
  assert.equal(dossierCopy(chromeLanguage('en', 'B1')).level_title, 'Votre niveau');
});

test('the state sentences follow the language they are given', () => {
  const placement = {
    available: true,
    estimate: 'A2.1',
    estimate_source: 'placement',
    confidence: 0.72,
    placement: { taken_at: '2026-09-10', graded_turns: 5 },
    evidence: { kind: 'placement', on: '2026-09-10' },
  };
  assert.equal(state.levelSentence(placement, 'en'), 'Estimated level (placement test) · A2.1');
  assert.equal(state.levelSentence(placement, 'de'), 'Geschätztes Niveau (Einstufungstest) · A2.1');
  assert.equal(state.levelSentence(placement), 'Niveau estimé (bilan) · A2.1');
  assert.equal(
    state.levelBasisSentence(placement, 'en'),
    'Measured by the placement test, on 5 marked answers. High confidence (72%).',
  );
  assert.equal(state.levelSourceLine(placement, 'de'), 'geschätzt (Einstufungstest vom 10. Sept.) · nicht geprüft');
  assert.equal(state.evidenceSentence(placement.evidence, 'en'), 'Placement test of 10 September');
  assert.equal(state.capabilityStateLabel('with_support', 'de'), 'Mit Hilfe');
  assert.equal(state.errataTotalSentence({ totals: { open: 2, repairing: 1 } }, 'en'), '3 mistakes noted in all.');
  assert.equal(state.noJourneySentence('en'), 'No scene yet today.');
  assert.equal(
    state.becauseSentence({ has_journey: true, because: { kind: 'erratum', label: 'l’accord' } }, 'en'),
    'This scene revisits a noted mistake: l’accord.',
  );
  assert.equal(
    state.capabilityEvidenceRef(
      { state: 'used_again_later', evidence: [{ on: '2026-09-12' }, { on: '2026-09-14' }] },
      'de',
    ),
    'Übungen vom 12. und 14. Sept.',
  );
  // French dates keep their conventions.
  assert.equal(longDate('2026-01-01'), '1er janvier');
  assert.equal(shortDate('2026-09-12', 'en'), '12 Sept');
});

test('the Dossier files read their chrome from the table', () => {
  const screen = code('components/atelier-v2/dossier/DossierScreen.tsx');
  const stateSource = code('components/atelier-v2/dossier/dossier-state.ts');
  const page = code('pages/dossier.tsx');
  assert.ok(screen.includes("from './dossier-copy'"));
  assert.ok(stateSource.includes("from './dossier-copy'"));
  assert.ok(page.includes("from '@/components/atelier-v2/dossier/dossier-copy'"));
  for (const phrase of [
    'Votre niveau',
    'Vos capacités',
    'Vos fautes notées',
    'Je connais déjà',
    'Revenir au dossier',
    'Deux questions, puis c’est réglé',
    'Dossier indisponible',
    'Pas encore tenté',
    'Niveau déclaré',
    'Confiance élevée',
    'Pas encore de scène aujourd’hui',
    'Le dossier n’a pas pu être ouvert',
    'Cette action n’a pas abouti',
  ]) {
    for (const [name, source] of [['screen', screen], ['state', stateSource], ['page', page]]) {
      assert.ok(!source.includes(phrase), `inline chrome in ${name}: ${phrase}`);
    }
  }
});
