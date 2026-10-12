/* La troupe vivante · the jointed cast keeps the rigs' drawing line for line, acts every face and
 * gesture, and never moves in a way CSS cannot stop.
 *   node --test components/cast/vivant/vivant.test.js
 */
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');

require('../../../node_modules/sucrase/register/ts');
require('../../../node_modules/sucrase/register/tsx');

const ROOT = path.resolve(__dirname, '../../..');
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) return originalResolve.call(this, path.join(ROOT, request.slice(2)), ...rest);
  return originalResolve.call(this, request, ...rest);
};

const React = require(path.join(ROOT, 'node_modules/react'));
const { renderToStaticMarkup } = require(path.join(ROOT, 'node_modules/react-dom/server'));
global.React = React;

const { CastRig } = require('../CastRig.tsx');
const { VivantFigure } = require('./VivantFigure.tsx');
const { FIGURES, figureFor } = require('./registry.ts');
const { EXPRESSIONS, GESTURES, armFrames, elbowAt, figureCss, palmAt, solveKeys } = require('./kit.ts');

const vivant = (props) => renderToStaticMarkup(React.createElement(VivantFigure, props));
const rig = (props) => renderToStaticMarkup(React.createElement(CastRig, { still: true, blink: false, ...props }));
const paths = (html) => [...html.matchAll(/<path d="([^"]+)"/g)].map((m) => m[1]);
const numbers = (d) => (d.match(/-?\d*\.?\d+/g) || []).map(Number);

test('six of the cast act: Romy, Gus, Margaux, Marin, M. Marchand and Lila', () => {
  assert.deepEqual(FIGURES.map((f) => f.rig.id).sort(), [
    'augustin_de_roncourt', 'landlord_marchand', 'lila_bonnet', 'margaux_barman', 'marin_leveque', 'romy_tremblay',
  ]);
  assert.equal(figureFor('Gus')?.key, 'gus', 'the cast aliases work');
  assert.equal(figureFor('romy_tremblay')?.key, 'romy');
  assert.equal(figureFor('user'), null, 'Toi has no jointed figure');
});

/**
 * At rest a figure is its rig: every path the rig draws is drawn again, except the sleeves cut at
 * the elbow, whose two halves must meet where the original curve passes.
 */
test('at rest each figure draws its rig line for line', () => {
  for (const fig of FIGURES) {
    const whole = paths(vivant({ id: fig.key, still: true }));
    const drawn = new Set([...whole, ...whole.flatMap((d) => d.split(/(?=M)/).map((s) => s.trim()))]);
    const pieces = [...drawn].map(numbers);
    const close = (a, b) => Math.abs(a - b) < 0.6;
    for (const d of paths(rig({ id: fig.rig.id }))) {
      if (drawn.has(d)) continue;
      // a path of several strokes may be drawn stroke by stroke
      for (const sub of d.split(/(?=M)/).map((s) => s.trim())) {
        if (drawn.has(sub)) continue;
        const q = sub.match(/^M\s*(-?[\d.]+)[ ,](-?[\d.]+)\s*Q\s*(-?[\d.]+)[ ,](-?[\d.]+)\s+(-?[\d.]+)[ ,](-?[\d.]+)$/);
        const c = sub.match(/^M\s*(-?[\d.]+)[ ,](-?[\d.]+)\s*C\s*(-?[\d.]+)[ ,](-?[\d.]+)\s+(-?[\d.]+)[ ,](-?[\d.]+)\s+(-?[\d.]+)[ ,](-?[\d.]+)$/);
        assert.ok(q || c, `${fig.key}: the rig's "${sub}" is missing`);
        const p = (q || c).slice(1).map(Number);
        const start = [p[0], p[1]];
        const end = [p[p.length - 2], p[p.length - 1]];
        // the cut: a piece starting where the stroke starts and another ending where it ends,
        // meeting at a point of the curve
        const first = pieces.find((n) => close(n[0], start[0]) && close(n[1], start[1]) && n.length === p.length);
        const last = pieces.find((n) => close(n[n.length - 2], end[0]) && close(n[n.length - 1], end[1]) && n.length === p.length);
        assert.ok(first && last, `${fig.key}: "${sub}" is neither drawn nor cut in two`);
        assert.ok(close(first[first.length - 2], last[0]) && close(first[first.length - 1], last[1]), `${fig.key}: the halves of "${sub}" meet`);
      }
    }
  }
});

