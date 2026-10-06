// node --test lib/forge-copy.test.js
//
// WP-S3 — La Forge's chrome follows the one language rule and is wired:
//   1. the three copy tables (en / de / fr) are complete and never empty;
//   2. sentence case: no all-caps chrome;
//   3. the Cahier rule page offers «Test out» from the chrome language, and the
//      séance runs the forge's item sequence (forge.next), not the fixed ladder.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));

const { FORGE_COPY, fillForge, forgeCopy, forgeRungLabel } = require('./forge-copy.ts');

function leaves(value, prefix = '') {
  if (value && typeof value === 'object') {
    return Object.entries(value).flatMap(([key, inner]) => leaves(inner, prefix ? `${prefix}.${key}` : key));
  }
  return [[prefix, value]];
}

test('the three copy tables have the same keys and no empty string', () => {
  const keys = (table) => leaves(table).map(([key]) => key).sort();
  for (const language of ['en', 'de', 'fr']) {
    assert.deepEqual(keys(FORGE_COPY[language]), keys(FORGE_COPY.en), language);
    for (const [key, value] of leaves(FORGE_COPY[language])) {
      assert.equal(typeof value, 'string', `${language}.${key}`);
      assert.ok(value.trim().length > 0, `${language}.${key}`);
      assert.notEqual(value, value.toUpperCase(), `${language}.${key} is not sentence case`);
    }
  }
});

test('an English A1 learner reads English; unknown languages fall back to English', () => {
  assert.equal(forgeCopy('en').test_out_action, 'Test out this rule');
  assert.equal(forgeCopy('de').test_out_action, FORGE_COPY.de.test_out_action);
  assert.equal(forgeCopy('fr').test_out_action, 'Passer l’épreuve de la règle');
  assert.equal(forgeCopy(undefined).test_out_action, 'Test out this rule');
});

test('placeholders and rung labels fill in', () => {
  const en = forgeCopy('en');
  assert.equal(fillForge(en.step_of, { n: 3, rung: forgeRungLabel(en, 'build') }), 'Step 3 of 6 · build');
  assert.equal(forgeRungLabel(forgeCopy('fr'), 'free_use'), 'emploi libre');
  assert.equal(forgeRungLabel(en, 'nonsense'), 'recognise');
});

test('the Cahier offers the test-out and the séance follows the forge', () => {
  const grammar = fs.readFileSync(path.join(WEB_ROOT, 'pages/grammar.tsx'), 'utf8');
  assert.match(grammar, /api\.startForgeTestOut\(concept\.id\)/);
  assert.match(grammar, /forgeCopy\(useChromeLanguage\(concept\.level\)\)/);
  assert.match(grammar, /\/atelier\?testout=/);

  const atelier = fs.readFileSync(path.join(WEB_ROOT, 'pages/atelier.tsx'), 'utf8');
  assert.match(atelier, /const forgeView = forgeViewOf\(next\.forge\)/);
  assert.match(atelier, /if \(forge && !activeRetest\) \{/);
  assert.match(atelier, /apiService\.startForgeTestOut\(conceptId\)/);
  // WP-S6: the action is drawn by ForgeHead (components/epreuve/Forge.tsx).
  assert.match(atelier, /onClick: \(\) => onTestOut\(activeConcept\.id\)/);
});
