// node --test components/gold/done-screen-language.test.js
//
// #694 — the Done screen («Fertig») and La Forge's end card read in one
// language: the learner's chrome language.
//
// Live walk 11 Nov 2026, English chrome: the Done screen said «Or +29 · 19 / 20
// vers la journée pleine» and the seal «11 nov.»; La Forge's end card printed a
// bare «11 · 11 · 26». Every line those screens derive comes from a function
// that now takes the chrome language; this test builds each line for an en, a
// de and a fr learner and fails on a word or a date of another language.
//
// The seal's ring line «Atelier · le feuilleton» is the publication's name (the
// masthead, as «L’Atelier» in the tab title) and stays French by the design
// contract (`lib/learner-language.ts`); it is the one exemption, and it is
// named here so nothing else can hide behind it.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..');
const REPO_ROOT = path.resolve(WEB_ROOT, '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  return originalResolve.call(this, request, ...rest);
};

const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const { Seal } = require('@/components/ui/Seal.tsx');
const gold = require('@/lib/gold-model.ts');
const recapModel = require('@/components/atelier-v2/journey/journey-recap-model.ts');

const MASTHEAD = 'Atelier · le feuilleton';

/** Words, dates and typography that only French chrome may print. */
const FRENCH = [
  /\bvers\b/, /journée/i, /\bpleine\b/i, /\bOr \+/, /\bfeuilles?\b/, /\bSceau\b/, /aujourd/i,
  /\bplafond\b/i, /\bépreuve\b/i, /\bpilonné\b/, /\bsemaine\b/i, /\bpas encore\b/,
  // A French short date: «11 nov.», «22 sept.», «mer. 11 nov.»
  /\d (janv|févr|mars|avr|mai|juin|juil|août|sept|oct|nov|déc)\.?(\s|$)/,
  /\b(lun|mar|mer|jeu|ven|sam|dim)\. \d/,
  /[éèêàçœ]/,
];
/** Words only English or German chrome prints. */
const NOT_FRENCH = [
  /\b(the|of|toward|full|today|leaf|leaves|Gold|Seal|week)\b/,
  /\b(von|Tag|heute|Blatt|Blättern|Blattgold|Siegel|Woche)\b/,
  /\d (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b/,
];
/** A numeric date with no language at all («11 · 11 · 26»). */
const BARE_DATE = /\b\d{1,2} · \d{1,2} · \d{2}\b/;

function assertChrome(language, where, text) {
  assert.ok(text, `${where} (${language}) is empty`);
  const shown = String(text).replace(MASTHEAD, '');
  assert.doesNotMatch(shown, BARE_DATE, `${where} (${language}) prints a bare numeric date: «${text}»`);
  if (language === 'fr') {
    for (const pattern of NOT_FRENCH) {
      assert.doesNotMatch(shown, pattern, `${where} (fr chrome) prints English or German: «${text}»`);
    }
    return;
  }
  for (const pattern of FRENCH) {
    assert.doesNotMatch(shown, pattern, `${where} (${language} chrome) prints French: «${text}»`);
  }
}

const view = (today = {}, week = {}) => ({
  visible: true,
  balance: 40,
  today: {
    local_date: '2026-11-11', settled: 29, earn_settled: 19, pending: 0, earned_before_plafond: 19,
    plafond: 'open', plafond_full_rate_up_to: 90, plafond_stops_at: 150, rhythm: 'regulier', mark: 20, pleine: false,
    ...today,
  },
  week: { week_id: '2026-W46', settled: 40, journees_pleines: 3, journees_pleines_goal: 5, days: [], ...week },
  entries: [],
});

const FIXTURE = JSON.parse(
  fs.readFileSync(path.join(REPO_ROOT, 'tests/fixtures/daily_journey_v1/public/completed.json'), 'utf8'),
).response;
const finishedDay = () => {
  const recap = { ...FIXTURE.recap, keepsake: { ...(FIXTURE.recap.keepsake || {}), local_date: '2026-11-11' } };
  return { journey: { ...FIXTURE, recap, status: 'completed', edition_no: 29 }, recap };
};

const LANGUAGES = ['en', 'de', 'fr'];

test('the Done screen’s gold line is in the chrome language and names its unit', () => {
  const unit = { en: /\bleaves\b/, de: /\bBlatt\b/, fr: /\bfeuilles\b/ };
  for (const language of LANGUAGES) {
    const toward = gold.tirageLine(view(), language);
    assertChrome(language, 'the tirage line', toward);
    assert.match(toward, unit[language], `the progress line (${language}) names what «19 / 20» counts: «${toward}»`);
    assert.match(toward, /19\D+20/, `the progress line (${language}) keeps the numbers: «${toward}»`);
    const full = gold.tirageLine(view({ settled: 48, earn_settled: 38, pleine: true }, { journees_pleines: 4 }), language);
    assertChrome(language, 'the full-day tirage line', full);
    assert.match(full, /4\D+5/, `the full-day line (${language}) keeps the week's count: «${full}»`);
  }
  assert.equal(gold.tirageLine({ visible: false }, 'en'), null);
});

test('the Done screen’s seal dates the day and names itself in the chrome language', () => {
  const { journey, recap } = finishedDay();
  for (const language of LANGUAGES) {
    const seal = recapModel.rewardView(journey, recap, language).seal;
    assert.ok(seal, 'a completed day presses a seal');
    assertChrome(language, 'the seal date', seal.date);
    // Rendered as the Done screen renders it (pages/fertig.tsx).
    const html = renderToStaticMarkup(
      React.createElement(Seal, {
        stamp: true, size: 'lg', variant: seal.variant, no: seal.no, date: seal.date ?? '', label: seal.label,
        rings: seal.rings, ringsLabel: seal.ringsLabel, gold: 0.95, goldLabel: gold.tirageLine(view(), language),
      }),
    );
    const label = /aria-label="([^"]*)"/.exec(html)[1].replace(/&#x27;/g, '\'').replace(/&amp;/g, '&');
    assertChrome(language, 'the seal’s accessible name', label);
    const ring = [...html.matchAll(/<textPath[^>]*>([^<]*)<\/textPath>/g)].map((m) => m[1]).join(' · ');
    assertChrome(language, 'the seal’s ring lines', ring);
  }
});

