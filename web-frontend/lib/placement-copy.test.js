// node --test lib/placement-copy.test.js
//
// 2026-09-24 — the placement and the sign-up follow the one-language rule:
// the placement in the learner's declared native language, sign-up and the
// taste in the detected onboarding language. French sample content stays French.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

const { placementCopy, placementFill, placementConfidenceLabel } = require('./placement-copy.ts');
const { SIGNUP_NAV } = require('./onboarding-signup.ts');
const { TASTE_NAV } = require('./onboarding-taste.ts');

const flat = (table) =>
  Object.entries(table).flatMap(([key, value]) =>
    typeof value === 'string' ? [[key, value]] : Object.entries(value).map(([k, v]) => [`${key}.${k}`, v]),
  );

test('the three placement tables are complete and fill the same placeholders', () => {
  const fr = Object.fromEntries(flat(placementCopy('fr')));
  const holes = (s) => (s.match(/\{\w+\}/g) || []).sort().join(',');
  for (const language of ['en', 'de']) {
    const table = Object.fromEntries(flat(placementCopy(language)));
    assert.deepEqual(Object.keys(table).sort(), Object.keys(fr).sort());
    for (const [key, value] of Object.entries(table)) {
      assert.ok(value.trim(), `${language}.${key} is empty`);
      assert.equal(holes(value), holes(fr[key]), `${language}.${key}`);
    }
  }
  assert.equal(placementFill(placementCopy('en').estimated, { level: 'A2.1' }), 'Estimated level: A2.1');
  assert.equal(placementConfidenceLabel(0.8, placementCopy('de')), 'Eine solide Schätzung');
});

test('the placement page reads its chrome from the table, in the native language', () => {
  const page = fs.readFileSync(path.join(WEB_ROOT, 'pages/placement.tsx'), 'utf8');
  assert.ok(page.includes('useLearnerLanguage()'), 'the declared native language, not the level');
  assert.ok(page.includes('pickByLanguage(prompt.hint_by_language, language)'));
  // The prompt itself is French content.
  assert.match(page, /<h1 className="av2-headline av2-headline--screen" lang="fr">\s*\{prompt\.prompt_fr\}/);
  for (const phrase of ['Commencer le bilan', 'Passer pour l’instant', '>Niveau non évalué<', 'Envoyer\n', 'Écrivez ici']) {
    assert.ok(!page.includes(phrase), `inline French chrome: ${phrase}`);
  }
});

test('sign-up and the taste buttons follow the onboarding language', () => {
  assert.equal(SIGNUP_NAV.en.submit, 'Create my account');
  assert.equal(SIGNUP_NAV.de.have_account, 'Ich habe schon ein Konto');
  assert.equal(SIGNUP_NAV.fr.submit, 'Créer mon compte');
  assert.equal(TASTE_NAV.en.start, 'Start');
  assert.equal(TASTE_NAV.fr.keep, 'Gardez votre histoire');
  const signup = fs.readFileSync(path.join(WEB_ROOT, 'pages/auth/signup.tsx'), 'utf8');
  assert.ok(!signup.includes('Créer un compte'), 'no inline French screen name');
});
