/* WP-143 «One stage, one light» · a face is never cropped, the light is derived from
 * the plate, and nothing in it moves under Reduce Motion.
 *   node --test components/cast/stage-light.test.js
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

const { RIGS, rigFor } = require('./cast-registry.ts');
const { PanelStage } = require('./PanelStage.tsx');
const { CastRig } = require('./CastRig.tsx');
const { RvStage } = require('../revue/RvStage.tsx');
const frame = require('../../lib/stage-frame.ts');
const grade = require('../../lib/stage-grade.ts');

const SPEAKERS = RIGS.filter((rig) => rig.id !== 'user').map((rig) => rig.id);
const ASPECTS = { band: 390 / 168, une: 16 / 9, full: 4 / 3, square: 1, phone: 9 / 16, narrow: 0.4 };

function combos(size) {
  const out = [];
  const pick = (start, chosen) => {
    if (chosen.length === size) return out.push(chosen);
    for (let i = start; i < SPEAKERS.length; i += 1) pick(i + 1, [...chosen, SPEAKERS[i]]);
  };
  pick(0, []);
  return out;
}

const html = (element) => renderToStaticMarkup(element);
const stage = (props) => html(React.createElement(PanelStage, props));
const heads = (markup) =>
  [...markup.matchAll(/data-head="([^"]+)"/g)].map((m) => {
    const [x, y, w, h] = m[1].split(' ').map(Number);
    return { x, y, w, h };
  });

// ── the framing rule ──────────────────────────────────────────────────────────

test('a face is never cropped: every cast of one to three, every aspect, both framings, any focus', () => {
  let checked = 0;
  for (const size of [1, 2, 3]) {
    for (const cast of combos(size)) {
      for (const [name, aspect] of Object.entries(ASPECTS)) {
        for (const framing of ['band', 'fill']) {
          for (const focusX of [0, 0.5, 1]) {
            for (const speaker of [null, ...cast]) {
              const layout = frame.stageLayout({
                members: cast.map((rigId) => ({ rigId, speaking: rigId === speaker })),
                aspect,
                rigOf: rigFor,
                framing,
                focus: { x: focusX, y: 0.5 },
              });
              assert.equal(layout.length, cast.length);
              for (const place of layout) {
                assert.ok(
                  frame.boxInFrame(place.head, frame.HEAD_MARGIN),
                  `${place.rigId} cropped in ${cast.join('+')} @${name} ${framing} focus ${focusX}: ${JSON.stringify(place.head)}`,
                );
                checked += 1;
              }
            }
          }
        }
      }
    }
  }
  assert.ok(checked > 10000, `checked ${checked} heads`);
});

test('the rule moves a figure only when its head would leave the frame (WP-116 slots kept otherwise)', () => {
  // A wide band: the three slots of WP-116 already keep every head in.
  const wide = frame.stageLayout({ members: [{ rigId: 'margaux_barman' }, { rigId: 'marin_leveque', speaking: true }, { rigId: 'lila_bonnet' }], aspect: 390 / 168, rigOf: rigFor });
  assert.deepEqual(wide.map((p) => p.centre), [20, 50, 80]);
  assert.equal(wide[1].bottom, 0, 'the speaker stands on the bottom edge');
  // A square plate: the raw outer slots would cut both outer heads; the rule brings them in.
  const raw = frame.headBox(rigFor('augustin_de_roncourt'), 'bust', { centre: 20, height: 82 * 0.92, bottom: 0 }, 1);
  assert.ok(raw.x < 0, 'without the rule Gus’s face leaves a square frame');
  const square = frame.stageLayout({ members: [{ rigId: 'augustin_de_roncourt' }, { rigId: 'marin_leveque', speaking: true }, { rigId: 'lila_bonnet' }], aspect: 1, rigOf: rigFor });
  assert.ok(square[0].centre > 20 && square[2].centre < 80);
  for (const place of square) assert.ok(frame.boxInFrame(place.head, frame.HEAD_MARGIN));
});

test('the stage renders every head box inside its frame, and fill draws whole figures', () => {
  const members = [{ id: 'romy_tremblay', speaking: true }, { id: 'marin', mood: 'happy' }, { id: 'lila' }];
  for (const aspect of Object.values(ASPECTS)) {
    for (const framing of ['band', 'fill']) {
      const markup = stage({ members, aspect, framing, plateUrl: null });
      const boxes = heads(markup);
      assert.equal(boxes.length, 3);
      for (const box of boxes) assert.ok(frame.boxInFrame(box, frame.HEAD_MARGIN - 0.1), `${framing} @${aspect}: ${JSON.stringify(box)}`);
      assert.match(markup, new RegExp(`data-framing="${framing}"`));
      if (framing === 'fill') assert.equal((markup.match(/data-crop="full"/g) || []).length, 3, 'whole figures in fill');
    }
  }
});

test('a focus point keeps its part of the plate in a 9:16 crop', () => {
  assert.equal(frame.plateObjectPosition({ plateAspect: 16 / 9, stageAspect: 9 / 16, focus: { x: 0.5, y: 0.5 } }), '50% 50%');
  assert.equal(frame.plateObjectPosition({ plateAspect: 16 / 9, stageAspect: 9 / 16, focus: { x: 0, y: 0.5 } }), '0% 50%');
  const right = frame.plateObjectPosition({ plateAspect: 16 / 9, stageAspect: 9 / 16, focus: { x: 0.7, y: 0.5 } });
  // Visible share 0.316: the focus at 0.7 sits mid-frame when the plate starts at 0.542.
  assert.equal(right, '79.3% 50%');
  // A plate narrower than the stage is cropped top and bottom instead.
  assert.equal(frame.plateObjectPosition({ plateAspect: 1, stageAspect: 2, focus: { x: 0.2, y: 0.25 } }), '50% 0%');
});

test('the head box is the rig’s own authored head, read in the crop the stage draws', () => {
  const romy = rigFor('romy_tremblay');
  const bust = frame.headFraction(romy, 'bust');
  assert.equal(bust.y, 0, 'Romy’s head starts at the top of her bust crop');
  assert.ok(bust.w > 0.7 && bust.w <= 1);
  const full = frame.headFraction(romy, 'full');
  assert.ok(full.y > 0.1 && full.h < 0.4, 'in a whole figure the head is the upper third');
});

// ── the grade ─────────────────────────────────────────────────────────────────

function plate(width, height, colourAt) {
  const data = new Uint8ClampedArray(width * height * 4);
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const [r, g, b] = colourAt(x, y);
      const i = (y * width + x) * 4;
      data[i] = r; data[i + 1] = g; data[i + 2] = b; data[i + 3] = 255;
    }
  }
  return data;
}

test('the light comes from the plate’s bright side', () => {
  const W = 32;
  const H = 24;
  const fromLeft = grade.samplePalette(plate(W, H, (x) => { const v = 240 - x * 6; return [v, v, v]; }), W, H);
  const fromRight = grade.samplePalette(plate(W, H, (x) => { const v = 50 + x * 6; return [v, v, v]; }), W, H);
  assert.ok(fromLeft.light.x < -0.5);
  assert.ok(fromRight.light.x > 0.5);
  assert.equal(grade.gradeFromPalette(fromLeft).side, -1);
  assert.equal(grade.gradeFromPalette(fromRight).side, 1);
  const fromTop = grade.samplePalette(plate(W, H, (x, y) => { const v = 240 - y * 8; return [v, v, v]; }), W, H);
  assert.ok(grade.gradeFromPalette(fromTop).height > grade.gradeFromPalette(fromLeft).height, 'light from above stands higher');
});

test('the grade is the plate’s colour: a warm plate warms the cast, its shadow and highlight become ink and rim', () => {
  const W = 32;
  const H = 24;
  const warm = grade.samplePalette(plate(W, H, (x, y) => { const v = (x + y) * 4; return [Math.min(255, 90 + v), Math.min(255, 60 + v * 0.8), 30 + v * 0.4]; }), W, H);
  const cool = grade.samplePalette(plate(W, H, (x, y) => { const v = (x + y) * 4; return [30 + v * 0.4, Math.min(255, 60 + v * 0.8), Math.min(255, 90 + v)]; }), W, H);
  const w = grade.gradeFromPalette(warm);
  const c = grade.gradeFromPalette(cool);
  assert.ok(w.slope[0] > w.slope[2], 'warm: red gains on blue');
  assert.ok(c.slope[2] > c.slope[0], 'cool: blue gains on red');
  assert.ok(w.intercept[0] > w.intercept[2], 'the ink lifts toward the warm shadow');
  assert.notEqual(w.rim, c.rim);
  assert.notEqual(w.shadow, c.shadow);
  assert.match(w.rim, /^#[0-9a-f]{6}$/);
  // Deterministic: the same plate, the same grade.
  assert.deepEqual(grade.gradeFromPalette(warm), w);
  assert.equal(w.sampled, true);
  assert.equal(grade.NEUTRAL_GRADE.sampled, false);
});

test('a quiet plate quiets the cast; a grainy plate lays more grain', () => {
  const W = 32;
  const H = 24;
  const flatGrey = grade.samplePalette(plate(W, H, () => [128, 128, 128]), W, H);
  assert.equal(flatGrey.texture, 0);
  assert.equal(flatGrey.saturation, 0);
  const grey = grade.gradeFromPalette(flatGrey);
  assert.equal(grey.saturate, 0.72, 'a grey plate takes the most colour out of the rigs');
  const grainy = grade.gradeFromPalette(grade.samplePalette(plate(W, H, (x, y) => { const v = (x * 7 + y * 13) % 2 ? 200 : 90; return [v, v, v]; }), W, H));
  assert.ok(grainy.grain > grey.grain);
  for (const g of [grey, grainy]) {
    for (const s of g.slope) assert.ok(s >= 0.55 && s <= 1.15);
    assert.ok(g.grain >= 0.08 && g.grain <= 0.22, 'the grain stays a texture, never a veil');
  }
});

test('the stage draws the plate’s light; light={false} and the discs draw the flat rig', () => {
  const lit = stage({ members: [{ id: 'romy_tremblay', speaking: true }], plateUrl: '/plates/x.webp', aspect: 4 / 3 });
  // On the server the plate is not read yet: the neutral light, the same markup the client hydrates.
  assert.match(lit, /data-lit="neutral"/);
  assert.match(lit, /<filter id="stage-light-[^"]+"/);
  assert.match(lit, /<g filter="url\(#stage-light-[^"]+\)" data-stage-light="">/);
  assert.match(lit, /class="cast-stage__grain"/);
  assert.match(lit, /data-dof=""/);
  assert.match(lit, /--stage-shadow:rgba\(/);
  const flat = stage({ members: [{ id: 'romy_tremblay', speaking: true }], plateUrl: '/plates/x.webp', aspect: 4 / 3, light: false });
  assert.doesNotMatch(flat, /data-lit|<filter|cast-stage__grain|data-stage-light|data-dof/);
  // The portrait discs (CastRig without `filter`) are untouched.
  const disc = html(React.createElement(CastRig, { id: 'romy_tremblay', crop: 'head', size: 64 }));
  assert.doesNotMatch(disc, /filter|data-stage-light/);
});

test('the Revue stage reads its own plate, and a plate still in the press is not read', () => {
  const live = html(React.createElement(RvStage, { plateUrl: '/plates/marche.webp', size: 'full', cast: [{ id: 'romy_tremblay', hold: 'notebook', speaking: true }], you: { outfit: 'coat' } }));
  assert.match(live, /data-lit="neutral"/);
  const box = heads(live)[0];
  assert.ok(frame.boxInFrame(box, frame.HEAD_MARGIN - 0.1), 'Romy’s face is in the arrive frame');
  const pending = html(React.createElement(RvStage, { plateUrl: '/plates/marche.webp', size: 'band', cast: [{ id: 'romy_tremblay', hold: null }], pending: { folio: 'sous presse' } }));
  assert.doesNotMatch(pending, /data-lit/);
});

// ── Reduce Motion ─────────────────────────────────────────────────────────────

test('nothing in the light moves: no animation, and Reduce Motion drops its fade-in', () => {
  const css = fs.readFileSync(path.join(ROOT, 'styles/cast-rig.css'), 'utf8');
  const wp143 = css.slice(css.indexOf('WP-143'));
  assert.ok(wp143.length > 100, 'the WP-143 block is in cast-rig.css');
  assert.doesNotMatch(wp143, /animation\s*:/, 'the light has no animation');
  const reduce = wp143.slice(wp143.indexOf('@media (prefers-reduced-motion: reduce)'));
  assert.ok(reduce.startsWith('@media'), 'a Reduce Motion block');
  for (const selector of ['.cast-stage__grain', '.cast-stage[data-lit] .cast-stage__figure > .cast-rig']) {
    assert.ok(reduce.includes(selector), `${selector} under Reduce Motion`);
  }
  assert.match(reduce, /transition:\s*none/);
  // The stage markup carries no inline motion of its own.
  const markup = stage({ members: [{ id: 'romy_tremblay', speaking: true }, { id: 'marin' }], plateUrl: '/p.webp', aspect: 1 });
  assert.doesNotMatch(markup, /animation|transition/);
  // The light never animates the SVG itself (no SMIL in the filter).
  assert.doesNotMatch(markup, /<animate|<set /);
});

test('the light adds no colour token and no font: its colours are the plate’s or the rigs’ own', () => {
  const css = fs.readFileSync(path.join(ROOT, 'styles/cast-rig.css'), 'utf8');
  const wp143 = css.slice(css.indexOf('WP-143'));
  assert.doesNotMatch(wp143, /--av2-[a-z-]+\s*:/, 'no av2 token is defined');
  assert.doesNotMatch(wp143, /font-family/);
  assert.doesNotMatch(wp143.replace(/url\("data:[^"]+"\)/g, ''), /#[0-9a-f]{3,8}\b/i, 'no literal colour outside the procedural grain');
  const src = fs.readFileSync(path.join(ROOT, 'lib/stage-grade.ts'), 'utf8');
  // Colour triples (not the [0, 1, 2] channel indices or the [1, 1, 1] identity slope).
  const literals = [...src.matchAll(/\[(\d+), (\d+), (\d+)\]/g)].map((m) => m.slice(1).map(Number)).filter((t) => Math.max(...t) > 2).map((t) => t.join(','));
  assert.deepEqual([...new Set(literals)].sort(), ['128,128,128', '20,17,13', '248,243,232'].sort(), 'only ink, paper and the empty plate’s grey');
});
