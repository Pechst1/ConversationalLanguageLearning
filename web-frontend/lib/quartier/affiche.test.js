// node --test lib/quartier/affiche.test.js
//
// Le Quartier · today's Papier on the Morris column (`REVUE_QUARTIER_AFFICHE_ENABLED`).
//
//   1. the poster's model: the date in French, the headline set in balanced lines (a short word
//      never ends a line, a long headline ends on «…»), no edition → no poster, done → «lu»;
//   2. the route a tap opens: a spot that opens one, while you are free to walk; the nearest such
//      object within reach shows its card;
//   3. the wiring: the engine hangs the poster with its spot, the stage leaves the tap to the
//      screen, the screen follows the route, the page reads today's edition and navigates.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (typeof request === 'string' && request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

const model = { ...require('./affiche-model.ts'), ...require('./affiche-today.ts') };

const offer = (extra = {}) => ({
  week: { iso: '2026-W47', label: 'Semaine 47', range: '' },
  recommended: { dossierId: 'd1' },
  recommendedReason: 'first',
  alternatives: [],
  evergreenOnly: false,
  resume: null,
  filed: null,
  affiche: { dossierId: 'd1', headlineFr: 'Le Goncourt retire un roman de sa première sélection', done: false },
  ...extra,
});
const SUNDAY = new Date(2026, 10, 22, 20, 0);

// --- 1. the model ---------------------------------------------------------------

test('the date is said in French, as a dateline', () => {
  assert.equal(model.frenchDate(SUNDAY), 'dimanche 22 novembre');
  assert.equal(model.frenchDate(new Date(2026, 9, 1)), 'jeudi 1er octobre');
});

test('the headline is set in balanced lines, short words kept with the next', () => {
  const lines = model.wrapHeadline('Le Goncourt retire un roman de sa première sélection');
  assert.ok(lines.length >= 3 && lines.length <= model.HEADLINE_MAX_LINES, lines.join(' / '));
  assert.equal(lines.join(' '), 'Le Goncourt retire un roman de sa première sélection');
  for (const line of lines) {
    assert.ok(line.length <= Math.max(model.HEADLINE_LINE_CHARS, 'sélection'.length), line);
    // a line never ends on «le», «un», «de», «sa», «à»
    assert.doesNotMatch(line, /\s(le|la|un|de|sa|à|l’)$/i, line);
  }
  // balanced: no line is a lone short word while another is full
  const lengths = lines.map((l) => l.length);
  assert.ok(Math.max(...lengths) - Math.min(...lengths) <= 7, lengths.join(','));
  assert.equal(model.wrapHeadline('La ligne 14 à Orly').length, 2);
  // a lone mark stays with its word
  for (const line of model.wrapHeadline('Arc de Triomphe : seize chevaux, deux minutes, un vainqueur')) assert.doesNotMatch(line, /^[:;?!]/);
  assert.deepEqual(model.wrapHeadline('Matisse'), ['Matisse']);
  assert.deepEqual(model.wrapHeadline('   '), []);
});

test('a word longer than the measure stands alone, and a long headline ends on «…»', () => {
  assert.deepEqual(model.wrapHeadline('Anticonstitutionnellement voté'), ['Anticonstitutionnellement', 'voté']);
  const long = model.wrapHeadline(
    'Le budget de la ville est voté après une nuit de débats et trois amendements sur les écoles, les crèches et les parcs du quartier',
  );
  assert.equal(long.length, model.HEADLINE_MAX_LINES);
  assert.match(long[long.length - 1], /…$/);
});

test('no edition today, no poster: the column keeps its own', () => {
  assert.equal(model.afficheOf(null, SUNDAY), null);
  assert.equal(model.afficheOf(offer({ affiche: null }), SUNDAY), null);
  assert.equal(model.afficheOf(offer({ affiche: undefined }), SUNDAY), null);
  assert.equal(model.afficheOf(offer({ affiche: { dossierId: 'd1', headlineFr: '  ', done: false } }), SUNDAY), null);
});

