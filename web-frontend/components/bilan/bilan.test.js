// node --test components/bilan/bilan.test.js
//
// «Le bilan», the page model:
//   1. the copy: the same keys and placeholders in fr / en / de; the place's name French;
//   2. the client: a bare 404 is «switched off», the wire is parsed and cleaned;
//   3. the headline is true to the week: several days, one day (short and warm), none;
//   4. a section with nothing in it is not drawn; a rule's move uses the Cahier's words;
//   5. Home's card: the last closed played week, until opened or dismissed;
//   6. the page renders the corrected lines, the days and one primary action.

const assert = require('node:assert/strict');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '../..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

const { BILAN_COPIES, bilanCopy, fill } = require('./bilan-copy.ts');
const model = require('./bilan-model.ts');
const { bilanFixture } = require('./bilan-fixtures.ts');
const { createBilanClient, bilanHref } = require('../../lib/bilan-api.ts');
const { parseBilan } = require('../../lib/bilan-types.ts');

const holes = (s) => (s.match(/\{\w+\}/g) || []).sort().join(',');
const memoryStore = () => {
  const map = new Map();
  return { get: (k) => (map.has(k) ? map.get(k) : null), set: (k, v) => map.set(k, v) };
};

test('the copy has the same keys and placeholders in every language', () => {
  const keys = Object.keys(BILAN_COPIES.fr).sort();
  for (const language of ['en', 'de']) {
    const table = BILAN_COPIES[language];
    assert.deepEqual(Object.keys(table).sort(), keys, language);
    for (const key of keys) assert.equal(holes(table[key]), holes(BILAN_COPIES.fr[key]), `${language}.${key}`);
  }
  for (const language of ['en', 'de', 'fr']) assert.equal(bilanCopy(language).page_title, 'Le bilan');
  assert.equal(bilanCopy('xx'), BILAN_COPIES.en);
});

test('the client reads the week, and a bare 404 is the switch off', async () => {
  const calls = [];
  const client = createBilanClient({
    get: async (url) => {
      calls.push(url);
      return bilanFixture('full', 'de');
    },
  });
  const result = await client.week('2026-11-16');
  assert.equal(calls[0], '/bilan?week=2026-11-16');
  assert.equal(result.enabled, true);
  assert.equal(result.bilan.daysPlayed, 4);
  assert.equal(result.bilan.lines[0].textFr, 'Je voudrais un café et un croissant.');

  const off = createBilanClient({ get: async () => Promise.reject({ response: { status: 404 } }) });
  assert.deepEqual(await off.week(), { enabled: false });
  assert.deepEqual(await off.card(), { enabled: false });
  const down = createBilanClient({ get: async () => Promise.reject({ response: { status: 500 } }) });
  await assert.rejects(() => down.week(), /server/);
  assert.equal(bilanHref(null), '/bilan');
  assert.equal(bilanHref('2026-11-16'), '/bilan?week=2026-11-16');
});

test('the parser drops what it cannot read', () => {
  const raw = bilanFixture('full', 'en');
  raw.lines.push({ text_fr: '   ', date: '2026-11-16', source: 'scene' });
  raw.words.shown.push({ word: 'sans glose' });
  const bilan = parseBilan(raw);
  assert.equal(bilan.lines.length, 4);
  assert.equal(bilan.words.shown.length, 5);
  assert.throws(() => parseBilan({}));
});

test('the headline is true to the week', () => {
  const copy = bilanCopy('en');
  const full = parseBilan(bilanFixture('full', 'en'));
  assert.deepEqual(model.bilanHeadline(full, copy), { title: '4 days in the story this week.', body: null });
  assert.equal(model.bilanHeadline({ ...full, isCurrent: true }, copy).title, '4 days in the story so far.');
  const thin = parseBilan(bilanFixture('thin', 'en'));
  assert.deepEqual(model.bilanHeadline(thin, copy), {
    title: 'One day this week.',
    body: 'A short week, and a real one. Here is what it left.',
  });
  const empty = parseBilan(bilanFixture('empty', 'de'));
  const de = bilanCopy('de');
  assert.equal(model.bilanHeadline(empty, de).title, 'Eine stille Woche.');
  assert.equal(model.bilanHeadline({ ...empty, isCurrent: true }, de).title, 'Die Woche fängt gerade an.');
  // No praise anywhere: the copy never cheers.
  for (const table of Object.values(BILAN_COPIES)) {
    for (const line of Object.values(table)) assert.doesNotMatch(line, /!|great|bravo|super|toll|génial/i);
  }
});

