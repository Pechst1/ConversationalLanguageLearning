// node --test components/lexique/deck-session.test.js — a filed card stays filed.
const assert = require('node:assert/strict');
const path = require('node:path');
const { test } = require('node:test');

require(path.resolve(__dirname, '../../node_modules/sucrase/register/ts'));
const deck = require('./deck-session.ts');

const card = (word_id) => ({ word_id, word: `mot ${word_id}` });
const ids = (items) => items.map((item) => item.word_id);

test('a card filed before the fresh deck lands is not asked again (owner 2026-10-18, «je sais»)', () => {
  // The cached deck is on screen; «je sais» files 3, «Encore» files 4.
  let progress = deck.fileCard(deck.EMPTY_PROGRESS, 3, false);
  progress = deck.fileCard(progress, 4, true);
  // The server's answer was computed before those reviews were saved: it still deals 3 and 4.
  progress = deck.progressAfterLoad(progress, 'revalidate');
  const fresh = [card(3), card(4), card(5), card(6)];
  assert.deepEqual(ids(deck.remainingCards(fresh, progress)), [5, 6, 4], '3 stays filed; 4 comes back once, at the end');
  assert.equal(progress.filed.size, 2, 'the count keeps both');
});

test('another deck starts from nothing', () => {
  const progress = deck.progressAfterLoad(deck.fileCard(deck.EMPTY_PROGRESS, 3, true), 'new-deck');
  assert.deepEqual(ids(deck.remainingCards([card(3), card(5)], progress)), [3, 5]);
  assert.equal(progress.filed.size, 0);
});

test('successive relearning: wrong goes to the end, right leaves the loop', () => {
  let progress = deck.fileCard(deck.EMPTY_PROGRESS, 1, true);
  const items = [card(1), card(2)];
  assert.deepEqual(ids(deck.remainingCards(items, progress)), [2, 1]);
  progress = deck.fileCard(progress, 2, false);
  progress = deck.fileCard(progress, 1, false);
  assert.deepEqual(ids(deck.remainingCards(items, progress)), []);
});

test('the cached deck drops the filed cards, so a reopened deck does not show them again', () => {
  const context = {
    summary: { total: 4 },
    due_words: [card(1), card(2)],
    fragile_words: [card(3)],
    linked_words: [],
    topic_compatible_words: [],
    new_words: [card(4)],
    algorithm: 'fsrs',
  };
  const cached = deck.withoutFiled(context, new Set([1, 4]));
  assert.deepEqual(ids(cached.due_words), [2]);
  assert.deepEqual(ids(cached.fragile_words), [3]);
  assert.deepEqual(ids(cached.new_words), []);
  assert.equal(cached.algorithm, 'fsrs');
  assert.deepEqual(ids(context.due_words), [1, 2], 'the deck on screen is untouched');
});