test('«D’où vient ton or», opened from the Done screen, explains itself in the chrome language', () => {
  for (const language of LANGUAGES) {
    assertChrome(language, 'the pending note', gold.todayNote(view({ pending: 5 }), language));
    assertChrome(language, 'the half-rate note', gold.todayNote(view({ plafond: 'half' }), language));
    assertChrome(language, 'the closed note', gold.todayNote(view({ plafond: 'closed' }), language));
    const pulped = { id: 'v', amount: 2, state: 'void', void_reason: 'not_yet', local_date: '2026-11-11' };
    assertChrome(language, 'a pulped entry', gold.voidLine(pulped, language));
    assertChrome(language, 'a ledger day', gold.dayLabel('2026-11-11', language));
  }
});

test('the gold copy is complete in en, de and fr', () => {
  const { goldCopy } = require('@/lib/gold-model.ts');
  const fr = goldCopy('fr');
  for (const language of ['en', 'de']) {
    assert.deepEqual(Object.keys(goldCopy(language)).sort(), Object.keys(fr).sort(), `${language} keys`);
  }
  assert.equal(goldCopy('fr').remembered, 'Tu t’en souvenais.', 'the ×2 line is the spec’s');
});

test('La Forge’s end card dates the séance in the chrome language, never «11 · 11 · 26»', () => {
  const page = fs.readFileSync(path.join(WEB_ROOT, 'pages/atelier.tsx'), 'utf8');
  const head = /<EpRecapHead date=\{([^}]*\}?[^}]*)\} \/>/.exec(page);
  assert.ok(head, 'the recap renders EpRecapHead');
  assert.doesNotMatch(head[1], /Datestamp|Classée/, `the end card's date is a bare numeric stamp: ${head[1]}`);
  assert.match(head[1], /\blanguage\b/, `the end card's date reads the chrome language: ${head[1]}`);

  const { chromeDate } = require('@/lib/chrome-locale.ts');
  const day = new Date(2026, 10, 11, 12);
  for (const language of LANGUAGES) assertChrome(language, 'the Forge end date', chromeDate(day, language, 'heading'));
  assert.equal(chromeDate(day, 'en', 'heading'), 'Wednesday 11 Nov');
  assert.equal(chromeDate(day, 'de', 'heading'), 'Mittwoch, 11. Nov.');
  assert.equal(chromeDate(day, 'fr', 'heading'), 'Mercredi 11 nov.');
});
