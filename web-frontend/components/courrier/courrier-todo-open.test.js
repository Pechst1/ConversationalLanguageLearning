// node --test components/courrier/courrier-todo-open.test.js
//
// #922 — a reply that contradicts the To do («Non, je n’ai pas la serviette») ends
// «Partly», and the seal's sentence names the part of the To do still open, in the
// chrome language, instead of the generic «the rest can wait».

const assert = require('node:assert/strict');
const path = require('node:path');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));

const Module = require('node:module');
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

// What the debrief stores for the 19 Nov napkin letter (`recap.measured.todo_open`).
const TODO_OPEN = { fr: 'que tu as la serviette pour elle', en: 'you have the napkin for her' };

test('a partial letter names the part of the To do the reply contradicted', () => {
  const { crOutcomeSentence } = require('./Correspondance.tsx');
  const { courrierCopy } = require('./courrier-copy.ts');
  for (const [lang, item] of [['en', TODO_OPEN.en], ['fr', TODO_OPEN.fr], ['de', TODO_OPEN.fr]]) {
    const sentence = crOutcomeSentence('partial', 'Zoé', lang, { open: item });
    assert.ok(sentence.includes(item), `${lang}: «${sentence}» does not say which part was missed`);
    assert.notEqual(sentence, courrierCopy(lang).sentence_partial);
  }
  // Without a contradicted item the sentence stays the plain one.
  assert.equal(crOutcomeSentence('partial', 'Zoé', 'en', {}), courrierCopy('en').sentence_partial);
  // A kept letter never prints an open item.
  assert.doesNotMatch(crOutcomeSentence('kept', 'Zoé', 'en', { open: TODO_OPEN.en }), /napkin/);
});

test('the open item is read in the chrome language, the letter’s French otherwise', () => {
  const { crTodoOpen } = require('./Correspondance.tsx');
  assert.equal(crTodoOpen({ todo_open: TODO_OPEN }, 'en'), TODO_OPEN.en);
  assert.equal(crTodoOpen({ todo_open: TODO_OPEN }, 'de'), TODO_OPEN.fr);
  assert.equal(crTodoOpen({}, 'en'), null);
  assert.equal(crTodoOpen(null, 'en'), null);
});
