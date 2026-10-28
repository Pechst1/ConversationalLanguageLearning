// node --test lib/quartier/cast3d/cast3d.test.js
//
// Le Quartier · the cast in the round. Everyone the quarter stands up has a body; every body is
// skinned to its skeleton, printed on the people's own line ids and kept to a phone's budget; the
// troupe stands them up instead of printing cards; and the street's pieces leave the people's
// ids alone, so a sleeve against a wall always gets its line. The people the avatar kit draws
// (the passers-by, a forged place's stallholders) stand up from their record, whatever it holds,
// in the street, at the market and at the races, and stay cards when the quarter is on paper;
// across the square they change into a lighter body on the same bones.

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

const { createHash } = require('node:crypto');
const { Group, PerspectiveCamera, Vector3 } = require('three');
const { PEOPLE, personFor } = require('./people/index.ts');
const { sculptPerson } = require('./model.ts');
const { PLATE } = require('./kit.ts');
const { BONES, joints, posed } = require('./rig.ts');
const { nextId } = require('../geo.ts');
const { Troupe } = require('../cast.ts');
const { makeWorld } = require('../materials.ts');
const { MARKS, ROOM, SEATS } = require('../mistral.ts');
const { AVATAR_SLOTS, AVATAR_TOGGLES, DEFAULT_AVATAR, SLOT_OPTIONS } = require('../../avatar.ts');
const { passerbyAvatar, personAvatar } = require('../avatars.ts');
const { avatarPerson } = require('./avatar.ts');
const { ModelFigure, avatarRound } = require('./index.ts');
const { Crowd } = require('../crowd.ts');
const { Visit } = require('../visit.ts');

/** A body is skinned to its skeleton, on the people's ids, within a phone's budget. */
function checkBody(who, person, { min = 2000, max = 20000, hair = true } = {}) {
  const plate = new Set(Object.values(PLATE));
  const { geometry, triangles } = sculptPerson(person);
  assert.ok(triangles > min && triangles < max, `${who}: ${triangles} triangles`);
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
  assert.ok(ids.has(PLATE.skin), `${who} has no face`);
  if (hair) assert.ok(ids.has(PLATE.hair), `${who} has no hair`);
  return { geometry, triangles };
}

/** A quarter just big enough for the people of a place to be made in (no renderer, no press). */
function quarterFor(cast, site) {
  const troupes = [];
  return {
    troupes,
    q: { world: makeWorld(), cast, site, addTroupe: (t) => troupes.push(t), removeTroupe() {}, onTick: () => () => {}, on: () => () => {} },
  };
}

/** Who the quarter stands up in Le Mistral (`engine.ts`, loadCast). */
const ON_STAGE = ['augustin_de_roncourt', 'marin_leveque', 'lila_bonnet', 'margaux_barman', 'camille_marchand'];

