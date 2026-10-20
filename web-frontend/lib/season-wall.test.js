// node --test lib/season-wall.test.js
//
// Le mur du Mistral: the wall reaches as far as the pages read, keeps what the device was handed,
// spoils nothing still to come, and an object shows a choice only once it was made.

const assert = require('node:assert/strict');
const path = require('node:path');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));
const Module = require('node:module');
const resolveFilename = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) return resolveFilename.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  return resolveFilename.call(this, request, ...rest);
};

const React = require(path.join(WEB_ROOT, 'node_modules/react'));
const { renderToStaticMarkup } = require(path.join(WEB_ROOT, 'node_modules/react-dom/server'));
const { EMPTY_WALL, markLine, marksFor, wallHooks, wallText, WALL_COPY } = require('./season-wall.ts');
const { seasonItem } = require('./season-items.ts');
const { PlotItem } = require('../components/cast/items/PlotItem.tsx');

const wall = (extra) => ({ ...EMPTY_WALL, season_id: 's1', ...extra });

test('no season and nothing handed over is an empty wall', () => {
  assert.deepEqual(wallHooks(EMPTY_WALL, []), []);
  assert.deepEqual(wallHooks(null), []);
});

test('every tentpole up to the furthest part read hangs on the wall, the rest are numbered hooks', () => {
  const hooks = wallHooks(wall({ through: 3, pages: { t1: 'scene-1' } }));
  assert.equal(hooks.length, 8);
  assert.deepEqual(hooks.map((h) => h.number), [1, 2, 3, 4, 5, 6, 7, 8]);
  assert.deepEqual(hooks.filter((h) => h.owned).map((h) => h.item.id), ['cle_cigale', 'calendrier', 'petition']);
  assert.equal(hooks[0].page, 'scene-1');
  assert.equal(hooks[1].page, null);
  // the season's end hangs everything
  assert.ok(wallHooks(wall({ through: null })).every((h) => h.owned));
});

test("an object this device saw land stays on the wall even when the server cannot say", () => {
  const hooks = wallHooks(EMPTY_WALL, ['s1.cle_cigale', 's1.polaroid']);
  assert.deepEqual(hooks.filter((h) => h.owned).map((h) => h.item.id), ['cle_cigale', 'polaroid']);
});

test('an object shows only its own choice, said plainly in the learner language', () => {
  const marks = { 's1.fire_photo': 'margaux', 's1.promise_gus': 'yes' };
  const polaroid = seasonItem('polaroid');
  const petition = seasonItem('petition');
  assert.deepEqual(marksFor(polaroid, marks), { 's1.fire_photo': 'margaux' });
  assert.deepEqual(marksFor(petition, marks), { 's1.promise_gus': 'yes' });
  assert.deepEqual(marksFor(seasonItem('chaine'), marks), {});
  assert.match(markLine(polaroid, marks).fr, /Margaux/);
  assert.match(markLine(petition, { 's1.promise_gus': 'half' }).de, /Fragezeichen/);
  assert.equal(markLine(petition, { 's1.promise_gus': 'no' }), null);
  assert.equal(wallText(WALL_COPY.count, 'en', { n: 3, total: 8 }), '3 of 8 objects');
});

test('the drawings carry the mark, and only when it was made', () => {
  const html = (id, marks) => renderToStaticMarkup(React.createElement(PlotItem, { id, still: true, css: 'none', marks }));
  assert.ok(html('polaroid', { 's1.fire_photo': 'wall' }).includes('pi-mark--wall'));
  assert.ok(html('polaroid', { 's1.fire_photo': 'margaux' }).includes('pi-mark--till'));
  assert.ok(!html('polaroid', {}).includes('pi-mark'));
  assert.ok(html('petition', { 's1.promise_gus': 'yes' }).includes('pi-mark--promise'));
  assert.ok(!html('petition', { 's1.promise_gus': 'no' }).includes('pi-mark'));
});
