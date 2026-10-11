/**
 * WP-36 — the chrome around a repair the character asked for.
 *
 * The question itself is the character's French line and arrives on the wire;
 * nothing here invents it. What this pins is the copy the app puts around it:
 * complete in all three languages, in the learner's own language rather than
 * French, and — like every other key in this table — never a word about how the
 * learner sounds.
 *
 * Run: `node components/atelier-v2/journey/journey-self-repair.test.js`
 */

const assert = require('node:assert/strict');
const path = require('node:path');
const Module = require('node:module');

const HERE = __dirname;
const WEB_ROOT = path.resolve(HERE, '../../..');

require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolveWithAlias(request, ...rest) {
  if (typeof request === 'string' && request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

const { journeyCopy } = require(path.join(HERE, 'journey-copy.ts'));

const KEYS = ['correction_self_repair', 'self_repair_hint'];

for (const language of ['en', 'de', 'fr']) {
  const table = journeyCopy(language);
  for (const key of KEYS) {
    assert.ok(table[key] && table[key].trim().length > 0, `${language}.${key} exists`);
    // The label explains something, so it follows the learner's language — a
    // German beginner must not have to read French to know what was asked.
    for (const jargon of ['La Une', 'Épreuve', 'Relevé', 'Feuilleton']) {
      assert.ok(!table[key].includes(jargon), `${language}.${key} avoids "${jargon}"`);
    }
    for (const banned of ['pronunciation', 'prononciation', 'Aussprache', 'phoneme']) {
      assert.ok(
        !table[key].toLowerCase().includes(banned.toLowerCase()),
        `${language}.${key} must not judge pronunciation`,
      );
    }
  }
}

// Three distinct languages, not one string copied three times.
const rendered = ['en', 'de', 'fr'].map((language) => journeyCopy(language).correction_self_repair);
assert.equal(new Set(rendered).size, 3, 'each language says it in its own words');

// The unknown-language fallback is the same one the rest of the table uses.
assert.equal(journeyCopy('pt').correction_self_repair, journeyCopy('en').correction_self_repair);
assert.equal(journeyCopy(null).self_repair_hint, journeyCopy('en').self_repair_hint);

// The hint asks for the form again; it never states which one is right, because
// the whole point of the prompt is that the learner produces it.
for (const language of ['en', 'de', 'fr']) {
  const hint = journeyCopy(language).self_repair_hint;
  assert.ok(!/«|»|“|”|„/.test(hint), `${language}.self_repair_hint quotes no form`);
}

console.log('journey-self-repair: all checks passed');
