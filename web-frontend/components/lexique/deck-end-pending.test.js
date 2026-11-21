// node --test components/lexique/deck-end-pending.test.js
//
// Main's walk, run 43073091897 (en A1.1 day 6): the day's deck went through «33/33» and the
// page showed only its header and the count, nothing to tap, while it asked the server for
// the next dose or the day's next step. Every state of the finished day deck shows something:
// the next step, the fallback continuation, or, while it waits, a busy block that says so.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');

const source = fs.readFileSync(path.join(__dirname, '..', '..', 'pages/vocabulary/review.tsx'), 'utf8');

test('the finished day deck says it is busy while it waits for what comes next', () => {
  const gap = source.match(/\{!loading && !loadError && !current && daySession\?\.kind === 'day' && !dayNext && !dayFallback && \(([\s\S]*?)\)\}/);
  assert.ok(gap, 'a block for the wait between the last card and the day\'s next step');
  assert.match(gap[1], /<StateBlock tone="loading" title=\{dayLeft > 0 \? t\.opening_deck : daySessionCopy\(language\)\.words_done\} \/>/);
});

test('the wait, the next step and the fallback cover every finished day deck between them', () => {
  // The next step shows when the plan named one, the continuation when its read failed; the
  // wait covers the rest. A day deck with neither and no wait block is the empty «33/33» page.
  assert.match(source, /\{!loading && !loadError && !current && dayNext && \(/);
  assert.match(source, /\{!loading && !loadError && !current && !dayNext && \(daySession\?\.kind !== 'day' \|\| dayFallback\) && \(/);
});

test('the busy block\'s words exist in en, de and fr', () => {
  const day = fs.readFileSync(path.join(__dirname, '..', '..', 'lib/day-session.ts'), 'utf8');
  for (const words of ['Wörter geschafft', 'Mots terminés', 'Words done']) {
    assert.match(day, new RegExp(`words_done: '${words}'`));
  }
  assert.match(source, /opening_deck/);
});
