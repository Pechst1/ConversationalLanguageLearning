// node --test components/carte/carte.test.js
//
// WP-120 phase C · La Carte, client side.
//
//   1. projection: the client lands every check point of carte-projection.json
//      within 2 svg units of where scripts/geo/build_carte.py put it, and a point
//      off a drawing is `null`;
//   2. clustering: marks closer than 28 px merge (count, centroid), farther ones don't;
//      a cluster zooms when it all lies on the next drawing, else lists;
//   3. levels: France shows every pin, the Île-de-France and Paris only theirs, with
//      the rest counted as «ailleurs»; «Mon quartier» only on the Paris level;
//   4. the mock: six pins; from France, the Paris pins cluster; from Paris, three
//      separate pins and the Assemblée/Drouant pair;
//   5. the empty state;
//   6. the card: headline, week and place, kept words as tokens, the learner's
//      words marked with «toi», «Relire» and «Dans le Relevé»;
//   7. the wire parser: snake_case → camelCase, defensive.

const assert = require('node:assert/strict');
const { test } = require('node:test');

const { h, render, visibleText } = require('../revue/revue-test-setup');

const projection = require('./carte-projection.ts');
const model = require('./carte-model.ts');
const { carteCopy } = require('./carte-copy.ts');
const { CARTE_MOCK_VIEW } = require('./carte-mock.ts');
const { Carte, CarteEmpty, CartePinCard } = require('./index.ts');
const types = require('../../lib/carte-types.ts');
const { createCarteClient } = require('../../lib/carte-api.ts');

const FR = carteCopy('fr');
const PINS = CARTE_MOCK_VIEW.pins;
const noop = () => undefined;

const pin = (id, lat, lon, extra = {}) => ({
  sessionId: id, dossierId: id, week: '2026-W40', closedAt: null, placeLabelFr: id, lat, lon,
  precision: 'exact', level: 'paris', headlineFr: id, keptWords: [], contributionKind: null,
  contributionFr: null, contributionSpans: [], questionFr: null, plateUrl: null, vignette: null, ...extra,
});

// --- 1. projection ---------------------------------------------------------

test('every check point of the projection file lands within 2 svg units', () => {
  const { checks, fallback } = projection.CARTE_PROJECTION;
  assert.equal(fallback, false);
  assert.ok(checks.length >= 9);
  for (const check of checks) {
    const point = projection.projectPoint(check.drawing, check.lat, check.lon);
    assert.ok(point, check.label);
    assert.ok(Math.abs(point[0] - check.x) <= 2 && Math.abs(point[1] - check.y) <= 2, `${check.label}: ${point} vs ${check.x},${check.y}`);
  }
});

test('Lambert-93 puts the projection origin at (700 000, 6 600 000) and Paris north of Lyon', () => {
  const [x, y] = projection.lambert93(46.5, 3);
  assert.ok(Math.abs(x - 700000) < 0.01 && Math.abs(y - 6600000) < 0.01);
  const paris = projection.projectPoint('france', 48.8566, 2.3522);
  const lyon = projection.projectPoint('france', 45.764, 4.8357);
  assert.ok(paris[1] < lyon[1] && paris[0] < lyon[0]);
});

test('a point off a drawing is null; an overseas one lands in its inset box', () => {
  assert.equal(projection.projectPoint('paris', 45.764, 4.8357), null);
  assert.equal(projection.projectPoint('idf', 47.05, 4.83), null);
  assert.equal(projection.projectPoint('france', 40.4, -3.7), null); // Madrid
  const reunion = projection.CARTE_PROJECTION.drawings.france.insets.find((i) => i.code === '974');
  const [x, y] = projection.projectPoint('france', -21.115, 55.536);
  const [bx, by, bw, bh] = reunion.box;
  assert.ok(x > bx && x < bx + bw && y > by && y < by + bh);
});

// --- 2. clustering ---------------------------------------------------------

test('marks closer than 28 px cluster, farther ones stay apart', () => {
  const placed = [
    { item: 'a', x: 100, y: 100 },
    { item: 'b', x: 110, y: 100 },
    { item: 'c', x: 300, y: 100 },
  ];
  // 1 px per unit: a and b are 10 px apart, c is 190 px away.
  const one = model.clusterPlaced(placed, 1, (s) => s);
  assert.deepEqual(one.map((c) => c.members.length), [2, 1]);
  assert.equal(one[0].x, 105);
  assert.equal(one[0].id, 'a');
  // 0.1 px per unit: everything within 28 px.
  assert.deepEqual(model.clusterPlaced(placed, 0.1, (s) => s).map((c) => c.members.length), [3]);
  // 3 px per unit: a and b are 30 px apart.
  assert.deepEqual(model.clusterPlaced(placed, 3, (s) => s).map((c) => c.members.length), [1, 1, 1]);
});

