/* WP-168 · a written season's new faces: drawn from parameters, on the plate like the cast.
 *   node --test components/cast/generated-rig.test.js
 */
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');

require('../../node_modules/sucrase/register/ts');
require('../../node_modules/sucrase/register/tsx');

const ROOT = path.resolve(__dirname, '../..');
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) return originalResolve.call(this, path.join(ROOT, request.slice(2)), ...rest);
  return originalResolve.call(this, request, ...rest);
};

const React = require(path.join(ROOT, 'node_modules/react'));
const { renderToStaticMarkup } = require(path.join(ROOT, 'node_modules/react-dom/server'));
global.React = React;

const { CastRig } = require('./CastRig.tsx');
const { PanelStage, stageMembers } = require('./PanelStage.tsx');
const { drawnFaceId } = require('./CastFace.tsx');
const { RIGS, rigFor, registerGeneratedRigs, generatedRigId } = require('./cast-registry.ts');
const { RIG_MOODS } = require('./rig-kit.ts');
const { RIG_VOCABULARY, RIG_DEFAULTS, COLOURS, SKIN, HAIR, normaliseRigParams } = require('./rig-params.ts');
const { generatedRig } = require('./rigs/generated.tsx');

const render = (props) => renderToStaticMarkup(React.createElement(CastRig, props));

const AWA = {
  id: 'awa_ndiaye',
  name: 'Awa Ndiaye',
  rig: {
    build: 'slim', height: 'tall', head: 'long', skin: 'deeper', hair: 'braids', hair_colour: 'black',
    facial_hair: 'none', glasses: 'round', top: 'boubou', top_colour: 'ochre', bottom_colour: 'ink',
    accessory: 'headwrap', accessory_colour: 'green', idle: 'sway',
  },
};
const MARIUS = {
  id: 'marius_castellan',
  name: 'Marius Castellan',
  rig: {
    build: 'broad', height: 'short', head: 'square', skin: 'tan', hair: 'cropped', hair_colour: 'grey',
    facial_hair: 'beard', glasses: 'none', top: 'uniform', top_colour: 'navy', bottom_colour: 'navy',
    accessory: 'cap', accessory_colour: 'cream', idle: 'nod',
  },
};

test('a new face registers, draws every mood in every crop, and is named', () => {
  assert.deepEqual(registerGeneratedRigs([AWA, MARIUS]), ['awa_ndiaye', 'marius_castellan']);
  for (const id of ['awa_ndiaye', 'marius_castellan']) {
    const rig = rigFor(id);
    assert.ok(rig, id);
    for (const mood of RIG_MOODS) {
      for (const crop of ['full', 'bust', 'head']) {
        const html = render({ id, mood, crop, size: 100 });
        assert.match(html, /^<svg /, `${id} ${mood} ${crop}`);
        assert.match(html, new RegExp(`data-cast="${id}"`));
        assert.match(html, /role="img"/);
        assert.match(html, /class="cast-rig__idle"/);
      }
    }
  }
  assert.match(render({ id: 'awa_ndiaye' }), /aria-label="Awa Ndiaye"/);
  assert.notEqual(render({ id: 'awa_ndiaye', crop: 'full' }), render({ id: 'marius_castellan', crop: 'full' }));
  // The face is the cast's face machinery: a mood and a blink change it.
  assert.notEqual(render({ id: 'awa_ndiaye', mood: 'ravie', crop: 'head' }), render({ id: 'awa_ndiaye', mood: 'neutre', crop: 'head' }));
  assert.notEqual(render({ id: 'awa_ndiaye', blink: true, crop: 'head' }), render({ id: 'awa_ndiaye', blink: false, crop: 'head' }));
  // The fixed cast is untouched: the generated faces are not among the hand-drawn rigs.
  assert.equal(RIGS.length, 9);
});

