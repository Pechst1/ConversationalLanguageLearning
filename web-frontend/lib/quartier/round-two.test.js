// node --test lib/quartier/round-two.test.js
//
// P12 round 2 · Le Quartier as two learners met it on 17 Nov (walk-integration-a1/b1, day 3):
// the map's grey markers touched (`a1-d3-q-map.png`), the camera sat in the café's panelling
// (`a1-d3-q-walk2.png`), and ten taps on Lila and Gus opened no talk while the hint said
// «touche quelqu’un pour parler» (`a1-d3-q-talk.png`).

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));
const resolve = Module._resolveFilename;
Module._resolveFilename = function alias(request, ...rest) {
  if (typeof request === 'string' && request.startsWith('@/')) return resolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  return resolve.call(this, request, ...rest);
};

const { projectPoint } = require('@/components/carte/carte-projection');
const { mapPlaces } = require('./world.ts');
const { PIN, pinReach } = require('./map-labels.ts');
const { WHOLE_BOX, pinsIn, quarterBox } = require('@/components/quartier/QuartierMap.tsx');

const placed = () =>
  mapPlaces()
    .map((p) => ({ p, xy: projectPoint('paris', p.lat, p.lon) }))
    .filter((x) => x.xy);

/** Pairs of pins whose drawn marks (dot and stroke, the ring of the pin you are at) touch, with paper between. */
function touching(pins, u, here) {
  const out = [];
  pins.forEach((a, i) =>
    pins.slice(i + 1).forEach((b) => {
      const need = (pinReach(a.p.id === here) + pinReach(b.p.id === here) + PIN.apart) * u;
      const d = Math.hypot(a.xy[0] - b.xy[0], a.xy[1] - b.xy[1]);
      if (d < need - 1e-6) out.push(`${a.p.id} × ${b.p.id} (${(d / u).toFixed(2)}u < ${(need / u).toFixed(2)}u)`);
    }),
  );
  return out;
}

for (const [zoom, boxOf] of [
  ['Ton quartier (the default)', (list) => quarterBox(list.map((x) => x.xy))],
  ['Tout Paris', () => WHOLE_BOX],
]) {
  test(`La carte, ${zoom}: no marker touches another`, () => {
    const raw = placed();
    const box = boxOf(raw);
    const u = box[2] / 100;
    const here = 'quai_de_valmy';
    // what the map drew: each pin at its place, the gare, the mairie and the quai within a few units
    if (zoom.startsWith('Ton')) assert.ok(touching(raw, u, here).length > 0, 'the observed fault: markers touched');
    const drawn = pinsIn(raw, box, here);
    assert.deepEqual(touching(drawn, u, here), []);
    // the pin you are at stays at its place; the others move no further than they must
    const at = (list, id) => list.find((x) => x.p.id === id).xy;
    assert.deepEqual(at(drawn, here), at(raw, here));
    for (const x of drawn) {
      const moved = Math.hypot(x.xy[0] - at(raw, x.p.id)[0], x.xy[1] - at(raw, x.p.id)[1]) / u;
      assert.ok(moved < 8, `${x.p.id} moved ${moved.toFixed(1)}u`);
    }
  });
}

test('the camera keeps a hand’s breadth from the café’s walls, the feet where they are', () => {
  const { Vector3 } = require('three');
  const { CardPress, LacePress, Press, seeded } = require('./geo.ts');
  const { buildQuai } = require('./quai.ts');
  const { buildMistral } = require('./mistral.ts');
  const { Nav } = require('./nav.ts');
  const B = { dry: new Press(), fine: new Press(), wet: new Press(), lace: new LacePress(), glass: new Press(), cards: new CardPress(), signs: [], lamps: [], walk: [], blocks: [], rand: seeded(1102) };
  const quai = buildQuai(B);
  buildMistral(B, quai.mistral);
  const nav = new Nav(B.walk, B.blocks, { x0: -182, z0: -212, x1: 32, z1: 212 });
  const clearance = (x, z) => {
    let best = Infinity;
    for (let i = 0; i < 32; i++) {
      const a = (i / 32) * Math.PI * 2;
      for (let t = 0.01; t <= 0.6; t += 0.01) {
        if (!nav.walkable(x + Math.cos(a) * t, z + Math.sin(a) * t)) {
          best = Math.min(best, t);
          break;
        }
      }
    }
    return best;
  };
  // walk with the stick from the middle of the café straight into its east wall, as far as the feet may go
  let x = -31.6;
  let z = -13.0;
  for (let i = 0; i < 200; i++) [x, z] = nav.slide(x, z, 0.05, 0);
  const feet = clearance(x, z);
  assert.ok(feet < 0.3, `the feet stand ${feet.toFixed(2)} m from the wall (the walk’s case)`);
  const [ex, ez] = nav.eyeAt(x, z);
  assert.ok(nav.walkable(ex, ez));
  assert.ok(clearance(ex, ez) >= 0.3, `the eye is ${clearance(ex, ez).toFixed(2)} m from the wall`);
  // in the open, the eye is the feet
  const mid = new Vector3(-31.6, 0, -13.0);
  assert.deepEqual(nav.eyeAt(mid.x, mid.z), [mid.x, mid.z]);
  // the frame puts the camera at the eye
  const engine = fs.readFileSync(path.join(__dirname, 'engine.ts'), 'utf8');
  assert.match(engine, /nav\.eyeAt\(this\.feet\.x, this\.feet\.z\)[\s\S]{0,80}camera\.position\.set\(eyeX, this\.eyeY, eyeZ\)/);
});

test('a tap on someone opens the talk in one tap, on a day that has people to talk to; else the hint promises none', () => {
  const stage = fs.readFileSync(path.join(__dirname, 'stage.ts'), 'utf8');
  // one tap on a person who is in today's talk opens it (no pill to tap a second time)
  assert.match(stage, /if \(TALKERS\[hit\.key as CastId\] && this\.person\(hit\.key\)\) \{\s*this\.talkTo\(hit\.key\);/);
  const { canTalkOn } = require('./stage.ts');
  const page = (storylets) => ({ season_id: 's1', segment: 'g1', day: '3', key: 'g1.3', title_fr: 'Lila attend', movements: [], storylets });
  // day 3 of the walk: a page written at night, no talk storylet: the pill was all there was
  assert.equal(canTalkOn(page([])), false);
  assert.equal(canTalkOn(page([{ id: 'talk', cue: 'talk', who: null, after_seconds: null, lines: [], chips: [], people: [{ who: 'lila_bonnet' }] }])), true);
  const screen = fs.readFileSync(path.join(WEB_ROOT, 'components/quartier/QuartierScreen.tsx'), 'utf8');
  assert.match(screen, /ui\?\.canTalk === false \? copy\.walkHint : copy\.roamHint/);
  const { COPY } = require('@/components/quartier/QuartierScreen.tsx');
  for (const lang of Object.keys(COPY)) assert.ok(COPY[lang].walkHint && !/parler/.test(COPY[lang].walkHint), lang);
});