test('every figure has ten faces and six gestures, each its own', () => {
  for (const fig of FIGURES) {
    assert.deepEqual(Object.keys(fig.expressions).sort(), [...EXPRESSIONS].sort(), fig.key);
    assert.deepEqual(Object.keys(fig.gestures).sort(), [...GESTURES].sort(), fig.key);
    for (const id of GESTURES) {
      const g = fig.gestures[id];
      assert.ok(g.label && g.line && g.note, `${fig.key} ${id} is described`);
      assert.equal(g.keys[0].at, 0, `${fig.key} ${id} starts at rest`);
      assert.equal(g.keys[g.keys.length - 1].at, 1, `${fig.key} ${id} ends at rest`);
      assert.ok(g.peak > 0 && g.peak < g.keys.length - 1, `${fig.key} ${id}: the still pose is inside the gesture`);
      g.keys.forEach((k, i) => i && assert.ok(k.at > g.keys[i - 1].at, `${fig.key} ${id}: keys in order`));
    }
  }
  // the same slot is played differently by each of them
  for (const id of GESTURES) {
    const lines = new Set(FIGURES.map((f) => f.gestures[id].line));
    assert.equal(lines.size, FIGURES.length, `${id}: everyone says it their own way`);
  }
  for (const id of EXPRESSIONS) {
    const labels = new Set(FIGURES.map((f) => JSON.stringify([f.expressions[id].eyes, f.expressions[id].brows, f.expressions[id].mouth])));
    assert.equal(labels.size, FIGURES.length, `${id}: six different faces`);
  }
});

test('every face and every gesture renders, in every crop, as a labelled image', () => {
  for (const fig of FIGURES) {
    for (const expression of EXPRESSIONS) {
      for (const crop of ['full', 'bust', 'head']) {
        const html = vivant({ id: fig.key, expression, crop, size: 90 });
        assert.match(html, /^<svg /);
        assert.match(html, new RegExp(`viewBox="${fig.rig.crops[crop].join(' ')}"`));
        assert.match(html, new RegExp(`aria-label="${fig.name.replace('.', '\\.')}"`));
        assert.match(html, new RegExp(`tv-e--${expression}`));
      }
    }
    for (const gesture of GESTURES) {
      const html = vivant({ id: fig.key, gesture, size: 90 });
      assert.match(html, new RegExp(`class="tv tv--${fig.key} [^"]*tv-g--${gesture} tv--acting`));
      assert.match(html, /<style>/, 'a lone figure carries its own motion');
      assert.doesNotMatch(vivant({ id: fig.key, gesture, css: 'none' }), /<style>/);
    }
    const all = vivant({ id: fig.key, faces: 'all', css: 'none' });
    for (const expression of EXPRESSIONS) assert.match(all, new RegExp(`tv-face--${expression}\\b`), `${fig.key}: all faces drawn for a canvas`);
  }
});

test('a hand lands where its key sends it, and no elbow snaps between keys', () => {
  for (const fig of FIGURES) {
    for (const id of GESTURES) {
      const keys = fig.gestures[id].keys;
      const solved = solveKeys(fig, keys);
      keys.forEach((k, i) => {
        for (const side of ['L', 'R']) {
          const to = k[side]?.to;
          if (!to) continue;
          const arm = fig.arms[side];
          const upper = Math.hypot(arm.elbow[0] - arm.shoulder[0], arm.elbow[1] - arm.shoulder[1]);
          const fore = Math.hypot(arm.palm[0] - arm.elbow[0], arm.palm[1] - arm.elbow[1]) * (k[side].reach ?? 1);
          const away = Math.hypot(to[0] - arm.shoulder[0], to[1] - arm.shoulder[1]);
          // out of reach (or closer than a folded arm allows) the arm points there: nothing to land
          if (away > upper + fore - 0.5 || away < Math.abs(fore - upper) + 0.5) continue;
          const p = palmAt(arm, solved[i][side]);
          assert.ok(Math.hypot(p[0] - to[0], p[1] - to[1]) < 0.75, `${fig.key} ${id} key ${i} ${side}: palm at ${p} for ${to}`);
        }
      });
      for (const side of ['L', 'R']) {
        let prev = null;
        for (const f of armFrames(fig, keys, side)) {
          const e = elbowAt(fig.arms[side], f.a);
          if (prev && f.at > prev.at) {
            const speed = Math.hypot(e[0] - prev.e[0], e[1] - prev.e[1]) / ((f.at - prev.at) * 100);
            assert.ok(speed < 25, `${fig.key} ${id} ${side}: the elbow jumps ${speed.toFixed(1)} px per 1% at ${f.at}`);
          }
          prev = { at: f.at, e };
        }
      }
    }
  }
});

test('no SMIL and no script: every move is CSS that reduced motion and `still` stop', () => {
  for (const file of fs.readdirSync(path.join(__dirname, 'figures'))) {
    const source = fs.readFileSync(path.join(__dirname, 'figures', file), 'utf8');
    assert.doesNotMatch(source, /<animate/i, file);
  }
  const shared = fs.readFileSync(path.join(ROOT, 'styles/cast-vivant.css'), 'utf8');
  assert.match(shared, /@media \(prefers-reduced-motion: reduce\)[\s\S]*\.tv-blink[\s\S]*animation: none/);
  assert.match(fs.readFileSync(path.join(ROOT, 'pages/_app.tsx'), 'utf8'), /styles\/cast-vivant\.css/);
  for (const fig of FIGURES) {
    const css = figureCss(fig);
    assert.match(css, /@media \(prefers-reduced-motion: reduce\)/, `${fig.key}: gestures stop for Reduce Motion`);
    assert.match(css, /\.tv--still/, `${fig.key}: and for still`);
    assert.match(vivant({ id: fig.key, gesture: 'bravo', still: true }), /tv--still/);
  }
});
