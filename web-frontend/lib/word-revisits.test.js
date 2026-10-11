// node --test lib/word-revisits.test.js
//
// WP-93 — «Revu dans l'épisode du 12 sept.»: the word biography's revisit rows.

const assert = require('node:assert/strict');
const path = require('node:path');
const { test } = require('node:test');

require(path.join(__dirname, '..', 'node_modules/sucrase/register/ts'));

const { formatRevisitDate, revisitRows, MAX_REVISIT_ROWS } = require('./word-revisits.ts');

test('a calendar date is that day in the learner’s language, in every timezone', () => {
  assert.equal(formatRevisitDate('2026-09-12', 'fr-FR'), '12 sept.');
  assert.equal(formatRevisitDate('2026-09-12', 'en-GB'), '12 Sept');
  assert.equal(formatRevisitDate('2026-09-12', 'de-DE'), '12. Sept.');
  assert.equal(formatRevisitDate('2026-01-01', 'fr-FR'), '1 janv.', 'midnight UTC never slips to the day before');
  assert.equal(formatRevisitDate('not a date', 'fr-FR'), '');
  assert.equal(formatRevisitDate(null, 'fr-FR'), '');
});

test('rows: newest first, one per episode, three at most, undated entries dropped', () => {
  const rows = revisitRows(
    [
      { date: '2026-09-02', scene_title_fr: 'Le marché' },
      { date: '2026-09-12', scene_title_fr: 'La fête du quartier' },
      { date: 'soon', scene_title_fr: 'Sans date' },
      { date: '2026-09-12', scene_title_fr: 'La fête du quartier' },
      { date: '2026-09-08', scene_title_fr: '  Le Mistral ' },
      { date: '2026-08-30', scene_title_fr: 'Trop ancien' },
      null,
    ],
    'fr-FR',
    'Revu dans l’épisode du {date}',
  );
  assert.equal(MAX_REVISIT_ROWS, 3);
  assert.deepEqual(
    rows.map((row) => [row.label, row.title]),
    [
      ['Revu dans l’épisode du 12 sept.', 'La fête du quartier'],
      ['Revu dans l’épisode du 8 sept.', 'Le Mistral'],
      ['Revu dans l’épisode du 2 sept.', 'Le marché'],
    ],
  );
  assert.equal(new Set(rows.map((row) => row.key)).size, rows.length);
});

test('older payloads print nothing', () => {
  assert.deepEqual(revisitRows(undefined, 'en-GB', 'Seen again in the episode of {date}'), []);
  assert.deepEqual(revisitRows(null, 'en-GB', '{date}'), []);
  assert.deepEqual(revisitRows([], 'en-GB', '{date}'), []);
  assert.equal(
    revisitRows([{ date: '2026-09-12' }], 'en-GB', 'Seen again in the episode of {date}')[0].label,
    'Seen again in the episode of 12 Sept',
  );
});