test('a cluster zooms when it is all on the next drawing, else it lists', () => {
  const paris = model.layoutLevel('france', PINS).clusters.find((c) => c.members.length > 1);
  assert.deepEqual(model.clusterTarget('france', paris), { kind: 'zoom', level: 'idf' });
  const lyon = { id: 'x', x: 0, y: 0, members: [pin('l1', 45.764, 4.8357), pin('l2', 45.76, 4.84)].map((item) => ({ item, x: 0, y: 0 })) };
  assert.deepEqual(model.clusterTarget('france', lyon), { kind: 'list' });
  const same = { id: 'y', x: 0, y: 0, members: [pin('p1', 48.849, 2.378), pin('p2', 48.849, 2.378)].map((item) => ({ item, x: 0, y: 0 })) };
  assert.deepEqual(model.clusterTarget('paris', same), { kind: 'list' });
});

// --- 3. levels -----------------------------------------------------------------

test('levels: France shows all, Île-de-France and Paris only theirs, the rest «ailleurs»', () => {
  const france = model.layoutLevel('france', PINS);
  const idf = model.layoutLevel('idf', PINS);
  const paris = model.layoutLevel('paris', PINS);
  const count = (layout) => layout.clusters.reduce((n, c) => n + c.members.length, 0);
  assert.deepEqual([count(france), count(idf), count(paris)], [6, 5, 5]);
  assert.deepEqual([france.elsewhere, idf.elsewhere, paris.elsewhere], [0, 1, 1]);
  assert.equal(model.nextLevel('france'), 'idf');
  assert.equal(model.nextLevel('paris'), null);
  assert.equal(model.previousLevel('paris'), 'idf');
  // «Mon quartier» is laid out on the Paris level only.
  assert.equal(model.layoutLevel('idf', PINS, { quartier: CARTE_MOCK_VIEW.quartier }).quartier.length, 0);
  const quartier = model.layoutLevel('paris', PINS, { quartier: CARTE_MOCK_VIEW.quartier }).quartier;
  // Le Mistral and the quai de Valmy are 120 m apart: one square, two names.
  assert.deepEqual(quartier.map((c) => c.members.map((m) => m.item.id)), [['le_mistral', 'quai_de_valmy'], ['buttes_chaumont']]);
});

test('the level switches: the «France» corner on idf/paris, the quartier toggle on Paris only', () => {
  const at = (level) => render(h(Carte, { pins: PINS, quartier: CARTE_MOCK_VIEW.quartier, copy: FR, onRelire: noop, onReleve: noop, initialLevel: level, drawings: { [level]: '<svg/>' } }));
  const france = at('france');
  assert.match(france, /data-level="france"/);
  assert.doesNotMatch(france, /carte__france/);
  assert.doesNotMatch(france, /Mon quartier/);
  const idf = at('idf');
  assert.match(idf, /class="av2-chip carte__france"[^>]*aria-label="Revenir à la carte de France"/);
  assert.match(visibleText(idf), /Île-de-France 5 Papiers/);
  assert.match(visibleText(idf), /1 Papier ailleurs en France/);
  assert.doesNotMatch(idf, /Mon quartier/);
  const paris = at('paris');
  assert.match(paris, /aria-pressed="false"[^>]*>[\s\S]*?Mon quartier/);
});

// --- 4. the mock ------------------------------------------------------------------

test('the mock: six pins; from France the Paris ones cluster, Bourgogne stands alone with a wide ring', () => {
  assert.equal(PINS.length, 6);
  const html = render(h(Carte, { pins: PINS, copy: FR, onRelire: noop, onReleve: noop, drawings: { france: '<svg/>' } }));
  const clusters = [...html.matchAll(/class="carte-cluster" data-count="(\d+)"/g)].map((m) => Number(m[1]));
  const singles = [...html.matchAll(/class="carte-pin" data-precision="(\w+)" data-session="([\w-]+)"/g)].map((m) => [m[1], m[2]]);
  // The four Paris pins cluster, with Longchamp (Bois de Boulogne, 16e) beside them.
  assert.deepEqual(clusters, [5]);
  assert.deepEqual(singles, [['region', 'mock-bourgogne']]);
  assert.match(html, /carte-pin__ring/);
  assert.match(visibleText(html), /La France 6 Papiers/);
  assert.match(html, /aria-label="5 Papiers ici\. Agrandir\."/);
});

