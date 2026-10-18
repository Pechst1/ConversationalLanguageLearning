// node --test lib/season-items.test.js
//
// Les objets de la saison: one drawn object per tentpole, handed over by the person it belongs
// to, carried on through the gap after it.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));

const { SEASON_ITEMS, itemForPart, itemHandedIn } = require('./season-items.ts');
const { CAMEO_CAST } = require('./cameo.ts');

const season = JSON.parse(
  fs.readFileSync(path.join(WEB_ROOT, '..', 'app/data/season/s1/season.json'), 'utf8'),
);

test('every tentpole of season 1 hands over exactly one object', () => {
  const tentpoles = season.segments.filter((s) => s.kind === 'tentpole').map((s) => s.id);
  assert.deepEqual(SEASON_ITEMS.map((item) => item.segment), tentpoles);
  assert.equal(new Set(SEASON_ITEMS.map((item) => item.id)).size, SEASON_ITEMS.length);
});

test('every object is drawn and carried by somebody in the cast', () => {
  const drawings = fs.readFileSync(path.join(WEB_ROOT, 'components/cast/items/PlotItem.tsx'), 'utf8');
  SEASON_ITEMS.forEach((item) => {
    assert.match(drawings, new RegExp(`\\b${item.id}: \\(\\) =>`), `${item.id} has a drawing`);
    assert.ok(CAMEO_CAST.some((who) => who.id === item.carrier), `${item.id}: ${item.carrier}`);
    assert.ok(item.line.fr.length <= 52, `too long for a bubble: ${item.line.fr}`);
    assert.ok(item.line.de && item.line.en && item.name.de && item.name.en, item.id);
  });
});

test('a gap carries the object of the tentpole before it, and only a tentpole hands one over', () => {
  assert.equal(itemForPart({ season_id: 's1', segment: 'g3' }).id, 'petition');
  assert.equal(itemHandedIn({ season_id: 's1', segment: 'g3' }), null);
  assert.equal(itemHandedIn({ season_id: 's1', segment: 't3' }).id, 'petition');
  assert.equal(itemForPart({ season_id: 's1', segment: 'e1' }), null, 'the epilogue has none of its own yet');
  assert.equal(itemForPart({ season_id: 's2', segment: 't1' }), null, 'another season has its own objects');
  assert.equal(itemForPart(null), null);
});
