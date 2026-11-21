// node --test components/courrier/courrier-ribbon-used.test.js
//
// #928 — the ribbon's «words used» is the server's record, not a substring test.
//
// The walk of 19 Nov wrote «Je n ai pas vendu l appartement. J ai garde la cle…»
// to a letter asking for vendre, clé, appartement and read «1/3». The server's
// check records each used target (lemma- and accent-aware) and serialize_mission
// hands it over as `used_target_word_ids`
// (tests/test_courrier_used_words_928.py); the ribbon reads that and nothing else.

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

const { ribbonWords } = require('./ribbon-words.ts');

const PAGE = fs.readFileSync(path.join(WEB_ROOT, 'pages', 'missions.tsx'), 'utf8');
const WALK_REPLY = 'Je n ai pas vendu l appartement. J ai garde la cle dans ma poche, je ne sais pas pourquoi.';
const TARGETS = [
  { word_id: 9281, word: 'vendre', translation: 'to sell' },
  { word_id: 9282, word: 'la clé', translation: 'the key' },
  { word_id: 9283, word: "l'appartement", translation: 'the flat' },
];

function letter(used) {
  return {
    id: 'm-928',
    target_vocabulary: TARGETS,
    prompt_payload: { target_vocabulary: TARGETS },
    turns: [{ id: 't1', turn_index: 1, role: 'user', text: WALK_REPLY }],
    ...(used ? { used_target_word_ids: used } : {}),
  };
}

const count = (ribbon) => ribbon.filter((item) => item.used).length;

test('the walk’s reply counts 3/3 when the server recorded all three', () => {
  const ribbon = ribbonWords(letter([9281, 9282, 9283]));
  assert.deepEqual(ribbon.map((item) => item.t), ['vendre', 'la clé', "l'appartement"]);
  assert.equal(count(ribbon), 3);
});

test('a word the server did not record is not marked, whatever the text says', () => {
  // The reply contains «appartement» verbatim; the screen still waits for the check.
  assert.equal(count(ribbonWords(letter([]))), 0);
  assert.equal(count(ribbonWords(letter(null))), 0);
  assert.deepEqual(ribbonWords(letter([9282])).map((item) => Boolean(item.used)), [false, true, false]);
});

test('the page takes the ribbon from the shared module, with no text match of its own', () => {
  assert.match(PAGE, /from '@\/components\/courrier\/ribbon-words'/);
  assert.doesNotMatch(PAGE, /function ribbonWords\(/);
  const source = fs.readFileSync(path.join(__dirname, 'ribbon-words.ts'), 'utf8');
  assert.doesNotMatch(source, /\.includes\(/);
});
