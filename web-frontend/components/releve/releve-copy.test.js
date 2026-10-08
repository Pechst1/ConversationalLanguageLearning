// node --test components/releve/releve-copy.test.js
//
// WP-82 — Le Relevé and «Vos sceaux» follow the one language rule: the chrome
// is the learner's language up to A2 and French from B1; a keepsake's title
// stays French. French wording is the table's, verbatim from before.

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
  if (request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

const { RELEVE_COPY, releveCopy, fill, plural } = require('./releve-copy.ts');
const { chromeLanguage } = require('@/lib/language-rule.ts');
const { sealCollectionView, daysLabel, weekdayInitials } = require('./seal-collection-model.ts');

const holes = (s) => (s.match(/\{\w+\}/g) || []).sort().join(',');
const code = (file) =>
  fs
    .readFileSync(path.join(__dirname, file), 'utf8')
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/^\s*\/\/.*$/gm, '');

test('the three tables are complete and fill the same placeholders', () => {
  const fr = RELEVE_COPY.fr;
  for (const language of ['en', 'de']) {
    const table = RELEVE_COPY[language];
    assert.deepEqual(Object.keys(table).sort(), Object.keys(fr).sort(), language);
    for (const [key, value] of Object.entries(table)) {
      assert.ok(value.trim(), `${language}.${key} is empty`);
      assert.equal(holes(value), holes(fr[key]), `${language}.${key}`);
    }
  }
  assert.equal(RELEVE_COPY.en.weekday_initials.split(' ').length, 7);
  assert.equal(RELEVE_COPY.de.weekday_initials.split(' ').length, 7);
});

test('A1 reads English, A2 German, B1 French', () => {
  assert.equal(releveCopy(chromeLanguage('en', 'A1')).cours_title, 'Your course');
  assert.equal(releveCopy(chromeLanguage('de', 'A2')).collection_empty_title, 'Noch nichts hier');
  assert.equal(releveCopy(chromeLanguage('en', 'B1')).collection_empty_title, 'Rien d’accroché encore');
  assert.equal(fill(releveCopy('en').status_forecast, { low: 30, high: 45 }), 'Estimate: 30 to 45 days at this pace.');
  assert.equal(plural(releveCopy('de'), 'pieces', 3), '3 Stücke');
  assert.equal(plural(releveCopy('fr'), 'pieces', 1), '1 pièce');
});

test('the seal grid names its cells in the chrome language', () => {
  const payload = {
    current_streak: 1,
    longest_streak: 4,
    today: '2026-09-23',
    calendar: [
      { date: '2026-09-22', state: 'relache', is_today: false },
      { date: '2026-09-23', state: 'today', is_today: true },
    ],
  };
  const fr = sealCollectionView(payload);
  const en = sealCollectionView(payload, undefined, 'en');
  const de = sealCollectionView(payload, undefined, 'de');
  assert.match(fr.today.label, /aujourd’hui, le sceau attend/);
  assert.match(en.today.label, /Wednesday.*today, the seal is waiting/);
  assert.match(de.today.label, /Mittwoch.*heute, das Siegel wartet/);
  assert.equal(daysLabel(1), '1 jour');
  assert.equal(daysLabel(11, 'en'), '11 days');
  assert.equal(daysLabel(1, 'de'), '1 Tag');
  assert.deepEqual(weekdayInitials('en'), ['M', 'T', 'W', 'T', 'F', 'S', 'S']);
});

test('the Relevé files read their chrome from the table', () => {
  const releve = code('Releve.tsx');
  const seals = code('SealCollection.tsx');
  const model = code('seal-collection-model.ts');
  assert.ok(releve.includes("from '@/components/releve/releve-copy'"));
  assert.ok(seals.includes("from './releve-copy'"));
  assert.ok(model.includes("from './releve-copy'"));
  assert.ok(releve.includes('useChromeLanguage()') && seals.includes('useChromeLanguage()'));
  for (const phrase of [
    'Le relevé sort de presse',
    'Réessayer',
    't="Le cours"',
    'Mots acquis',
    'Rien d’accroché encore',
    'Avis du bureau des archives',
    'Décernée au fil des séances.',
    'La première journée bouclée.',
    'arrêté au',
  ]) {
    assert.ok(!releve.includes(phrase), `inline chrome in Releve.tsx: ${phrase}`);
  }
  for (const phrase of ['Vos sceaux', 'Le sceau du jour', 'Un jour de relâche en réserve', 'Réessayer', 'Série ·']) {
    assert.ok(!seals.includes(phrase), `inline chrome in SealCollection.tsx: ${phrase}`);
  }
  for (const phrase of ['journée faite', 'jour de relâche', 'pas de séance', "'1 jour'", "'fr-FR'"]) {
    assert.ok(!model.includes(phrase), `inline chrome in seal-collection-model.ts: ${phrase}`);
  }
  // A keepsake's title is content: it stays French whatever the chrome.
  assert.ok(releve.includes("title: 'Première scène'"));
});
