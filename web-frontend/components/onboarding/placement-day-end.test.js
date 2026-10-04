// node --test components/onboarding/placement-day-end.test.js
//
// WP-126 — the placement offered at the end of the day (after the first
// completed ending), with skip and resume, in the learner's own language:
//
//   1. the state: hidden unless the server offers; hidden after an early stop;
//      «resume» when a placement is open; a quiet note once declined;
//   2. the card: a secondary action (the day keeps its own primary), «Pas
//      maintenant» beside it, the href, en/de/fr — no other language leaks;
//   3. the copy tables are complete and identical in shape;
//   4. the sign-up and placement pages no longer promise «after day three».

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

const realConsoleError = console.error;
console.error = (...args) => {
  const first = String(args[0] || '');
  if (first.includes('non-boolean attribute') || first.includes('useLayoutEffect')) return;
  realConsoleError(...args);
};

const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

const {
  PLACEMENT_DAY_END_HREF,
  PlacementDayEndOfferView,
  dayEndOfferState,
} = require('./PlacementDayEndOffer.tsx');
const { placementCopy } = require('@/lib/placement-copy.ts');

const h = React.createElement;
const noop = () => {};
const render = (state, language = 'en') =>
  renderToStaticMarkup(h(PlacementDayEndOfferView, { state, language, onSkip: noop }));

test('the offer shows only when the server makes it, and never after an early stop', () => {
  assert.equal(dayEndOfferState(null), 'hidden');
  assert.equal(dayEndOfferState({ offer: false }), 'hidden');
  assert.equal(dayEndOfferState({ offer: true, resume: false }), 'offer');
  assert.equal(dayEndOfferState({ offer: true, resume: true }), 'resume');
  assert.equal(dayEndOfferState({ offer: true }, { partial: true }), 'hidden');
  assert.equal(dayEndOfferState({ offer: true }, { declined: true }), 'declined');
  assert.equal(render('hidden'), '');
});

test('the card: a secondary action to the placement and «not now», never a second primary', () => {
  const html = render('offer', 'en');
  assert.ok(html.includes('Shall we check your level?'));
  assert.ok(html.includes(`href="${PLACEMENT_DAY_END_HREF.replace('&', '&amp;')}"`));
  assert.ok(html.includes('Take the level check'));
  assert.ok(html.includes('Not now'));
  assert.ok(html.includes('av2-btn--secondary'));
  assert.ok(!html.includes('av2-btn--primary'), 'the day keeps its own primary');
  assert.ok(html.includes('data-placement-offer="offer"'));
});

test('an open placement is offered for resuming', () => {
  const html = render('resume', 'de');
  assert.ok(html.includes('Ihre Einstufung ist noch offen'));
  assert.ok(html.includes('Einstufung fortsetzen'));
});

test('a declined offer leaves one quiet line pointing to Réglages', () => {
  const html = render('declined', 'fr');
  assert.ok(html.includes('Le bilan reste disponible dans les Réglages.'));
  assert.ok(html.includes('role="status"'));
  assert.ok(!html.includes('<a '));
});

test('the card speaks the learner’s language only', () => {
  const fr = render('offer', 'fr');
  const de = render('offer', 'de');
  const en = render('offer', 'en');
  assert.ok(fr.includes('Et si l’on vérifiait votre niveau ?'));
  assert.ok(de.includes('Sollen wir Ihr Niveau prüfen?'));
  for (const english of ['Shall we', 'Not now', 'level check']) {
    assert.ok(!de.includes(english), `de: ${english}`);
    assert.ok(!fr.includes(english), `fr: ${english}`);
  }
  for (const german of ['Einstufung', 'Jetzt nicht']) assert.ok(!en.includes(german), `en: ${german}`);
});

test('the day-end copy is complete in en, de and fr', () => {
  const keys = ['day_end_kicker', 'day_end_title', 'day_end_title_resume', 'day_end_lead', 'day_end_fine',
    'day_end_begin', 'day_end_resume', 'day_end_skip', 'day_end_skipped', 'chip'];
  for (const language of ['en', 'de', 'fr']) {
    const copy = placementCopy(language);
    for (const key of keys) assert.ok(String(copy[key] || '').trim(), `${language}.${key}`);
  }
  assert.deepEqual(Object.keys(placementCopy('en')).sort(), Object.keys(placementCopy('fr')).sort());
  assert.deepEqual(Object.keys(placementCopy('de')).sort(), Object.keys(placementCopy('fr')).sort());
});

test('nothing still promises the placement «after day three»', () => {
  for (const file of ['pages/auth/signup.tsx', 'lib/onboarding-signup.ts', 'pages/placement.tsx']) {
    const source = fs.readFileSync(path.join(WEB_ROOT, file), 'utf8');
    assert.ok(!/after (day three|three completed days)/i.test(source), file);
  }
});

test('when the day’s ending mounts the offer, it mounts it for a completed day only', () => {
  const recap = fs.readFileSync(path.join(WEB_ROOT, 'components/atelier-v2/journey/JourneyRecap.tsx'), 'utf8');
  if (!recap.includes('PlacementDayEndOffer')) return; // wired by the integration patch (WP-126 report)
  assert.match(recap, /<PlacementDayEndOffer[^>]*partial=\{partial\}/);
});
