// node --test lib/quartier/carnet.test.js
//
// P12 stage 5 · «Ton carnet» reads the story (`carnet-model.ts`). Observed 17 Nov (Jonas, A1,
// seven days played as pages): «LES GENS — Personne encore. Entre au Mistral.», the places of Le
// Papier as his places, and a day labelled «Épisode 1». Now the people come from the
// trombinoscope, the places from the played days, the choices from the end card's own lines under
// the day's edition, and Le Papier's places only while the news is on.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
const resolve = Module._resolveFilename;
Module._resolveFilename = function alias(request, ...rest) {
  if (typeof request === 'string' && request.startsWith('@/')) return resolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  return resolve.call(this, request, ...rest);
};

const { Memory, editionKey } = require('./memory.ts');
const { carnetOf, dayLabel } = require('./carnet-model.ts');

const w = (fr) => ({ fr, en: fr, de: fr });

/** The trombinoscope's payload (`GET /serial/threads/current/cast`): only the people met. */
const CAST = [
  { id: 'lila_bonnet', name: 'Lila', register: 'tu', tu_since: { date: '2026-11-12', scene_id: 's2' }, known_about_you: [{ text_fr: 'Tu es venu pour l’appartement d’Odile.', date: '2026-11-11', scene_id: 's1' }, { text_fr: 'Tu as gardé la photo.', date: '2026-11-17', scene_id: 's8' }] },
  { id: 'margaux_barman', name: 'Margaux', relationship: { register: 'tu', known_about_you: [{ text_fr: 'Tu as laissé la clé derrière la caisse.', date: '2026-11-11', scene_id: 's1' }] } },
  { id: 'augustin_de_roncourt', name: 'Gus', register: 'vous', known_about_you: [] },
];

/** The archive's days (`GET /story-engine/archive`), each with its place. */
const DAYS = [
  { date: '2026-11-11', edition_no: 1, title_fr: 'Le mauvais accueil', location_id: 'le_mistral', location_name: 'Le Mistral' },
  { date: '2026-11-12', edition_no: 2, title_fr: 'La clé', location_id: 'le_mistral', location_name: 'Le Mistral' },
  { date: '2026-11-17', edition_no: 8, title_fr: 'Là-haut', location_id: 'stairwell', location_name: 'L’escalier' },
];

function day8Memory() {
  const m = new Memory(false);
  // the quarter played day 8 («Là-haut», the season's page t1.b) and kept its edition
  m.apply('t1b', { kind: 'fact', key: editionKey('t1b'), value: 8 });
  m.apply('t1b', { kind: 'journal', words: w('Tu as dit que tu ne savais pas.') });
  // a day the quarter played before it kept editions: no number at all, never «Épisode 1»
  m.apply('t1a', { kind: 'journal', words: w('Tu as dit non merci.') });
  return m;
}

test('three people met in the story and two played places are listed, with what each one knows', () => {
  const model = carnetOf(day8Memory(), { cast: CAST, days: DAYS, news: false });
  assert.deepEqual(model.people.map((p) => p.name), ['Lila', 'Margaux', 'Gus']);
  assert.deepEqual(model.people.map((p) => p.register), ['tu', 'tu', 'vous']);
  assert.equal(model.people[0].knows, 'Tu as gardé la photo.', 'the newest thing Lila knows');
  assert.equal(model.people[1].knows, 'Tu as laissé la clé derrière la caisse.');
  assert.equal(model.people[2].knows, null);

  const names = model.places.map((p) => p.name.fr);
  assert.deepEqual(names, ["L'escalier du Mistral", 'Le quai de Valmy']);
  assert.deepEqual(model.places.find((p) => p.id === 'quai_de_valmy').editions, ['Nº 2', 'Nº 1']);
  assert.deepEqual(model.places.find((p) => p.id === 'escalier_mistral').editions, ['Nº 8']);
  assert.ok(model.places.every((p) => p.tag === 'known'));
});

test('on day 8 the choices stand under «Nº 8», and no day is «Épisode 1»', () => {
  const model = carnetOf(day8Memory(), { cast: CAST, days: DAYS, news: false });
  // newest first, as the end card wrote them
  assert.deepEqual(
    model.did.map((d) => [d.words.fr, d.label]),
    [
      ['Tu as dit non merci.', null],
      ['Tu as dit que tu ne savais pas.', 'Nº 8'],
    ],
  );
  assert.ok(!JSON.stringify(model).includes('Épisode'));
  assert.equal(dayLabel('t1a', {}), null);
  assert.equal(dayLabel('roam', {}), 'En te promenant');
  const carnet = fs.readFileSync(path.join(WEB_ROOT, 'components/quartier/Carnet.tsx'), 'utf8');
  assert.doesNotMatch(carnet, /Épisode 1/, 'the carnet names no episode by the season page');
});

test('Le Papier’s places stand in their own section, only while the news is on', () => {
  const off = carnetOf(new Memory(false), { cast: CAST, days: DAYS, news: false });
  assert.equal(off.news, null);
  assert.ok(!off.places.some((p) => p.id === 'marche_aligre' || p.id === 'hippodrome_longchamp'), 'never among the learner’s places');
  const on = carnetOf(new Memory(false), { cast: CAST, days: DAYS, news: true });
  assert.deepEqual(on.news.map((p) => p.id).sort(), ['hippodrome_longchamp', 'marche_aligre']);
  assert.ok(!on.places.some((p) => p.id === 'marche_aligre'));
});

test('an empty section says what will fill it, in three languages', () => {
  const model = carnetOf(new Memory(false), null);
  assert.deepEqual([model.people.length, model.did.length, model.places.length], [0, 0, 0]);
  assert.equal(model.news, null);
  for (const key of ['people', 'did', 'places', 'news']) {
    for (const lang of ['fr', 'en', 'de']) assert.ok(model.empty[key][lang].length > 10, `${key}.${lang}`);
  }
  assert.doesNotMatch(model.empty.people.fr, /Entre au Mistral/);
});

test('someone met only in the quarter is still listed, with how they see you', () => {
  const m = new Memory(false);
  m.apply('roam', [{ kind: 'meet', who: 'camille_marchand' }, { kind: 'regard', who: 'camille_marchand', delta: 1 }]);
  const model = carnetOf(m, { cast: CAST, days: [], news: false });
  const camille = model.people.find((p) => p.who === 'camille_marchand');
  assert.ok(camille && camille.regard && camille.regard.fr.includes('Camille'));
  assert.equal(model.people.length, 4);
});

test('an engine day keeps its edition in the quarter’s memory as it begins', () => {
  const stage = fs.readFileSync(path.join(WEB_ROOT, 'lib/quartier/stage.ts'), 'utf8');
  assert.match(stage, /private beginDay\(\)[\s\S]{0,400}editionKey\(this\.day\)/);
  assert.doesNotMatch(stage, /this\.memory\.beginDay\(this\.day\);\n\s*this\.routes/, 'every start goes through beginDay()');
});