test('today’s edition: masthead date, headline lines, the Papier’s route; done is the «lu»', () => {
  const poster = model.afficheOf(offer(), SUNDAY);
  assert.equal(poster.date, 'dimanche 22 novembre');
  assert.equal(poster.lines.join(' '), 'Le Goncourt retire un roman de sa première sélection');
  assert.equal(poster.done, false);
  assert.equal(poster.route, '/revue');
  const resumed = model.afficheOf(offer({ resume: { sessionId: 's 9' } }), SUNDAY);
  assert.equal(resumed.route, '/revue?session=s%209');
  const read = model.afficheOf(offer({ affiche: { dossierId: 'd1', headlineFr: 'La Nuit blanche', done: true } }), SUNDAY);
  assert.equal(read.done, true);
  assert.equal(model.afficheOpens(read).label.fr, 'Le Papier du jour · lu');
  assert.equal(model.afficheOpens(poster).label.fr, 'Le Papier du jour');
  // Integration 2026-11-22: the name stays French and unarticled in every language.
  assert.deepEqual(model.afficheOpens(poster).label, { fr: 'Le Papier du jour', de: 'Le Papier von heute', en: 'Le Papier, today' });
  assert.deepEqual(model.afficheOpens(read).label, {
    fr: 'Le Papier du jour · lu',
    de: 'Le Papier von heute · gelesen',
    en: 'Le Papier, today · read',
  });
  assert.equal(model.afficheOpens(poster).route, '/revue');
  for (const lang of ['fr', 'en', 'de']) assert.ok(model.afficheOpens(poster).label[lang]);
});

// --- 2. the pick → the route ------------------------------------------------------

test('a tap on an object that opens a route opens it, only while you are free to walk', () => {
  const hit = { kind: 'spot', id: model.AFFICHE_SPOT, opens: '/revue' };
  assert.equal(model.routeOfHit(hit, true), '/revue');
  assert.equal(model.routeOfHit(hit, false), null, 'not in the middle of a scene, a talk or a card');
  assert.equal(model.routeOfHit({ kind: 'spot', id: 'switch:a' }, true), null, 'a spot that opens nothing');
  assert.equal(model.routeOfHit({ kind: 'person', key: 'margaux' }, true), null);
  assert.equal(model.routeOfHit({ kind: 'ground', point: {} }, true), null);
  assert.equal(model.routeOfHit(null, true), null);
});

test('the card shows for the nearest object that opens a route within reach', () => {
  const opens = { route: '/revue', label: { fr: 'Le Papier du jour', en: 'x', de: 'y' } };
  const spots = [
    { id: 'a', pos: { x: 0, z: 0 }, enabled: true, opens },
    { id: 'b', pos: { x: 2, z: 0 }, enabled: true, opens },
    { id: 'c', pos: { x: 1, z: 0 }, enabled: true },
    { id: 'd', pos: { x: 1.5, z: 0 }, enabled: false, opens },
  ];
  assert.equal(model.openingNear(spots, { x: 1.6, z: 0 }, 4.5).id, 'b');
  assert.equal(model.openingNear(spots, { x: 0.2, z: 0 }, 4.5).id, 'a');
  assert.equal(model.openingNear(spots, { x: 20, z: 0 }, 4.5), null);
});

// --- 3. the wiring --------------------------------------------------------------

test('the engine hangs the poster with its spot; the stage leaves the tap to the screen; the page opens it', () => {
  const read = (file) => fs.readFileSync(path.join(WEB_ROOT, file), 'utf8');
  // the street never loads the Revue's client: only the page reads the offer
  for (const file of ['lib/quartier/affiche-model.ts', 'lib/quartier/affiche-art.ts', 'lib/quartier/quai.ts', 'lib/quartier/engine.ts']) {
    assert.doesNotMatch(read(file), /@\/lib\/revue/, file);
  }
  const engine = read('lib/quartier/engine.ts');
  assert.match(engine, /buildQuai\(B, this\.opts\.affiche \?\? null\)/);
  assert.match(engine, /id: AFFICHE_SPOT[^\n]*opens: afficheOpens\(this\.opts\.affiche\)/);
  assert.match(engine, /opens: s\.opens\.route/);
  const quai = read('lib/quartier/quai.ts');
  assert.match(quai, /affiche\s*\?\s*\{ key: 'poster:papier', draw: afficheArt\(affiche\)/);
  assert.match(quai, /: \{ key: 'poster:brocante'/, 'no edition: the column’s own poster');
  assert.match(read('lib/quartier/stage.ts'), /if \(hit\.kind === 'spot' && hit\.opens\) return;/);
  const screen = read('components/quartier/QuartierScreen.tsx');
  assert.match(screen, /const route = routeOfHit\(hit, free\.current\);\s*if \(route\) openRef\.current\?\.\(route\);/);
  assert.match(screen, /onClick=\{\(\) => onOpen\(opening\.route\)\}/);
  const page = read('pages/quartier.tsx');
  assert.match(page, /afficheOf\(week\.offer, new Date\(\)\)/);
  assert.match(page, /affiche=\{afficheToday\} onOpen=\{open\}/);
});
