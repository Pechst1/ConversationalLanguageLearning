// node --test components/carte/carte-entry.test.js
//
// WP-120 phase D · the ways onto La Carte.
//
//   1. the Relevé's badge: a France silhouette with the pin count, linking to /carte;
//      nothing at zero; it reads `counts.france` from GET /revue/carte;
//   2. the close screen: «Voir sur la carte» under «Classer le Papier», linking to
//      /carte?focus=<session_id>, in the learner's chrome;
//   3. `focus`: the named Papier's card is open on load, on its own level; an
//      unknown id opens nothing and leaves the level alone.

const assert = require('node:assert/strict');
const { test } = require('node:test');

const { h, render, visibleText } = require('../revue/revue-test-setup');

const { carteCopy } = require('./carte-copy.ts');
const { CARTE_MOCK_VIEW } = require('./carte-mock.ts');
const { Carte } = require('./Carte.tsx');
const { CarteBadge, CARTE_HREF } = require('./CarteBadge.tsx');
const { RvCloseCarteLink, carteFocusHref } = require('../revue/RvClose.tsx');

const FR = carteCopy('fr');
const PINS = CARTE_MOCK_VIEW.pins;
const noop = () => undefined;

// --- 1. the badge ----------------------------------------------------------

test('the badge draws France, the count, and links to /carte', () => {
  const html = render(h(CarteBadge, { count: 6 }));
  assert.equal(CARTE_HREF, '/carte');
  assert.match(html, /^<a [^>]*href="\/carte"/);
  assert.match(html, /aria-label="La Carte · 6 Papiers"/);
  assert.match(html, /data-carte-badge="6"/);
  assert.match(html, /<svg class="carte-badge__france"[^>]*aria-hidden="true"/);
  assert.match(html, /<span class="carte-badge__count" aria-hidden="true">6<\/span>/);
  assert.equal(visibleText(html), 'La Carte 6');
});

test('the badge speaks the chrome language and says nothing at zero', () => {
  assert.match(render(h(CarteBadge, { count: 1, language: 'en' })), /aria-label="La Carte · 1 Papier, open the map"/);
  assert.match(render(h(CarteBadge, { count: 3, language: 'de' })), /aria-label="La Carte · 3 Papiers, Karte öffnen"/);
  assert.equal(render(h(CarteBadge, { count: 0 })), '');
});

test('the badge’s number is counts.france of GET /revue/carte; off is no badge', async () => {
  // A static render runs no effect: the badge's fetch is checked on the client it uses.
  const { createCarteClient } = require('../../lib/carte-api.ts');
  const live = createCarteClient({ get: async (url) => (assert.equal(url, '/revue/carte'), { pins: [], quartier: [], counts: { france: 4, idf: 3, paris: 2 } }) });
  const result = await live.carte();
  assert.equal(result.enabled && result.view.counts.france, 4);
  const off = createCarteClient({ get: async () => { throw { response: { status: 404 } }; } });
  assert.deepEqual(await off.carte(), { enabled: false });
  // Before the read lands the badge draws nothing (no flash of a zero).
  assert.equal(render(h(CarteBadge, { client: live })), '');
});

// --- 2. the close screen ------------------------------------------------------

test('the close links to its own pin: /carte?focus=<session_id>', () => {
  assert.equal(carteFocusHref('3f2c-a b'), '/carte?focus=3f2c-a%20b');
  const html = render(h(RvCloseCarteLink, { sessionId: 'sess-42', language: 'fr' }));
  assert.match(html, /^<a [^>]*href="\/carte\?focus=sess-42"/);
  assert.match(html, /class="av2-btn av2-btn--quiet"/);
  assert.match(html, /data-carte-focus="sess-42"/);
  assert.equal(visibleText(html), 'Voir sur la carte');
  assert.equal(visibleText(render(h(RvCloseCarteLink, { sessionId: 's', language: 'en' }))), 'See it on the map');
  assert.equal(visibleText(render(h(RvCloseCarteLink, { sessionId: 's', language: 'de' }))), 'Auf der Karte ansehen');
});

test('the close screen shows «Voir sur la carte» right under «Classer le Papier»', () => {
  const fs = require('node:fs');
  const path = require('node:path');
  const source = fs.readFileSync(path.join(__dirname, '../revue/RvEncounter.tsx'), 'utf8');
  const foot = source.slice(source.indexOf('{copy.file_revue}'));
  const link = foot.indexOf('<RvCloseCarteLink sessionId={session.id}');
  assert.ok(link > 0, 'RvEncounter mounts RvCloseCarteLink in the close foot');
  assert.ok(link < foot.indexOf('{copy.see_releve}'), 'the map comes before «Voir le Relevé»');
  assert.ok(foot.indexOf('</Action>') < link, 'and after «Classer le Papier»');
});

// --- 3. focus ---------------------------------------------------------------------

test('focus opens that Papier’s card on load, on the level that draws it', () => {
  const aligre = PINS.find((p) => p.sessionId === 'mock-aligre');
  assert.equal(aligre.level, 'paris');
  const html = render(h(Carte, { pins: PINS, copy: FR, onRelire: noop, onReleve: noop, focusSessionId: 'mock-aligre', mapPx: 358, drawings: { paris: '<svg/>', france: '<svg/>' } }));
  assert.match(html, /<section class="carte" data-level="paris"/);
  assert.match(html, /role="dialog"/);
  assert.match(html, /class="carte-card" data-session="mock-aligre"/);
  assert.match(html, /<h2[^>]*class="av2-headline">Les fruits et légumes coûtent plus cher<\/h2>/);
});

test('focus on a Papier outside Paris opens on France; an unknown id opens nothing', () => {
  const far = PINS.find((p) => p.level === 'france');
  assert.ok(far, 'the mock has a pin outside the Île-de-France');
  const html = render(h(Carte, { pins: PINS, copy: FR, onRelire: noop, onReleve: noop, focusSessionId: far.sessionId, mapPx: 358, drawings: { france: '<svg/>' } }));
  assert.match(html, /<section class="carte" data-level="france"/);
  assert.match(html, new RegExp(`class="carte-card" data-session="${far.sessionId}"`));
  const none = render(h(Carte, { pins: PINS, copy: FR, onRelire: noop, onReleve: noop, focusSessionId: 'nope', initialLevel: 'idf', mapPx: 358, drawings: { idf: '<svg/>' } }));
  assert.match(none, /<section class="carte" data-level="idf"/);
  assert.doesNotMatch(none, /role="dialog"/);
});
