// node --test components/lexique/deck-slot.test.js
//
// Walk 3 Nov (#505): the word deck headed a due review «Word of the day» and
// today's scene words «Due 9 November». The card header says why the card is in
// today's deck (its slot, as the server dealt it, `app/services/deck_order.py`),
// never when the card falls due next.
const assert = require('node:assert/strict');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));
// The copy table imports the design system through the `@/` alias.
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  return originalResolve.call(this, request, ...rest);
};
const { lexiqueCopy } = require('./lexique-copy.ts');

const en = lexiqueCopy('en');
const due = { word_id: 1, bucket: 'due', due_at: '2026-11-04T08:00:00Z' };
const scene = { word_id: 2, bucket: 'new', scene_word: true, due_at: '2026-11-09T08:00:00Z' };
const fresh = { word_id: 3, bucket: 'new' };
// The review also sits on today's slate; so does the scene word.
const slate = new Set([1, 2]);

test('a due review is headed «To review», even when it is on the day slate', () => {
  const { deckSlotLabel } = require('./deck-session.ts');
  assert.equal(deckSlotLabel(en, due, slate), en.state_due);
  assert.notEqual(deckSlotLabel(en, due, slate), en.word_of_day);
});

test('a scene word is headed as the scene\'s, not with its next due date', () => {
  const { deckSlotLabel } = require('./deck-session.ts');
  const label = deckSlotLabel(en, scene, slate);
  assert.equal(label, en.bucket_scene);
  assert.doesNotMatch(label, /Due|November/);
});

test('a new word is headed «Today\'s new words»', () => {
  const { deckSlotLabel } = require('./deck-session.ts');
  assert.equal(deckSlotLabel(en, fresh, new Set()), en.bucket_new_deck);
});

test('the review page prints the slot label and no longer reads the card\'s due date for its header', () => {
  const fs = require('node:fs');
  const source = fs.readFileSync(path.join(WEB_ROOT, 'pages/vocabulary/review.tsx'), 'utf8');
  assert.match(source, /deckSlotLabel\(/, 'the header comes from the card\'s slot in the day deck');
  assert.doesNotMatch(source, /t\.due_on/, 'the header must not print «Due <date>»');
  assert.doesNotMatch(source, /currentSlateEntry \? t\.word_of_day/, 'being on the slate must not turn a review into «Word of the day»');
});

test('no card of today\'s deck is headed with a due date, in any language', () => {
  const { deckSlotLabel } = require('./deck-session.ts');
  for (const language of ['en', 'de', 'fr']) {
    const copy = lexiqueCopy(language);
    for (const card of [due, scene, fresh, { ...due, bucket: 'fragile' }, { ...due, bucket: 'linked' }]) {
      const label = deckSlotLabel(copy, card, slate);
      assert.ok(label, `${language}: ${card.bucket} has a header`);
      assert.doesNotMatch(label, /2026|novemb|Nov/i, `${language}: ${card.bucket} header carries a date`);
    }
  }
});