test('the mock from Paris: three pins and one pair (Assemblée and Drouant are 1.4 km apart)', () => {
  const html = render(h(Carte, { pins: PINS, quartier: CARTE_MOCK_VIEW.quartier, copy: FR, onRelire: noop, onReleve: noop, initialLevel: 'paris', mapPx: 358, initialQuartier: true, drawings: { paris: '<svg/>' } }));
  const sessions = [...html.matchAll(/data-session="([\w-]+)"/g)].map((m) => m[1]).sort();
  assert.deepEqual(sessions, ['mock-aligre', 'mock-canicules', 'mock-longchamp']);
  assert.deepEqual([...html.matchAll(/class="carte-cluster" data-count="(\d+)"/g)].map((m) => m[1]), ['2']);
  // The city-precision pin wears the dotted ring and a plain ink pin (no vignette yet).
  assert.match(html, /data-precision="city" data-session="mock-canicules"[^>]*><span class="carte-pin__ring"[^>]*><\/span><span class="carte-pin__plain"/);
  // A vignette pin is the 28 px stamp, hidden from the reader (the button speaks).
  assert.match(html, /class="carte-pin__stamp" aria-hidden="true"><figure class="rv-vignette rv-vignette--pin"/);
  assert.match(html, /aria-label="Place d&#x27;Aligre et marché Beauvau, Paris 12e · Semaine 40 · Les fruits et légumes coûtent plus cher"/);
  assert.equal((html.match(/class="carte-quartier"/g) || []).length, 2);
  assert.match(html, /aria-pressed="true"/);
  // Pins are buttons: keyboard-reachable, in reading order.
  assert.equal((html.match(/<button type="button" class="carte-(pin|cluster|quartier)"/g) || []).length, 6);
});

// --- 5. the empty state ---------------------------------------------------------

test('the empty map says where the first Papier will put you', () => {
  const html = render(h(CarteEmpty, { copy: FR, onOpenPapier: noop }));
  assert.match(visibleText(html), /Ta carte est vide\. Le premier Papier te mettra quelque part\. Ouvrir le Papier/);
  assert.doesNotMatch(html, /av2-btn--primary/);
  const map = render(h(Carte, { pins: [], copy: FR, onRelire: noop, onReleve: noop, drawings: { france: '<svg/>' } }));
  assert.match(visibleText(map), /Aucun Papier/);
  assert.doesNotMatch(map, /carte-pin|carte-cluster/);
  assert.match(visibleText(render(h(CarteEmpty, { copy: carteCopy('de') }))), /Deine Karte ist leer\./);
});

// --- 6. the card --------------------------------------------------------------------

