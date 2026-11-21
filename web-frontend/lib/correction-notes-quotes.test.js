// node --test lib/correction-notes-quotes.test.js
//
// R5 (check walk of 19 Nov, A1, German): «„Tu est bavard ? “ stimmt nicht; richtig ist
// „Tu es bavard ? Mit «tu» …» — the note was cut into sentences at every «?», inside the
// quotes, and glued back with spaces; the lone «“.» was dropped. A note keeps its quotes.

const assert = require('node:assert/strict');
const path = require('node:path');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
const { dedupeNotes, correctionNotes } = require('./correction-notes.ts');

const balanced = (text) => {
  const count = (re) => (text.match(re) || []).length;
  return count(/„/g) === count(/“/g) && count(/«/g) === count(/»/g);
};

test('a German judgement note keeps its quotes and its stops (R5)', () => {
  const why = '„Tu est bavard ?“ stimmt nicht; richtig ist „Tu es bavard ?“. Mit «tu» heißt «être» «es», nicht «est».';
  const [note] = correctionNotes({ note_native: why });
  assert.equal(note, why);
  assert.ok(balanced(note));
});

test('the same note in French and English quotes stays whole too', () => {
  for (const why of [
    '« Tu est bavard ? » n’est pas correcte ; il faut « Tu es bavard ? ».',
    '“Tu est bavard ?” is not right; it should be “Tu es bavard ?”.',
  ]) {
    assert.deepEqual(dedupeNotes([why]), [why]);
  }
});

test('a sentence said twice is still said once', () => {
  assert.deepEqual(
    dedupeNotes(['„Ils a“ stimmt nicht. Mit ils heißt es ont.', 'Mit ils heißt es ont.']),
    ['„Ils a“ stimmt nicht. Mit ils heißt es ont.'],
  );
});
