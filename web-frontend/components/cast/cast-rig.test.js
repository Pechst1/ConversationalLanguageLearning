/* WP-116 · the drawn cast renders, maps moods, and never moves in a way CSS cannot stop.
 *   node --test components/cast/cast-rig.test.js
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
const { RIGS, rigFor, rigMoodFor } = require('./cast-registry.ts');
const { RIG_MOODS, VISEMES } = require('./rig-kit.ts');

const render = (props) => renderToStaticMarkup(React.createElement(CastRig, props));

test('the whole season-1 cast has a rig, Toi included', () => {
  const ids = RIGS.map((rig) => rig.id).sort();
  assert.deepEqual(ids, [
    'augustin_de_roncourt', 'camille_marchand', 'landlord_marchand', 'lila_bonnet', 'margaux_barman',
    'marin_leveque', 'odile_ferrand', 'romy_tremblay', 'user',
  ]);
  assert.equal(rigFor('Gus').id, 'augustin_de_roncourt');
  assert.equal(rigFor('toi').id, 'user');
  assert.equal(rigFor('bastien_roux'), null);
});

test('every rig renders every mood in every crop as a labelled image', () => {
  for (const rig of RIGS) {
    for (const mood of RIG_MOODS) {
      for (const crop of ['full', 'bust', 'head']) {
        const html = render({ id: rig.id, mood, crop, size: 100 });
        assert.match(html, /^<svg /, `${rig.id} ${mood} ${crop}`);
        assert.match(html, new RegExp(`data-cast="${rig.id}"`));
        assert.match(html, /role="img"/);
        assert.match(html, new RegExp(`aria-label="${rig.name.replace('.', '\\.')}"`));
        assert.match(html, /class="cast-rig__idle"/);
      }
    }
  }
});

test('a mood and a viseme change the face', () => {
  const face = (props) => render({ id: 'margaux_barman', crop: 'head', ...props });
  const neutral = face({ mood: 'neutre' });
  assert.notEqual(face({ mood: 'ravie' }), neutral);
  assert.notEqual(face({ mood: 'emue' }), neutral);
  const mouths = new Set(VISEMES.map((mouth) => face({ mood: 'neutre', mouth })));
  assert.equal(mouths.size, VISEMES.length, 'six distinct mouth shapes');
  assert.notEqual(face({ blink: true }), face({ blink: false }));
});

test('Toi has no face, ever', () => {
  for (const mood of RIG_MOODS) {
    const html = render({ id: 'user', mood, crop: 'full' });
    assert.doesNotMatch(html, /#ffffff/, 'no eye whites drawn for Toi');
  }
});

test('Camille draws the variant the learner chose, Margaux what she holds', () => {
  const f = render({ id: 'camille', variant: 'f', crop: 'head' });
  const m = render({ id: 'camille', variant: 'm', crop: 'head' });
  assert.notEqual(f, m);
  assert.notEqual(render({ id: 'margaux', hold: 'cle' }), render({ id: 'margaux', hold: 'verre' }));
});

test('the app moods map onto the rig moods', () => {
  assert.equal(rigMoodFor('neutral'), 'neutre');
  assert.equal(rigMoodFor('happy'), 'ravie');
  assert.equal(rigMoodFor('cross'), 'fachee');
  assert.equal(rigMoodFor('moved'), 'emue');
  assert.equal(rigMoodFor('surprised'), 'surprise');
  assert.equal(rigMoodFor(undefined), 'neutre');
  assert.equal(rigMoodFor('nonsense'), 'neutre');
});

test('no SMIL anywhere: every loop is CSS that reduced motion and `still` stop', () => {
  const dir = path.join(__dirname, 'rigs');
  for (const file of fs.readdirSync(dir)) {
    const source = fs.readFileSync(path.join(dir, file), 'utf8');
    assert.doesNotMatch(source, /<animate/i, file);
  }
  const css = fs.readFileSync(path.join(ROOT, 'styles/cast-rig.css'), 'utf8');
  assert.match(css, /@media \(prefers-reduced-motion: reduce\)[\s\S]*cast-rig__idle[\s\S]*animation: none/);
  assert.match(css, /\.cast-rig--still \.cast-rig__idle/);
  assert.match(render({ id: 'lila', still: true }), /cast-rig--still/);
  assert.match(fs.readFileSync(path.join(ROOT, 'pages/_app.tsx'), 'utf8'), /styles\/cast-rig\.css/);
});

test('the art set defaults to painted until the owner says otherwise', () => {
  const { defaultArtSet, artSet, ART_SET_STORAGE_KEY } = require('../../lib/art-set.ts');
  assert.equal(defaultArtSet(), 'painted');
  assert.equal(artSet(), 'painted');
  assert.equal(ART_SET_STORAGE_KEY, 'atelier.artSet');
});

test('every face has a PNG snapshot for pushes (scripts/render-rigs.mjs)', () => {
  for (const rig of RIGS) {
    if (rig.faceless) continue;
    for (const mood of RIG_MOODS) {
      const file = path.join(ROOT, 'public/assets/serial/drawn', rig.id, `portrait-${mood}.png`);
      assert.ok(fs.existsSync(file), `${rig.id} ${mood}: run node scripts/render-rigs.mjs`);
    }
  }
});