test('the card: the headline, the week and place, kept words as tokens, «toi», two actions', () => {
  const aligre = PINS.find((p) => p.sessionId === 'mock-aligre');
  const html = render(h(CartePinCard, { pin: aligre, copy: FR, onClose: noop, onRelire: noop, onReleve: noop, onWord: noop }));
  const text = visibleText(html);
  assert.match(html, /role="dialog"/);
  // The stamp prints the place under itself; the eyebrow keeps the week.
  assert.match(html, /<p class="av2-label"><span lang="fr">Semaine 40<\/span><\/p>/);
  assert.match(html, /<figcaption class="rv-vignette__place" lang="fr" aria-hidden="true">Place d&#x27;Aligre et marché Beauvau, Paris 12e<\/figcaption>/);
  assert.match(html, /<h2[^>]*class="av2-headline">Les fruits et légumes coûtent plus cher<\/h2>/);
  assert.match(html, /rv-vignette--large/);
  assert.match(html, /class="carte-card__plate"[\s\S]*?src="\/assets\/serial\/locations\/marche_canal.webp"/);
  assert.match(text, /Ta question Est-ce que les prix au marché sont plus bas toi qu’au supermarché \?/);
  assert.match(html, /<span class="carte-yours">les prix au marché sont plus bas<sup>toi<\/sup><\/span>/);
  const words = [...html.matchAll(/class="av2-chip carte-word"><span>([^<]+)<\/span>/g)].map((m) => m[1]);
  assert.deepEqual(words, ['un étal', 'le prix', 'la récolte', 'augmenter']);
  assert.equal((html.match(/<button type="button" class="av2-chip carte-word"/g) || []).length, 4);
  assert.match(html, /data-tone="primary"[^>]*><span>Relire<\/span>/);
  assert.match(html, /data-tone="secondary"[^>]*><span>Dans le Relevé<\/span>/);
  // One red press in the sheet.
  assert.equal((html.match(/av2-btn--primary/g) || []).length, 1);
  // The same question is not printed twice.
  assert.doesNotMatch(text, /La question gardée/);
});

test('the card in German keeps the French content and translates the chrome', () => {
  const canicules = PINS.find((p) => p.sessionId === 'mock-canicules');
  const text = visibleText(render(h(CartePinCard, { pin: canicules, copy: carteCopy('de'), onClose: noop, onRelire: noop, onReleve: noop })));
  assert.match(text, /Semaine 37 · Paris/);
  assert.match(text, /Die offene Frage Combien d’arbres seront plantés \?/);
  assert.match(text, /Behaltene Wörter la chaleur un arbre l’ombre/);
  assert.match(text, /Nochmal lesen Im Relevé/);
  assert.equal(render(h(CartePinCard, { pin: null, copy: FR, onClose: noop, onRelire: noop, onReleve: noop })), '');
});

test('the learner’s words are split out of the text by their spans', () => {
  assert.deepEqual(model.markSpans('abcdef', [[1, 3]]), [
    { text: 'a', yours: false }, { text: 'bc', yours: true }, { text: 'def', yours: false },
  ]);
  assert.deepEqual(model.markSpans('abc', [[0, 99]]), [{ text: 'abc', yours: true }]);
  assert.deepEqual(model.markSpans('abc', []), [{ text: 'abc', yours: false }]);
});

// --- 7. the wire ------------------------------------------------------------------------

test('the parser reads the wire and drops what it cannot place', () => {
  const view = types.parseCarteView({
    pins: [
      { session_id: 's1', dossier_id: 'd', week: '2026-W40', closed_at: null, place_label_fr: 'Paris', lat: 48.85, lon: 2.35, precision: 'weird',
        level: 'paris', headline_fr: 'Titre', kept_words: ['le prix', 3], contribution_kind: 'reader_question', contribution_fr: 'Q ?',
        contribution_spans: [[0, 1], [5, 2], 'x'], question_fr: '', plate_url: '/p.webp',
        vignette: { ring: 'question', kept_contribution: true, pictogram_svg: '<svg/>' } },
      { session_id: 's2', lat: 'north', lon: 2 },
      { session_id: 's3', lat: 47, lon: 4.8, vignette: { ring: 'gold' } },
    ],
    quartier: [{ id: 'le_mistral', name_fr: 'Le Mistral', label_fr: '', lat: 48.87, lon: 2.36, plate_url: null }, { id: 'x' }],
    counts: { france: 2, idf: 1, paris: 1, unplaced: 4 },
  });
  assert.equal(view.pins.length, 2);
  const [first, second] = view.pins;
  assert.equal(first.precision, 'city');
  assert.deepEqual(first.keptWords, ['le prix', '3']);
  assert.deepEqual(first.contributionSpans, [[0, 1]]);
  assert.equal(first.questionFr, null);
  assert.deepEqual(first.vignette, { ring: 'question', keptContribution: true, pictogramSvg: '<svg/>' });
  assert.equal(second.vignette, null);
  assert.deepEqual(view.quartier, [{ id: 'le_mistral', nameFr: 'Le Mistral', labelFr: 'Le Mistral', lat: 48.87, lon: 2.36, plateUrl: null }]);
  assert.equal(view.counts.unplaced, 4);
});

test('the client: a 404 means the Revue is off; anything else is an error', async () => {
  const ok = createCarteClient({ get: async (url) => (assert.equal(url, '/revue/carte'), { pins: [], quartier: [], counts: {} }) });
  assert.deepEqual(await ok.carte(), { enabled: true, view: { pins: [], quartier: [], counts: { france: 0, idf: 0, paris: 0, unplaced: 0 } } });
  const off = createCarteClient({ get: async () => { throw { response: { status: 404 } }; } });
  assert.deepEqual(await off.carte(), { enabled: false });
  const down = createCarteClient({ get: async () => { throw { response: { status: 500 } }; } });
  await assert.rejects(() => down.carte(), (error) => error instanceof types.CarteError && error.status === 500);
});
