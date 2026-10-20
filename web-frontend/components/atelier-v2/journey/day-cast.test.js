// node --test components/atelier-v2/journey/day-cast.test.js
//
// Les apparitions, tied to the day: the walk-ons are today's page's people, and a part of the
// season is «reached» only once its page has been read.

const assert = require('node:assert/strict');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..', '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

const { chapterReached, dayCast } = require('./day-cast.ts');

const part = { season_id: 's1', segment: 't2', kind: 'tentpole', day_in_segment: 1 };
const journey = (status) => ({
  scenario: { character_id: 'margaux_barman', character_name: 'Margaux' },
  steps: [
    { id: 'a', kind: 'scene', status, prompt: { season_part: part } },
    { id: 'b', kind: 'respond', status: 'pending', prompt: { character_id: 'lila_bonnet', character_name: 'Lila' } },
  ],
});

test('today’s cast is the page’s speakers, then every step’s face, once each', () => {
  const episode = {
    panels: [
      { dialogue: [{ character_id: 'augustin_de_roncourt', character_name: 'Gus' }, { character_id: 'user' }] },
      { dialogue: [{ character_id: 'lila_bonnet', character_name: 'Lila' }] },
    ],
  };
  assert.deepEqual(dayCast(journey('completed'), episode), ['augustin_de_roncourt', 'lila_bonnet', 'margaux_barman']);
  assert.deepEqual(dayCast(null), []);
});

test('the part of the season is reached once its page is read, not before', () => {
  assert.equal(chapterReached(journey('active')), null);
  assert.deepEqual(chapterReached(journey('completed')), part);
  const off = journey('completed');
  off.steps[0].prompt = {};
  assert.equal(chapterReached(off), null, 'off a scripted season');
});
