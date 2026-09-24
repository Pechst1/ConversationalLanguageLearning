// node --test components/atelier-v2/rehearsal/rehearsal-copy.test.js
//
// WP-82 — «Répétition» follows the one language rule: the chrome is the
// learner's language up to A2 and French from B1; the scene and the learner's
// sentences stay French. French wording is the table's, verbatim.

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

const { REHEARSAL_COPY, rehearsalCopy } = require('./rehearsal-copy.ts');
const state = require('./rehearsal-state.ts');
const { chromeLanguage } = require('@/lib/language-rule.ts');

const holes = (s) => (s.match(/\{\w+\}/g) || []).sort().join(',');
const code = (file) =>
  fs
    .readFileSync(path.join(WEB_ROOT, file), 'utf8')
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/^\s*\/\/.*$/gm, '');

test('the three tables are complete and fill the same placeholders', () => {
  const fr = REHEARSAL_COPY.fr;
  for (const language of ['en', 'de']) {
    const table = REHEARSAL_COPY[language];
    assert.deepEqual(Object.keys(table).sort(), Object.keys(fr).sort(), language);
    for (const [key, value] of Object.entries(table)) {
      assert.ok(value.trim(), `${language}.${key} is empty`);
      assert.equal(holes(value), holes(fr[key]), `${language}.${key}`);
    }
  }
});

test('A1 reads English, A2 German, B1 French', () => {
  assert.equal(rehearsalCopy(chromeLanguage('en', 'A1')).declare_title, 'Rehearse a real situation');
  assert.equal(rehearsalCopy(chromeLanguage('de', 'A2')).declare_title, 'Proben Sie eine echte Situation');
  assert.equal(rehearsalCopy(chromeLanguage('en', 'B1')).declare_title, 'Répétez une vraie situation');
});

test('the state sentences follow the language they are given', () => {
  assert.equal(state.capSentence({ limit: 3, remaining: 2 }, 'en'), 'You have 2 rehearsals left this week.');
  assert.equal(state.capSentence({ limit: 0, remaining: 0 }, 'de'), 'Proben sind deaktiviert.');
  assert.equal(state.capSentence({ limit: 2, remaining: 1 }), 'Il vous reste une répétition cette semaine.');
  assert.match(state.eventDateSentence({ event_date: '2026-09-15' }, 'en'), /^It’s on Tuesday/);
  assert.match(state.nextSlotSentence('2026-09-20T08:00:00+00:00', 'de'), /^Nächste Probe möglich am /);
  const partial = { result: { outcome: 'partially_met', points_total: 3, points_covered: 2 } };
  assert.equal(state.resultSentence(partial, 'en'), 'You covered 2 points of 3.');
  assert.deepEqual(
    state.debriefChoices('de').map((choice) => choice.label),
    ['Ich habe es geschafft', 'Teilweise', 'Noch nicht'],
  );
  assert.equal(state.DEBRIEF_CHOICES[0].label, 'Je l’ai fait');
});

test('the Répétition files read their chrome from the table', () => {
  const screen = code('components/atelier-v2/rehearsal/RehearsalScreen.tsx');
  const stateSource = code('components/atelier-v2/rehearsal/rehearsal-state.ts');
  const page = code('pages/repetition.tsx');
  assert.ok(screen.includes("from './rehearsal-copy'"));
  assert.ok(stateSource.includes("from './rehearsal-copy'"));
  assert.ok(page.includes("from '@/components/atelier-v2/rehearsal/rehearsal-copy'"));
  for (const phrase of [
    'Revenir à l’Atelier',
    'Répétez une vraie situation',
    'Préparer la répétition',
    'Plus tard',
    'Répétition non préparée',
    'Votre réponse, en français',
    'Phrases utiles',
    'Comment ça s’est passé',
    'Enregistrer le bilan',
    'Il vous reste',
    'Je l’ai fait',
    'La page n’a pas pu être ouverte',
    'Cette action n’a pas abouti',
  ]) {
    for (const [name, source] of [['screen', screen], ['state', stateSource], ['page', page]]) {
      assert.ok(!source.includes(phrase), `inline chrome in ${name}: ${phrase}`);
    }
  }
});