test('dates and ranges follow the language', () => {
  assert.equal(model.weekRange('2026-11-16', '2026-11-22', 'fr'), '16–22 novembre');
  assert.equal(model.weekRange('2026-11-16', '2026-11-22', 'en'), '16–22 November');
  assert.equal(model.weekRange('2026-11-16', '2026-11-22', 'de'), '16.–22. November');
  assert.match(model.weekRange('2026-10-26', '2026-11-01', 'en'), /^26 Oct – 1 Nov$/);
  assert.equal(model.weekdayInitial('2026-11-16', 'fr'), 'L');
  assert.equal(model.weekdayInitial('2026-11-18', 'de'), 'M');
  assert.equal(model.bilanKicker(parseBilan(bilanFixture('full', 'fr')), bilanCopy('fr')), 'Semaine du 16–22 novembre');
});

test('only sections with something to say, rules in the Cahier’s words', () => {
  const thin = parseBilan(bilanFixture('thin', 'fr'));
  assert.deepEqual(model.bilanSections(thin), { lines: true, words: true, rules: false, story: true });
  const empty = parseBilan(bilanFixture('empty', 'fr'));
  assert.deepEqual(model.bilanSections(empty), { lines: false, words: false, rules: false, story: false });
  const copy = bilanCopy('de');
  const full = parseBilan(bilanFixture('full', 'de'));
  assert.deepEqual(full.rules.map((rule) => model.ruleMove(rule, copy)), [
    'diese Woche kennengelernt · in Übung',
    'in Übung → gefestigt',
  ]);
  assert.deepEqual(model.wordLines(full, bilanCopy('en')), ['14 new words met', '26 words held in review']);
  assert.deepEqual(model.wordLines(thin, bilanCopy('fr')), ['3 nouveaux mots rencontrés', '4 mots tenus en révision']);
});

test('Home’s card: the last closed played week, until opened or dismissed', () => {
  const store = memoryStore();
  assert.equal(model.cardWeek({ weekStart: null, daysPlayed: 0 }, store), null);
  assert.equal(model.cardWeek({ weekStart: '2026-11-16', daysPlayed: 0 }, store), null);
  assert.equal(model.cardWeek({ weekStart: '2026-11-16', daysPlayed: 2 }, store), '2026-11-16');
  model.markBilanSeen('2026-11-16', store);
  assert.equal(model.cardWeek({ weekStart: '2026-11-16', daysPlayed: 2 }, store), null);
  assert.equal(model.cardWeek({ weekStart: '2026-11-23', daysPlayed: 1 }, store), '2026-11-23');
  assert.deepEqual(model.cardLines({ weekStart: '2026-11-16', daysPlayed: 1 }, 'fr', bilanCopy('fr')), {
    title: 'Ta semaine, 16–22 novembre',
    meta: '1 jour joué',
  });
  assert.equal(fill('{n} jours', { n: 3 }), '3 jours');
});

test('the page draws the corrected lines, the days and one primary action', () => {
  const { BilanView } = require('./BilanView.tsx');
  const bilan = parseBilan(bilanFixture('full', 'en'));
  const html = renderToStaticMarkup(
    React.createElement(BilanView, { bilan, copy: bilanCopy('en'), onContinue: () => undefined, hrefFor: () => '#' }),
  );
  assert.match(html, /What you can say now/);
  assert.match(html, /Tu peux me prêter ta clé ce soir \?/);
  assert.equal((html.match(/bl-week__day/g) || []).length, 7);
  assert.equal((html.match(/data-played=""/g) || []).length, 4);
  assert.equal((html.match(/av2-btn--primary/g) || []).length, 1);
  assert.match(html, /data-saucers="4"/);
  assert.match(html, /practising → held/);

  const empty = renderToStaticMarkup(
    React.createElement(BilanView, {
      bilan: parseBilan(bilanFixture('empty', 'en')),
      copy: bilanCopy('en'),
      onContinue: () => undefined,
    }),
  );
  assert.doesNotMatch(empty, /id="bl-(lines|words|rules|story)"|data-saucers/);
  assert.match(empty, /The story is waiting where you left it\./);
});

test('a choice card reads under its episode; the rest stands on its own', () => {
  const bilan = parseBilan(bilanFixture('full', 'fr'));
  const rows = model.storyRows(bilan);
  assert.deepEqual(rows.episodes.map((row) => row.choices.map((c) => c.labelFr)), [[], ['Je la prends.'], []]);
  assert.deepEqual(rows.rest.map((d) => d.kind), ['resolved']);
});
