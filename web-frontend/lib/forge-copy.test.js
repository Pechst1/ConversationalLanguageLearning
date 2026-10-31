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
  // Owner, 2026-10-18: a rung reads as the learner's level on the rule, 1 to 6.
  assert.equal(fillForge(en.level, { n: 3 }), 'Level 3');
  assert.equal(fillForge(forgeCopy('de').level, { n: 3 }), 'Stufe 3');
  assert.equal(fillForge(forgeCopy('fr').level, { n: 3 }), 'Niveau 3');
  assert.equal(fillForge(en.level_up, { n: 4 }), 'Level 4 ↑');
  assert.equal(fillForge(forgeCopy('fr').run_cheer, { n: 3 }), '3 d’affilée');
  assert.equal(forgeRungLabel(forgeCopy('fr'), 'free_use'), 'emploi libre');
  assert.equal(forgeRungLabel(en, 'nonsense'), 'recognise');
});

test('the step line, the rule-change card and the coach line are gone from the tables', () => {
  for (const language of ['en', 'de', 'fr']) {
    for (const key of ['step_of', 'stair_label', 'next_rule', 'coach_label', 'reprise']) {
      assert.equal(FORGE_COPY[language][key], undefined, `${language}.${key}`);
    }
  }
});

test('the Cahier offers the test-out and the séance follows the forge', () => {
  const grammar = fs.readFileSync(path.join(WEB_ROOT, 'pages/grammar.tsx'), 'utf8');
  assert.match(grammar, /api\.startForgeTestOut\(concept\.id\)/);
  assert.match(grammar, /forgeCopy\(useChromeLanguage\(concept\.level\)\)/);
  assert.match(grammar, /\/atelier\?testout=/);

  const atelier = fs.readFileSync(path.join(WEB_ROOT, 'pages/atelier.tsx'), 'utf8');
  assert.match(atelier, /const forgeView = forgeViewOf\(next\.forge\)/);
  assert.match(atelier, /if \(forge && !activeRetest\) \{/);
  assert.match(atelier, /apiService\.startForgeTestOut\(conceptId, options\)/);
  // Owner, 2026-10-18: the épreuve is in the rule sheet, never on every screen…
  assert.match(atelier, /<ForgeSheetTestOut copy=\{fc\} pending=\{testOutPending\} onClick=\{\(\) => onTestOut\(activeConcept\.id\)\} \/>/);
  // …and the recap offers its short form every few days.
  assert.match(atelier, /startTestOut\(conceptId, \{ short: true, source: 'forge' \}\)/);
});

test('#300 a spot with several wrong words says how many, in all three languages', () => {
  for (const language of ['en', 'de', 'fr']) {
    const copy = forgeCopy(language);
    // The table says how many words, with the number in it, beside the one-word hint.
    assert.match(String(copy.hint_spot_n), /\{n\}/, language);
    assert.doesNotMatch(String(copy.hint_spot), /\{n\}/, language);
  }
  // The item carries the number and the spot card shows it.
  const atelier = fs.readFileSync(path.join(WEB_ROOT, 'pages/atelier.tsx'), 'utf8');
  assert.match(atelier, /fixWords=\{item\.fix_words\}/);
  const { spotHint } = require('./forge-copy.ts');
  for (const language of ['en', 'de', 'fr']) {
    const copy = forgeCopy(language);
    assert.equal(spotHint(copy, undefined), copy.hint_spot, language);
    assert.equal(spotHint(copy, 1), copy.hint_spot, language);
    assert.match(spotHint(copy, 2), /\b2\b/, language);
    assert.notEqual(spotHint(copy, 2), copy.hint_spot, language);
  }
  assert.equal(spotHint(forgeCopy('en'), 2), 'Tap the 2 wrong words and fix them.');
});

// #402: the level legend states the rule the staircase applies. The server hands the
// page that rule (`forge.level_rule`, from `app/core/forge.py`); a miss that keeps the
// level (owner decision #88) must not be described as «down one».
test('the level legend says what the server says a miss does', () => {
  const { levelExplain } = require('./forge-progress.ts');
  for (const language of ['en', 'de', 'fr']) {
    const copy = forgeCopy(language);
    assert.equal(typeof levelExplain, 'function', 'the legend is chosen from the server’s rule');
    const keeps = levelExplain(copy, { right: 1, wrong: 0 });
    const down = levelExplain(copy, { right: 1, wrong: -1 });
    assert.notEqual(keeps, down, language);
    assert.equal(down, copy.level_explain_down, language);
  }
  const en = forgeCopy('en');
  assert.doesNotMatch(levelExplain(en, { right: 1, wrong: 0 }), /down/i);
  assert.match(levelExplain(en, { right: 1, wrong: 0 }), /stays/i);
  // Without the rule (an older server) the legend promises nothing it cannot know.
  assert.equal(levelExplain(en, undefined), en.level_explain);
  assert.doesNotMatch(en.level_explain, /down/i);
  assert.doesNotMatch(forgeCopy('de').level_explain, /runter/i);
  assert.doesNotMatch(forgeCopy('fr').level_explain, /un de moins/i);
});
