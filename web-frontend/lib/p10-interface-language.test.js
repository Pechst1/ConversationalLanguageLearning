// node --test lib/p10-interface-language.test.js
//
// P10 — the strings that were in the wrong language (experience review, finding 9).
//
//   1. a word-bank card never quotes an empty or instruction-like meaning cue
//      («Construis la phrase : « Express a complete sentence in French using … » »);
//   2. the masthead's gear and Home's placement chip read the interface language
//      (French from B1), not the mother tongue («Settings» on a French page);
//   3. no copy table says «Mode POV» or «on trial»;
//   4. each language names a pace once: Home's Tempo sheet and Réglages read the
//      same table.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  return originalResolve.call(this, request, ...rest);
};

const read = (file) => fs.readFileSync(path.join(WEB_ROOT, file), 'utf8');

const { meaningCueText } = require('../components/atelier-v2/journey/drill-frame.ts');
const { chromeLanguage } = require('./language-rule.ts');
const { atelierChrome } = require('./atelier-v2-copy.ts');
const { daySessionCopy } = require('./day-session.ts');

test('a build card quotes a meaning or nothing — never the generator’s ask', () => {
  for (const cue of [
    '',
    null,
    undefined,
    '   ',
    'Express a complete sentence in French using pronoun choice; use every target chip once.',
    'Express: Express a complete sentence in French using the target grammar; use every target chip once.',
    'Build the full French sentence.',
  ]) {
    assert.equal(meaningCueText(cue), '', `quoted: ${JSON.stringify(cue)}`);
  }
  assert.equal(meaningCueText('Express: I do not drink coffee.'), 'I do not drink coffee.');
  assert.equal(meaningCueText('You saw that you had lost your phone.'), 'You saw that you had lost your phone.');
  const page = read('pages/atelier.tsx');
  assert.match(page, /const buildCue = meaningCueText\(item\.meaning_cue\) \|\| String\(item\.prompt \|\| ''\);/);
  assert.doesNotMatch(page, /stripExpressPrefix/);
});

test('the masthead’s gear reads «Réglages» for a B1 learner, whatever their own language', () => {
  for (const own of ['en', 'de', 'fr']) {
    assert.equal(atelierChrome(chromeLanguage(own, 'B1.1')).settings, 'Réglages');
  }
  assert.equal(atelierChrome(chromeLanguage('de', 'A1.1')).settings, 'Einstellungen');
  const masthead = read('components/layout/EditorialMasthead.tsx');
  assert.match(masthead, /chromeLanguage\(language, readLearnerLevel\(\)\)/);
  assert.match(masthead, /atelierChrome\(interfaceLanguage\)\.settings/);
  assert.doesNotMatch(masthead, /atelierChrome\(learnerLanguage\)/);
  // Home's placement chip sits on a French page from B1 too.
  assert.match(read('components/onboarding/PlacementOfferChip.tsx'), /placementCopy\(useChromeLanguage\(\)\)/);
});

test('no copy table leaks an internal word: «Mode POV», «on trial»', () => {
  const feuilleton = read('components/feuilleton/feuilleton-copy.ts');
  const bandCheck = read('components/atelier-v2/band-check/band-check-copy.ts');
  assert.doesNotMatch(feuilleton, /\bPOV\b/);
  assert.doesNotMatch(bandCheck, /on trial|à l’essai|erprobt/);
});

test('each language names a pace once, on Home and in Réglages', () => {
  const expected = {
    fr: { ruhig: 'Calme', normal: 'Normal', schnell: 'Rapide' },
    en: { ruhig: 'Easy', normal: 'Normal', schnell: 'Fast' },
    de: { ruhig: 'Ruhig', normal: 'Normal', schnell: 'Schnell' },
  };
  for (const [language, names] of Object.entries(expected)) {
    assert.deepEqual(daySessionCopy(language).pace, names, language);
  }
  // Réglages has no pace names of its own: it reads the Tempo sheet's table.
  assert.match(read('pages/settings.tsx'), /\{paceCopy\.pace\[pace\]\}/);
  assert.doesNotMatch(read('lib/settings-copy.ts'), /\bpace_(ruhig|normal|schnell)\b/);
});