test('everyone on stage in Le Mistral has a body, and the app’s short names find them too', () => {
  for (const key of ON_STAGE) assert.ok(personFor(key), `${key} has no body in the round`);
  assert.equal(personFor('gus').key, 'augustin_de_roncourt');
  assert.equal(personFor('Margaux').key, 'margaux_barman');
  assert.equal(personFor('odile').key, 'odile_ferrand');
  // a passer-by is none of the troupe's: the avatar kit stands them up (`avatar.ts`)
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

test('whatever the avatar kit draws stands up in the round: every part, and a hat over hair that stands up', () => {
  const records = [];
  for (const slot of AVATAR_SLOTS) {
    // colours change no shape; a few of them come with the people below
    if (slot === 'skin' || slot.endsWith('Color')) continue;
    for (const value of SLOT_OPTIONS[slot]) records.push([`${slot} ${value}`, { ...DEFAULT_AVATAR, [slot]: value }]);
  }
  for (const toggle of AVATAR_TOGGLES) records.push([toggle, { ...DEFAULT_AVATAR, [toggle]: !DEFAULT_AVATAR[toggle] }]);
  for (const hair of ['meche', 'chignon', 'afro', 'boucles', 'long']) {
    for (const hat of SLOT_OPTIONS.hat.slice(1)) records.push([`${hat} over ${hair}`, { ...DEFAULT_AVATAR, hair, hat, hatColor: 'jaune', hairColor: 'roux' }]);
  }
  for (const [who, cfg] of records) {
    // a street's worth of them goes on a phone: a third of a troupe person's budget at most
    checkBody(who, avatarPerson(cfg, { key: who, height: 1.7, seed: 3 }), { min: 3000, max: 14000, hair: cfg.hair !== 'chauve' });
  }
});

test('the same record stands up the same person, and someone else’s someone else', () => {
  const body = (cfg, seed) => {
    const g = sculptPerson(avatarPerson(cfg, { key: 'passant', seed })).geometry;
    return createHash('sha1').update(Buffer.from(g.getAttribute('position').array.buffer)).update(Buffer.from(g.getAttribute('aInk').array.buffer)).digest('hex');
  };
  // passant:0 of a street seeded 1789, as `crowd.ts` rolls them
  assert.equal(body(passerbyAvatar(1789), 1789), body(passerbyAvatar(1789), 1789));
  assert.notEqual(body(passerbyAvatar(1789), 1789), body(passerbyAvatar(1789 + 7919), 1789 + 7919));
  // a brief's look goes over the roll, and the roll is the same every time
  const look = { hat: 'casquette', hatColor: 'vert', top: 'veste', topColor: 'vert', beard: 'trois_jours' };
  const primeur = personAvatar(4101, look);
  for (const [slot, value] of Object.entries(look)) assert.equal(primeur[slot], value);
  assert.deepEqual(personAvatar(4101, look), primeur);
  // an earned piece a brief puts on (the clerk's foulard) stays on
  assert.equal(personAvatar(7311, { neck: 'foulard' }).neck, 'foulard');
});

test('the street’s passers-by stand up in the round from their record, and stay cards on paper', async () => {
  const round = quarterFor('round');
  const crowd = new Crowd(round.q, { count: 3, seed: 1789 });
  assert.deepEqual(round.troupes, [crowd.troupe]);
  const f = await crowd.troupe.add({ key: 'passant:1', height: 1.72 }, new Vector3(2, 0, -3));
  assert.ok(f instanceof ModelFigure, 'the passer-by is still a card');
  assert.ok(f.pos.equals(new Vector3(2, 0, -3)));
  // the record the card is drawn from: passant:1 of the street's seed
  const same = avatarPerson(passerbyAvatar(1 * 7919 + 1789), { key: 'passant:1', height: 1.72, seed: 1 * 7919 + 1789 });
  assert.equal(f.model.triangles, sculptPerson(same).triangles);
  // printed small, culled when off screen
  assert.equal(f.model.print.cell, 128);
  assert.ok(f.model.mesh.frustumCulled && f.model.mesh.boundingSphere.radius > 1);
  crowd.dispose();
  const paper = quarterFor('paper');
  const cards = new Crowd(paper.q, { count: 3 });
  assert.equal(cards.troupe.round, undefined, 'on paper the street stands nobody up');
});

test('a market stands the brief’s stallholders up in the round, dressed by its look', async () => {
  const site = {
    spec: {
      id: 'essai',
      people: [{ key: 'primeur', name: { fr: 'Le primeur', en: 'The greengrocer', de: 'Der Gemüsehändler' }, goods: 'fruits', pos: [4, 2], rot: 0, seed: 4101, look: { hat: 'casquette', top: 'veste' } }],
    },
    stalls: [{ goods: 'fruits', wares: [], front: new Vector3(4, 0, 2), facing: new Vector3(0, 0, 1) }],
    landmarks: [],
  };
  const { q, troupes } = quarterFor('round', site);
  const visit = new Visit(q);
  await visit.prepare();
  const f = troupes[0].get('vendeur:primeur');
  assert.ok(f instanceof ModelFigure, 'the primeur is still a card');
  const dressed = avatarPerson(personAvatar(4101, { hat: 'casquette', top: 'veste' }), { key: 'vendeur:primeur', seed: 4101 });
  assert.equal(f.model.triangles, sculptPerson(dressed).triangles);
  // behind the stall, facing out over it
  assert.ok(f.pos.distanceTo(new Vector3(4, 0, 2 - 2.45)) < 1e-9);
  visit.dispose();
});

test('someone the avatar kit draws stands as tall as their card, hat and all', () => {
  const f = avatarRound(makeWorld(), { ...DEFAULT_AVATAR, hat: 'canotier' }, { key: 'passant:9', height: 1.8 }, 5);
  // the card is printed to the top of the hat; the body is scaled to that, within limits
  const top = f.model.mesh.geometry.boundingBox.max.y * f.model.mesh.scale.y;
  assert.ok(Math.abs(top - 1.8) < 0.05, `stands ${top.toFixed(2)} m tall against 1.8`);
  assert.equal(f.model.print.cell, 160);
  f.dispose();
});

test('across the square someone of the street changes into a lighter body on the same bones, and back', () => {
  const f = avatarRound(makeWorld(), passerbyAvatar(1789), { key: 'passant:0', height: 1.72 }, 1789, 128);
  const { mesh, far } = f.model;
  assert.ok(far, 'the passer-by has no far body');
  // the same bones and print, culled the same way, on not half the triangles, and sound
  assert.equal(far.skeleton, mesh.skeleton);
  assert.equal(far.material, mesh.material);
  assert.ok(far.frustumCulled && far.boundingSphere.equals(mesh.boundingSphere));
  assert.ok(far.scale.equals(mesh.scale));
  const P = f.person;
  const { triangles } = checkBody('passant:0 far off', { ...P, ...P.far }, { min: 1500, max: 5000 });
  assert.ok(triangles < sculptPerson(P).triangles * 0.5, `${triangles} triangles far off against ${sculptPerson(P).triangles} near`);
  // walking away from them and back: near until a little past 30 m, far until a little inside it
  f.place(new Vector3(0, 0, 0));
  const camera = new PerspectiveCamera();
  const from = (z) => {
    camera.position.set(0, 1.6, z);
    f.update(0.016, 1, camera, [1, 1, 1]);
    return mesh.visible === far.visible ? 'both or neither' : mesh.visible ? 'near' : 'far';
  };
  assert.deepEqual([5, 29, 31, 33, 31, 29, 27, 5].map(from), ['near', 'near', 'near', 'far', 'far', 'far', 'near', 'near']);
  f.dispose();
  // the troupe you talk to are always themselves
  PEOPLE.forEach((p) => assert.equal(p.far, undefined, `${p.key} has a far body`));
});
