// Package O-2 — the Seal's gold rim and the leaf glyph (docs/ATELIER_GOLD_ECONOMY_PLAN.md §3, §4.4, §11).
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  return originalResolve.call(this, request, ...rest);
};

const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const { Seal, sealGoldRimPath } = require('@/components/ui/Seal.tsx');
const { GoldGlyph } = require('./GoldGlyph.tsx');

const h = React.createElement;

test('the rim gilds clockwise from twelve and closes into a full band at the mark', () => {
  assert.equal(sealGoldRimPath(0), null);
  const half = sealGoldRimPath(0.5);
  assert.match(half, /^M 0,-104\.5 A 104\.5,104\.5 0 0,1 0,104\.5 L 0,100\.5 A 100\.5,100\.5 0 0,0 0,-100\.5 Z$/);
  assert.match(sealGoldRimPath(0.75), / 0 1,1 /, 'past half way the arc is the large one');
  assert.equal(sealGoldRimPath(1), sealGoldRimPath(3), 'full is full');
  assert.doesNotMatch(sealGoldRimPath(1), /L /, 'the full rim is an annulus, not a sector');
});

test('the Seal draws the rim only when given one, and says it', () => {
  const plain = renderToStaticMarkup(h(Seal, { variant: 'quad', no: 12 }));
  assert.doesNotMatch(plain, /av2-seal__gold/);
  const gilt = renderToStaticMarkup(h(Seal, { variant: 'quad', no: 12, gold: 0.4, goldLabel: 'Or +8 · 8 / 20 vers la journée pleine' }));
  assert.match(gilt, /data-gold="partial"/);
  assert.match(gilt, /av2-seal__gold-track/);
  assert.match(gilt, /av2-seal__gold-leaf/);
  assert.match(gilt, /aria-label="Sceau Nº 12 · Or \+8 · 8 \/ 20 vers la journée pleine"/);
  assert.match(renderToStaticMarkup(h(Seal, { gold: 1.2 })), /data-gold="full"/);
  assert.doesNotMatch(renderToStaticMarkup(h(Seal, { gold: 0 })), /av2-seal__gold-leaf/, 'an empty day shows the track alone');
});

test('the leaf: filled on its press when printed, dashed while à l’épreuve', () => {
  assert.match(renderToStaticMarkup(h(GoldGlyph)), /av2-gold-glyph__press[\s\S]*av2-gold-glyph__face/);
  assert.match(renderToStaticMarkup(h(GoldGlyph, { state: 'pending' })), /av2-gold-glyph__proof/);
});

test('the gold CSS is tokens only and keeps the information under Reduce Motion', () => {
  const css = fs.readFileSync(path.join(WEB_ROOT, 'styles/atelier-v2.css'), 'utf8');
  const block = css.slice(css.indexOf("Package O-2 — l'or on screen"));
  assert.ok(block.length > 1000);
  assert.doesNotMatch(block, /#[0-9a-fA-F]{3,8}\b/, 'no hex colour');
  assert.doesNotMatch(block, /rgba?\(|hsla?\(/, 'no raw colour');
  assert.match(block, /--av2-gold: var\(--av2-yellow\)/);
  assert.match(block, /@media \(prefers-reduced-motion: reduce\)[\s\S]*\.av2-gold-grain \{ display: none; \}/);
});
