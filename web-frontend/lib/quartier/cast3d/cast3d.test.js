// node --test lib/quartier/cast3d/cast3d.test.js
//
// Le Quartier · the cast in the round. Everyone the quarter stands up has a body; every body is
// skinned to its skeleton, printed on the people's own line ids and kept to a phone's budget; the
// troupe stands them up instead of printing cards; and the street's pieces leave the people's
// ids alone, so a sleeve against a wall always gets its line.

const assert = require('node:assert/strict');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..', '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  return originalResolve.call(this, request, ...rest);
};

const { Group, Vector3 } = require('three');
const { PEOPLE, personFor } = require('./people/index.ts');
const { sculptPerson } = require('./model.ts');
const { PLATE } = require('./kit.ts');
const { BONES, joints, posed } = require('./rig.ts');
const { nextId } = require('../geo.ts');
const { Troupe } = require('../cast.ts');
const { makeWorld } = require('../materials.ts');
const { MARKS, ROOM, SEATS } = require('../mistral.ts');

/** Who the quarter stands up in Le Mistral (`engine.ts`, loadCast). */
const ON_STAGE = ['augustin_de_roncourt', 'marin_leveque', 'lila_bonnet', 'margaux_barman', 'camille_marchand'];

test('everyone on stage in Le Mistral has a body, and the app’s short names find them too', () => {
  for (const key of ON_STAGE) assert.ok(personFor(key), `${key} has no body in the round`);
  assert.equal(personFor('gus').key, 'augustin_de_roncourt');
  assert.equal(personFor('Margaux').key, 'margaux_barman');
  assert.equal(personFor('odile').key, 'odile_ferrand');
  // a passer-by stays on paper
  assert.equal(personFor('passant:3'), null);
  assert.equal(new Set(PEOPLE.map((p) => p.key)).size, PEOPLE.length, 'two people share a key');
});

test('every body is skinned to its skeleton, on the people’s ids, within a phone’s budget', () => {
  const plate = new Set(Object.values(PLATE));
  for (const person of PEOPLE) {
    for (const variant of person.variants ?? [undefined]) {
      const who = `${person.key}${variant ? ` (${variant})` : ''}`;
      const { geometry, triangles } = sculptPerson(person, variant);
      assert.ok(triangles > 2000 && triangles < 20000, `${who}: ${triangles} triangles`);
      const box = geometry.boundingBox;
      assert.ok(box.min.y > -0.01, `${who} stands below the floor (${box.min.y})`);
      const h = box.max.y / person.body.height;
      assert.ok(h > 0.95 && h < 1.2, `${who} is ${box.max.y.toFixed(2)} m against ${person.body.height} m`);
      const index = geometry.getAttribute('skinIndex');
      const weight = geometry.getAttribute('skinWeight');
      const ink = geometry.getAttribute('aInk');
      const ids = new Set();
      for (let i = 0; i < index.count; i++) {
        const w = weight.getX(i) + weight.getY(i) + weight.getZ(i) + weight.getW(i);
        assert.ok(Math.abs(w - 1) < 1e-5, `${who}: vertex ${i} weighs ${w}`);
        for (const b of [index.getX(i), index.getY(i)]) assert.ok(b < BONES.length, `${who}: vertex ${i} on bone ${b}`);
        ids.add(ink.array[i * 4 + 3]);
      }
      ids.forEach((id) => assert.ok(plate.has(id), `${who} prints on line id ${id}, not one of the people's`));
      assert.ok(ids.has(PLATE.skin) && ids.has(PLATE.hair), `${who} has no face or no hair`);
    }
  }
});

test('a pose moves what it turns and nothing else', () => {
  const J = joints(PEOPLE[0].body);
  const still = posed(J, {});
  const palm = J.palm.R.clone().applyMatrix4(still.handR);
  assert.ok(palm.distanceTo(J.palm.R) < 1e-9);
  const bent = posed(J, { foreR: [-1.2, 0, 0] });
  assert.ok(J.palm.R.clone().applyMatrix4(bent.handR).distanceTo(J.palm.R) > 0.1, 'the right hand did not come up');
  assert.ok(J.palm.L.clone().applyMatrix4(bent.handL).distanceTo(J.palm.L) < 1e-9, 'the left hand moved too');
});

test('the street’s pieces never take the people’s line ids', () => {
  const seen = new Set();
  for (let i = 0; i < 400; i++) {
    const id = nextId();
    assert.ok(id >= 1 && id <= 63, `id ${id}`);
    assert.ok(id < PLATE.skin || id > PLATE.prop, `id ${id} is one of the people's`);
    seen.add(id);
  }
  assert.equal(seen.size, 63 - 8);
});

test('a troupe that stands people up in the round prints no card for them', async () => {
  const printed = [];
  const art = {
    figure: (key) => {
      printed.push(key);
      return null;
    },
    item: () => null,
  };
  const calls = [];
  const fake = {
    key: 'margaux_barman',
    root: new Group(),
    pos: new Vector3(),
    place(p) {
      this.pos.copy(p);
      calls.push('place');
      return this;
    },
    express(expression, gesture) {
      calls.push(`express ${expression} ${gesture}`);
    },
    update() {},
    dispose() {},
  };
  const troupe = new Troupe(makeWorld(), art, 840, (spec) => (spec.key === fake.key ? fake : null));
  const f = await troupe.add({ key: 'margaux_barman', height: 1.66 }, MARKS.zincInside);
  assert.equal(f, fake);
  assert.equal(troupe.get('margaux_barman'), fake);
  assert.ok(troupe.group.children.includes(fake.root));
  assert.ok(fake.pos.equals(MARKS.zincInside));
  await troupe.face('margaux_barman', 'joie', 'salut');
  assert.deepEqual(calls, ['place', 'express joie salut']);
  assert.deepEqual(printed, []);
});

test('the café’s seats are inside the room, on its floor, the booth’s facing the room', () => {
  assert.ok(SEATS.length >= 5);
  for (const s of SEATS) {
    assert.ok(s.at.x > ROOM.x0 && s.at.x < ROOM.x1 && s.at.z > ROOM.z0 && s.at.z < ROOM.z1, `a seat outside at ${s.at.x}, ${s.at.z}`);
    assert.equal(s.at.y, ROOM.floor);
    assert.ok(s.height > 0.3 && s.height < 0.9);
  }
  for (const mark of [MARKS.boothCorner, MARKS.boothMiddle, MARKS.boothLeft]) {
    const s = SEATS.find((x) => x.at === mark);
    assert.ok(s, 'a booth place has no seat');
    // the booth's back is the north wall: sitting there you face +z, into the room
    assert.equal(s.yaw, 0);
  }
  // Gus stands on the bench, above its seat, and stays standing
  assert.ok(MARKS.boothBench.y - ROOM.floor > 0.3);
});
