// node --test components/courrier/courrier-words-used.test.js
//
// #928 (root cause #143): the Courrier's «words used» ribbon reads the server's
// record of the target words the replies used, never a substring test of the raw
// text. Walk 19 Nov: targets vendre, clé, appartement; the reply «Je n ai pas
// vendu l appartement. J ai garde la cle…» showed 1/3, because «vendre» is not a
// substring of «vendu» and «clé» is not one of «cle». The server had already
// recorded all three (tests/test_courrier_words_used.py).

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

const read = (...parts) => fs.readFileSync(path.join(WEB_ROOT, ...parts), 'utf8');

const WALK_REPLY = 'Je n ai pas vendu l appartement. J ai garde la cle dans ma poche.';
const TARGETS = [
  { word_id: 11, word: 'vendre', translation: 'to sell' },
  { word_id: 12, word: 'clé', translation: 'key' },
  { word_id: 13, word: 'appartement', translation: 'flat' },
];
const letter = (extra = {}) => ({
  id: 'm-928',
  status: 'in_progress',
  target_vocabulary: TARGETS,
  prompt_payload: {},
  turns: [{ id: 't1', turn_index: 1, role: 'user', text: WALK_REPLY }],
  ...extra,
});

test('the Courrier page does not decide «used» by finding the word in the raw text', () => {
  const page = read('pages', 'missions.tsx');
  assert.doesNotMatch(
    page,
    /said\.includes\(/,
    'the ribbon still marks a word used by a substring test of the reply («vendre» is not in «vendu», «clé» is not in «cle»)',
  );
});

test('the walk reply shows 3/3 when the server recorded vendre, clé and appartement as used', () => {
  const { ribbonWords } = require('./courrier-ribbon.ts');
  const ribbon = ribbonWords(letter({ used_target_word_ids: [11, 12, 13] }));
  assert.deepEqual(
    ribbon.map((word) => [word.t, word.used]),
    [['vendre', true], ['clé', true], ['appartement', true]],
  );
  assert.equal(ribbon.filter((word) => word.used).length, 3);
});

test('the ribbon does not second-guess the record from the text', () => {
  const { ribbonWords } = require('./courrier-ribbon.ts');
  // The reply contains «appartement», but nothing is recorded yet: the page waits for the server.
  const ribbon = ribbonWords(letter({ used_target_word_ids: [] }));
  assert.equal(ribbon.filter((word) => word.used).length, 0);
  // A recorded word reads as used even when the text spells it otherwise.
  const one = ribbonWords(letter({ used_target_word_ids: [12] }));
  assert.deepEqual(one.filter((word) => word.used).map((word) => word.t), ['clé']);
});