test('every parameter value draws, and anything outside the vocabulary is the default', () => {
  for (const [key, values] of Object.entries(RIG_VOCABULARY)) {
    for (const value of values) {
      const rig = generatedRig(`probe_${key}`, 'Probe', { [key]: value });
      const html = renderToStaticMarkup(React.createElement(rig.Art, { v: require('./rig-kit.ts').rigValues(rig, { mood: 'neutre', mouth: 'auto', blink: false }) }));
      assert.match(html, /^<g>/, `${key}=${value}`);
      assert.doesNotMatch(html, /NaN|undefined/, `${key}=${value}`);
    }
  }
  assert.deepEqual(normaliseRigParams({ skin: 'purple', hair: 'Afro', top_colour: 'RED', glasses: 42 }), {
    ...RIG_DEFAULTS, hair: 'afro', top_colour: 'red',
  });
  assert.deepEqual(normaliseRigParams(null), RIG_DEFAULTS);
  // A broken spec still draws (the defaults), and a garbage row is skipped, never thrown.
  assert.deepEqual(registerGeneratedRigs([{ id: 'zoe_martin', name: 'Zoé', rig: 'nonsense' }, { id: '' }, null, 7]), ['zoe_martin']);
  assert.match(render({ id: 'zoe_martin' }), /data-cast="zoe_martin"/);
  assert.deepEqual(registerGeneratedRigs(undefined), []);
});

test('the pure table of fixed ids is the registry\'s own', () => {
  const { FIXED_RIG_IDS } = require('./generated-cast.ts');
  assert.deepEqual([...FIXED_RIG_IDS].sort(), RIGS.map((rig) => rig.id).sort());
});

test("a new face never takes the fixed cast's id or name", () => {
  assert.deepEqual(registerGeneratedRigs([{ id: 'margaux_barman', name: 'Margaux', rig: AWA.rig }, { id: 'gus', name: 'Gus', rig: {} }]), []);
  assert.equal(rigFor('margaux_barman').name, 'Margaux');
  assert.equal(drawnFaceId('Margaux'), 'margaux_barman');
});

test('the stage finds a new face by its id or its name and stands it on the plate', () => {
  registerGeneratedRigs([AWA, MARIUS]);
  assert.equal(generatedRigId('awa_ndiaye'), 'awa_ndiaye');
  assert.equal(generatedRigId('Awa Ndiaye'), 'awa_ndiaye');
  assert.equal(generatedRigId('Marius'), 'marius_castellan');
  assert.equal(drawnFaceId('awa_ndiaye', 'Awa'), 'awa_ndiaye');
  assert.equal(drawnFaceId('stranger_nobody'), null, 'an unknown speaker keeps the initial');
  const members = [
    { id: 'awa_ndiaye', speaking: true },
    { id: 'romy_tremblay' },
    { id: 'marius_castellan', mood: 'cold' },
  ];
  assert.deepEqual(stageMembers(members).map((m) => m.rigId), ['awa_ndiaye', 'romy_tremblay', 'marius_castellan']);
  const html = renderToStaticMarkup(
    React.createElement(PanelStage, { members, you: true, light: false, aspect: 4 / 3, plateUrl: null }),
  );
  assert.match(html, /data-cast-stage="awa_ndiaye romy_tremblay marius_castellan"/);
  assert.match(html, /data-cast="awa_ndiaye"/);
  assert.match(html, /data-cast="marius_castellan"/);
  assert.match(html, /data-head="/);
});

test("every colour a new face can wear is one the drawn cast already wears", () => {
  const dir = path.join(__dirname, 'rigs');
  const worn = new Set();
  for (const file of fs.readdirSync(dir)) {
    if (file === 'generated.tsx') continue;
    for (const hex of fs.readFileSync(path.join(dir, file), 'utf8').match(/#[0-9a-f]{6}/gi) || []) worn.add(hex.toLowerCase());
  }
  for (const table of [COLOURS, SKIN, HAIR]) {
    for (const [name, hex] of Object.entries(table)) assert.ok(worn.has(hex.toLowerCase()), `${name} ${hex} is not a cast colour`);
  }
});
