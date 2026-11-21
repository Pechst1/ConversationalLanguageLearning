// node --test components/atelier-v2/home/r2-journal-after-day.test.js
//
// R2 (4) — the Journal chip stays while a retell waits, whatever the day's state.
// Walk 2026-11-17: A1 day 2 and B1 day 6 saw «Gestern erzählen» / «Raconter hier»
// before and during the day and lost it the moment the day was done («Journée
// bouclée … Nouvelle lettre ≈ 3 min»; B1 had to type /notebook?mode=journal). A
// finished day's Home draws ONE chip (HomeScreen's `chipRoom`) and the letter
// held it. On a finished day the retell is now the first chip.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..', '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  if (request === 'next/link') {
    return originalResolve.call(this, path.join(WEB_ROOT, 'components/feuilleton/reader/__fixtures__/next-link-stub.js'), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

const apiPath = Module._resolveFilename('@/services/api', module, false);
require.cache[apiPath] = {
  id: apiPath,
  filename: apiPath,
  loaded: true,
  exports: { __esModule: true, default: {}, apiService: {} },
};

const realConsoleError = console.error;
console.error = (...args) => {
  const first = String(args[0] || '');
  if (first.includes('non-boolean attribute') || first.includes('useLayoutEffect')) return;
  realConsoleError(...args);
};

const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
global.React = React;

const { HomeScreen } = require('./HomeScreen.tsx');
const { dayMarkState } = require('../journey/day-mark.ts');
const { atelierCopy } = require('@/lib/atelier-v2-copy.ts');
const journal = require('@/lib/journal-home.ts');

const h = React.createElement;
const read = (relative) => fs.readFileSync(path.join(WEB_ROOT, relative), 'utf8');

const letter = (language) => ({
  id: 'courrier',
  label: atelierCopy(language).home_letter,
  ariaLabel: atelierCopy(language).home_letter_aria,
  href: '/missions',
  shape: 'story',
});

function home(language, { dayDone }) {
  const chip = journal.journalHomeChip({ daysAgo: 1 }, language);
  return renderToStaticMarkup(
    h(HomeScreen, {
      dateLabel: 'mardi 18 novembre',
      editionLabel: 'Édition Nº 4 · A1.1',
      streak: 4,
      level: { band: 'A1.1', percent: 60 },
      language,
      day: dayMarkState(null, language),
      dayDone,
      chips: journal.withJournalChip([letter(language)], chip, false, dayDone),
    }),
  );
}

test('a finished day: the waiting retell is the first chip, the one Home draws', () => {
  const chip = journal.journalHomeChip({ daysAgo: 1 }, 'de');
  assert.deepEqual(
    journal.withJournalChip([letter('de'), { id: 'revue' }], chip, false, true).map((c) => c.id),
    ['journal', 'courrier', 'revue'],
  );
  for (const language of ['de', 'en', 'fr']) {
    const html = home(language, { dayDone: true });
    assert.match(html, /data-chip="journal"/, `${language}: the retell is on a finished day's Home`);
    assert.match(html, /href="\/notebook\?mode=journal"/, language);
  }
});

test('before and during the day: unchanged, second after the letter, both drawn', () => {
  const chip = journal.journalHomeChip({ daysAgo: 1 }, 'fr');
  assert.deepEqual(journal.withJournalChip([letter('fr')], chip, false, false).map((c) => c.id), ['courrier', 'journal']);
  const html = home('fr', { dayDone: false });
  assert.match(html, /data-chip="courrier"/);
  assert.match(html, /data-chip="journal"/);
  // Sent or skipped: no chip at all, finished day or not.
  assert.deepEqual(journal.withJournalChip([letter('fr')], null, false, true).map((c) => c.id), ['courrier']);
});

test('Home passes the day\'s state to the journal chip', () => {
  const page = read('pages/atelier.tsx');
  assert.match(page, /homeDay \? journalHomeChip\(journalWaiting, chromeLanguage\) : null,\s*Boolean\(revueEntry\.hero\),\s*homeChip\.dayDone,/);
  // The day's state is read before the chips are built.
  assert.ok(page.indexOf('const homeChip = homeDayChip(') < page.indexOf('const homeChips: HomeChip[]'));
});
