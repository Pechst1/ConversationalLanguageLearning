// WP-46 — Réglages reads in the learner's own language.
//
// The screen is the administrative surface, not a product screen: the French
// chrome rule (WP-43) stops at its door. These tests pin the three properties
// a learner actually depends on — that no language is missing a sentence, that
// no sentence is blank, and that an account we have no table for lands on
// English rather than on a half-translated page.
const test = require('node:test');
const assert = require('node:assert/strict');

require('../node_modules/sucrase/register/ts');
const {
  settingsCopy,
  resolveSettingsLanguage,
  SETTINGS_COPY_KEYS,
} = require('./settings-copy.ts');

const LANGUAGES = ['en', 'de', 'fr'];

test('the three tables carry exactly the same keys', () => {
  const en = Object.keys(settingsCopy('en')).sort();
  assert.ok(en.length > 100, `expected the whole screen, got ${en.length} keys`);
  for (const language of ['de', 'fr']) {
    const keys = Object.keys(settingsCopy(language)).sort();
    const missing = en.filter((key) => !keys.includes(key));
    const extra = keys.filter((key) => !en.includes(key));
    assert.deepEqual(missing, [], `${language} is missing keys`);
    assert.deepEqual(extra, [], `${language} has keys English does not`);
  }
});

test('SETTINGS_COPY_KEYS is the full key list', () => {
  assert.deepEqual([...SETTINGS_COPY_KEYS].sort(), Object.keys(settingsCopy('en')).sort());
});

test('no string is empty or whitespace in any language', () => {
  for (const language of LANGUAGES) {
    const table = settingsCopy(language);
    for (const [key, value] of Object.entries(table)) {
      assert.equal(typeof value, 'string', `${language}.${key} is not a string`);
      assert.ok(value.trim().length > 0, `${language}.${key} is empty`);
    }
  }
});

test('French is kept verbatim from the artboard', () => {
  const fr = settingsCopy('fr');
  assert.equal(fr.headline, 'Réglages');
  assert.equal(fr.page_title, 'L’administration · Réglages');
  assert.equal(fr.action_save, 'Classer les modifications');
  assert.equal(fr.row_feedback, 'Signaler un problème');
  assert.equal(fr.row_dossier, 'Votre dossier');
  assert.equal(fr.row_placement, 'Bilan de niveau');
  assert.equal(fr.row_rehearsal, 'Répéter une vraie situation');
});

test('an unknown language falls back to English, never to French', () => {
  for (const unknown of ['es', 'it', 'pt-BR', '', '  ', null, undefined, 42, {}]) {
    assert.equal(settingsCopy(unknown), settingsCopy('en'), `${String(unknown)} should be English`);
  }
});

test('locale tags and casing resolve to their base language', () => {
  assert.equal(settingsCopy('de-DE').headline, settingsCopy('de').headline);
  assert.equal(settingsCopy('DE').headline, settingsCopy('de').headline);
  assert.equal(settingsCopy('  fr  ').headline, 'Réglages');
  assert.equal(settingsCopy('fr_CA').headline, 'Réglages');
});

test('the three headlines differ — the table is translated, not copied', () => {
  const headlines = LANGUAGES.map((language) => settingsCopy(language).headline);
  assert.equal(new Set(headlines).size, 3);
});

test('German and English share no sentence with French beyond proper nouns', () => {
  // A key whose French and German values are identical is almost always an
  // untranslated paste. The allowed ones are names and abbreviations.
  const allowed = new Set(['language_es', 'address_neutral', 'theme_system', 'row_theme']);
  const fr = settingsCopy('fr');
  const de = settingsCopy('de');
  for (const [key, value] of Object.entries(fr)) {
    if (allowed.has(key)) continue;
    assert.notEqual(de[key], value, `${key} is the same in French and German`);
  }
});

test('resolveSettingsLanguage prefers the native language', () => {
  assert.equal(resolveSettingsLanguage('de', 'fr'), 'de');
  assert.equal(resolveSettingsLanguage('en', 'fr'), 'en');
  assert.equal(resolveSettingsLanguage('fr', 'en'), 'fr');
  assert.equal(resolveSettingsLanguage('de-AT', 'fr'), 'de');
});

test('resolveSettingsLanguage falls through native → control → English', () => {
  assert.equal(resolveSettingsLanguage(null, 'de'), 'de');
  assert.equal(resolveSettingsLanguage('', 'fr'), 'fr');
  assert.equal(resolveSettingsLanguage(null, null), 'en');
  assert.equal(resolveSettingsLanguage(undefined, undefined), 'en');
  // The pre-hydration case: nothing is known yet, and the answer is English —
  // French is never painted and then swapped away.
  assert.equal(resolveSettingsLanguage(null), 'en');
  assert.equal(settingsCopy(resolveSettingsLanguage(null)).headline, 'Settings');
});

test('an unsupported native language does not fall back to the control French', () => {
  // A Spanish native on a French-chrome app reads the administration in
  // English, not in the French they cannot yet read.
  assert.equal(resolveSettingsLanguage('es', 'fr'), 'en');
  assert.equal(settingsCopy(resolveSettingsLanguage('es', 'fr')).headline, 'Settings');
});
