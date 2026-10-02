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
const { RIG_MOODS, VISEMES, OUTFITS } = require('./rig-kit.ts');

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

/* WP-119 §8.2 · `outfit`, the first new field of the stage language. */

const HEX = /#[0-9a-f]{6}/gi;
const hexes = (text) => new Set((text.match(HEX) || []).map((c) => c.toLowerCase()));

test('Toi in no outfit is Toi in the coat, the canon drawing', () => {
  for (const crop of ['full', 'bust', 'head']) {
    assert.equal(render({ id: 'user', crop, outfit: 'coat' }), render({ id: 'user', crop }), crop);
  }
  const coat = render({ id: 'user', crop: 'full' });
  assert.match(coat, /fill="#5b5346"/, 'the heavy coat');
  assert.match(coat, /fill="#9c2411"/, 'the red scarf');
  assert.equal(render({ id: 'user', outfit: 'tuxedo' }), render({ id: 'user' }), 'an unknown outfit is the coat');
});

test('Toi draws all eight outfits; only the torso changes', () => {
  assert.deepEqual([...OUTFITS], ['coat', 'suit', 'apron', 'raincoat', 'sport', 'scarf_only', 'chef', 'hi_vis']);
  assert.deepEqual([...rigFor('user').outfits], [...OUTFITS], 'Toi declares every outfit');
  const coat = render({ id: 'user', crop: 'full' });
  const unchanged = [
    '<path d="M86,366 L86,392 M114,366 L114,392" fill="none" stroke="#14285f"', // legs
    '<circle cx="46" cy="303" r="8" fill="#2a231c">', // hands
    '<circle cx="154" cy="303" r="8" fill="#2a231c">',
    'fill="#8a5a32"', // the bag
    '<g transform="translate(100 150)">', // the head anchor
    '<path d="M-38,10 C-40,-34 -20,-48 0,-48 C20,-48 40,-34 38,10 Z" fill="#1d3a8a">', // the tuque
    '<circle cx="0" cy="-52" r="11" fill="#f8f3e8">', // its pompom
  ];
  const seen = new Set();
  for (const outfit of OUTFITS) {
    for (const crop of ['full', 'bust', 'head']) {
      const html = render({ id: 'user', crop, outfit });
      assert.match(html, new RegExp(`viewBox="${rigFor('user').crops[crop].join(' ')}"`), `${outfit} ${crop}: same crop`);
    }
    const html = render({ id: 'user', crop: 'full', outfit });
    for (const piece of unchanged) assert.ok(html.includes(piece), `${outfit} keeps ${piece}`);
    assert.doesNotMatch(html, /#ffffff/, `${outfit}: still no face`);
    if (outfit !== 'coat') assert.notEqual(html, coat, `${outfit} differs from the coat`);
    seen.add(html);
  }
  assert.equal(seen.size, OUTFITS.length, 'eight different torsos');
  const scarf = 'fill="#9c2411"></path>';
  for (const outfit of ['suit', 'apron', 'sport']) {
    const neck = render({ id: 'user', crop: 'full', outfit }).split('<g transform=')[1];
    assert.ok(!neck.includes('M-28,20 Q0,34 28,20'), `${outfit} drops the scarf`);
  }
  assert.ok(render({ id: 'user', outfit: 'scarf_only' }).includes(scarf), 'scarf_only keeps the scarf');
});

test('the outfits add no colour the cast does not already use (owner rule)', () => {
  const dir = path.join(__dirname, 'rigs');
  const palette = new Set();
  for (const file of fs.readdirSync(dir)) {
    if (file === 'toi.tsx') continue;
    for (const colour of hexes(fs.readFileSync(path.join(dir, file), 'utf8'))) palette.add(colour);
  }
  for (const colour of hexes(render({ id: 'user', crop: 'full' }))) palette.add(colour);
  for (const outfit of OUTFITS) {
    for (const colour of hexes(render({ id: 'user', crop: 'full', outfit }))) {
      assert.ok(palette.has(colour), `${outfit} uses ${colour}, which no rig used before`);
    }
  }
});

test('a rig that does not list an outfit ignores it', () => {
  for (const rig of RIGS) {
    if (rig.id === 'user') continue;
    assert.equal(rig.outfits, undefined, `${rig.id} declares no outfit in v1`);
    for (const crop of ['full', 'bust']) {
      assert.equal(render({ id: rig.id, crop, outfit: 'suit' }), render({ id: rig.id, crop }), `${rig.id} ${crop}`);
    }
  }
});

test('PanelStage drops `outfit` unless surface === "revue" (the coat stays canon in the story)', () => {
  const { PanelStage, toiOutfit } = require('./PanelStage.tsx');
  const members = [{ id: 'romy_tremblay', speaking: true }, { id: 'user', outfit: 'suit' }];
  const stage = (props) => renderToStaticMarkup(React.createElement(PanelStage, { members, you: true, ...props }));
  const toiFigure = (html) => html.match(/cast-stage__figure--you"[^>]*>/)[0];

  const story = stage({});
  assert.match(toiFigure(story), /data-outfit="coat"/, 'default surface is the story');
  assert.match(toiFigure(stage({ surface: 'story' })), /data-outfit="coat"/);
  assert.equal(stage({ surface: 'story' }), stage({ members: [{ id: 'romy_tremblay', speaking: true }] }), 'the story ignores the outfit entirely');

  const revue = stage({ surface: 'revue' });
  assert.match(toiFigure(revue), /data-outfit="suit"/);
  assert.notEqual(revue.split('cast-stage__figure--you')[1], story.split('cast-stage__figure--you')[1], 'the suit is drawn');
  assert.match(revue, /data-cast-stage="romy_tremblay"/, 'Toi is never one of the speakers');

  assert.equal(toiOutfit(members), 'coat');
  assert.equal(toiOutfit(members, 'revue'), 'suit');
  assert.equal(toiOutfit([{ id: 'romy_tremblay', outfit: 'chef' }], 'revue'), 'coat', 'only Toi\'s own outfit counts');
});
