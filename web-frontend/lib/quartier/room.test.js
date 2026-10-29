// node --test lib/quartier/room.test.js
//
// Le Quartier · the rooms of the season, written from the canon. A room file is drafted by
// `scripts/forge/room.py`, which the app's CI does not run, so these tests build every file in
// `world/rooms` and hold it to the drafter's own checks: you walk in from the street door and up
// the flight to the door the story opens, the push-buttons are in reach and light a circuit that
// goes out, the stage's marks stand where someone can stand, and the door the story opens once
// carries its number. And the map agrees with the files: a room is a locked place inside another
// (Le Mistral's stairwell is in the quai), not a pin of its own, until the story opens it.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..');
const REPO = path.resolve(WEB_ROOT, '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));

const { CardPress, LacePress, Press, seeded } = require('./geo.ts');
const { Nav } = require('./nav.ts');
const { buildRoom, flightPlan } = require('./room.ts');
const { WORLD, mapPlaces } = require('./world.ts');

const ROOMS = path.join(__dirname, 'world', 'rooms');
const files = fs.readdirSync(ROOMS).filter((f) => f.endsWith('.json'));
const rooms = files.map((f) => ({ file: f, room: JSON.parse(fs.readFileSync(path.join(ROOMS, f), 'utf8')) }));

const words = (w) => Boolean(w && w.fr && w.en && w.de);

/** The room as the engine builds it, and its walking grid. */
function build(room) {
  const B = { dry: new Press(), fine: new Press(), wet: new Press(), lace: new LacePress(), glass: new Press(), cards: new CardPress(), signs: [], lamps: [], walk: [], blocks: [], rand: seeded(1102) };
  const built = buildRoom(B, room);
  return { B, built, nav: new Nav(B.walk, B.blocks, built.bounds) };
}

const built = new Map(rooms.map(({ file, room }) => [file, build(room)]));

/** Can you walk from `a` to `b` (and arrive at its height)? */
function reach(nav, a, b) {
  const way = nav.path(a, b);
  if (!way || !way.length) return false;
  const end = way[way.length - 1];
  return Math.hypot(end.x - b.x, end.z - b.z) < 0.8 && Math.abs(nav.heightAt(end.x, end.z) - nav.heightAt(b.x, b.z)) < 0.35;
}

test('there is at least one room, and every room names itself after its file and its canon', () => {
  assert.ok(rooms.length >= 1);
  rooms.forEach(({ file, room }) => {
    assert.equal(`${room.id}.json`, file);
    assert.equal(room.kind, 'room', file);
    assert.equal(room.version, 1, file);
    assert.ok(words(room.title) && words(room.can_do), `${file}: title and can_do in three languages`);
    assert.ok(fs.existsSync(path.join(REPO, room.provenance.canon)), `${file}: no canon file ${room.provenance.canon}`);
    assert.ok(room.provenance.place && room.provenance.scenes.length, `${file}: the place and the scenes it is written from`);
  });
});

test('the map and the files agree: a room is a locked place inside another, never a pin of its own', () => {
  const index = fs.readFileSync(path.join(ROOMS, 'index.ts'), 'utf8');
  const pins = new Set(mapPlaces().map((p) => p.id));
  WORLD.places
    .filter((p) => p.room)
    .forEach((p) => {
      assert.ok(files.indexOf(`${p.room}.json`) >= 0, `${p.id}: no file for room ${p.room}`);
      // the story opens it (the quarter's memory), not the map
      assert.equal(p.status, 'locked', `${p.id}: a room of the season stays locked until the story reaches it`);
      assert.equal(p.site, null, `${p.id}: a room has no site of its own`);
      assert.ok(p.in && WORLD.places.some((q) => q.id === p.in && !q.in), `${p.id}: inside a place on the map`);
      assert.ok(!pins.has(p.id), `${p.id}: a room is not pinned on the map`);
    });
  rooms.forEach(({ room }) => {
    assert.ok(index.indexOf(`  ${room.id}: () => import('./${room.id}.json')`) >= 0, `rooms/index.ts does not load ${room.id}`);
    const place = WORLD.places.find((p) => p.room === room.id);
    assert.ok(place, `${room.id} is not in the world registry`);
    assert.equal(place.in, room.in, `${room.id}: inside ${place.in} on the map, ${room.in} in its file`);
  });
});

test('every flight is a stair you climb: a riser of 14 to 20 cm, a slope under 0.7', () => {
  rooms.forEach(({ file, room }) => {
    room.flights.forEach((F) => {
      const plan = flightPlan(F);
      assert.ok(plan.rise >= 0.14 && plan.rise <= 0.2, `${file}: flight ${F.key} rises ${plan.rise.toFixed(3)} m a step`);
      assert.ok((F.y1 - F.y0) / plan.run < 0.7, `${file}: flight ${F.key} is a ladder`);
    });
  });
});

test('you walk in from the street door, up the flight, to the door the story opens', () => {
  rooms.forEach(({ file, room }) => {
    const { built: r, nav } = built.get(file);
    assert.ok(nav.walkable(r.start.pos.x, r.start.pos.z), `${file}: the start is off the walking grid`);
    // every mark someone stands on is on the ground at its height, and you can walk to it
    Object.entries(r.marks).forEach(([key, m]) => {
      if (!nav.walkable(m.x, m.z)) return;
      const y = nav.heightAt(m.x, m.z);
      if (Math.abs(y - m.y) > 0.3) return;
      assert.ok(reach(nav, r.start.pos, m), `${file}: no way from the street door to the mark ${key}`);
    });
    r.openings
      .filter((o) => o.opens === 'once')
      .forEach((o) => {
        const before = r.marks.door ?? o.front;
        assert.ok(reach(nav, r.start.pos, before), `${file}: no way to the door ${o.key}`);
        assert.ok(Math.abs(nav.heightAt(before.x, before.z) - (o.centre.y - 1.45)) < 0.3, `${file}: you stand before ${o.key} on its floor`);
      });
  });
});

test('the stage has its marks: where the climb ends, before the door, on its threshold, what it shows', () => {
  rooms.forEach(({ file, room }) => {
    const { built: r, nav } = built.get(file);
    if (!r.openings.some((o) => o.opens === 'once')) return;
    ['landing', 'door', 'threshold', 'inside'].forEach((k) => assert.ok(r.marks[k], `${file}: the room director reads the mark ${k}`));
    const { landing, door, threshold, inside } = r.marks;
    // a body fits where the climb ends and before the door, so a walk there ends on the mark (not
    // half a metre off it, looking at the door from the side)
    assert.ok(nav.standable(landing.x, landing.z), `${file}: nobody fits on the landing's mark`);
    assert.ok(nav.standable(door.x, door.z), `${file}: nobody fits on the mark before the door`);
    const o = r.openings.find((x) => x.opens === 'once');
    // the threshold is in the doorway, at the leaf, and what the door shows lies beyond it
    assert.ok(Math.hypot(threshold.x - o.centre.x, threshold.z - o.centre.z) < 0.6, `${file}: the threshold is in the doorway`);
    const away = o.front.clone().sub(o.centre).setY(0).normalize();
    assert.ok(inside.clone().sub(o.centre).dot(away) < -0.5, `${file}: what the door shows is beyond it`);
    const sealed = room.floors.filter((f) => f.zone === 'sealed');
    assert.ok(sealed.length, `${file}: the door opens onto a room not entered yet`);
  });
});

test('the light: every circuit has a push-button in reach and a timer, and every button lights a lamp', () => {
  rooms.forEach(({ file, room }) => {
    const { nav } = built.get(file);
    const circuits = new Set(room.lights.map((l) => l.circuit).filter(Boolean));
    const buttons = new Set(room.switches.map((s) => s.circuit));
    circuits.forEach((c) => {
      assert.ok(buttons.has(c), `${file}: no push-button lights ${c}`);
      assert.ok(room.timers[c] > 0, `${file}: ${c} never goes out`);
    });
    buttons.forEach((c) => assert.ok(circuits.has(c), `${file}: the buttons of ${c} light nothing`));
    room.switches.forEach((s) => {
      const x = s.at[0] + s.facing[0] * 0.55;
      const z = s.at[2] + s.facing[1] * 0.55;
      assert.ok(nav.walkable(x, z), `${file}: nobody can stand before ${s.key}`);
      const h = s.at[1] - nav.heightAt(x, z);
      assert.ok(h >= 1.0 && h <= 1.7, `${file}: ${s.key} is ${h.toFixed(2)} m above the floor`);
    });
  });
});

test('the door the story opens once carries its brass number, and every opening stands in its wall', () => {
  rooms.forEach(({ file, room }) => {
    room.doors.forEach((d) => {
      assert.ok(['never', 'once'].indexOf(d.opens ?? 'never') >= 0, `${file}: ${d.key} opens never or once`);
      if (d.opens === 'once') assert.match(d.numeral ?? '', /^\d+$/, `${file}: ${d.key} has its number`);
    });
    [...room.doors, ...room.windows, ...(room.holes ?? [])].forEach((o) => {
      const w = room.walls[o.wall];
      assert.ok(w, `${file}: an opening in no wall`);
      const len = Math.hypot(w.b[0] - w.a[0], w.b[1] - w.a[1]);
      assert.ok(o.u0 >= -0.001 && o.u0 < o.u1 && o.u1 <= len + 0.001, `${file}: ${o.key ?? 'a hole'} runs off its wall`);
    });
  });
});
