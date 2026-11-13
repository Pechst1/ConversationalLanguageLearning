// node --test lib/quartier/room.test.js
//
// Le Quartier · the rooms of the season, written from the canon. A room file is drafted by
// `scripts/forge/room.py`, which the app's CI does not run, so these tests build every file in
// `world/rooms` and hold it to the drafter's own checks: you walk in from the street door and up
// the flight to the door the story opens, the push-buttons are in reach and light a circuit that
// goes out, the stage's marks stand where someone can stand, and the door the story opens once
// carries its number; what you can tap says what it is, and you can walk up to it. And the map agrees with the files: a room is a locked place inside another
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

/**
 * Can you get from `a` to `b` in a room, on its walking grid and along its passages (the climb past
 * a storey the grid cannot hold, a door into the flat), either way?
 */
function reachIn(room, nav, a, b) {
  const V = a.constructor;
  const seen = [a];
  const queue = [a];
  while (queue.length) {
    const at = queue.shift();
    if (reach(nav, at, b)) return true;
    for (const p of room.passages ?? []) {
      for (const [x, y] of [[p.a, p.b], [p.b, p.a]]) {
        const there = new V(y[0], nav.heightAt(y[0], y[1]), y[1]);
        if (seen.some((s) => Math.hypot(s.x - there.x, s.z - there.z) < 0.01)) continue;
        if (reach(nav, at, new V(x[0], nav.heightAt(x[0], x[1]), x[1]))) {
          seen.push(there);
          queue.push(there);
        }
      }
    }
  }
  return false;
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
      assert.ok(reachIn(room, nav, r.start.pos, m), `${file}: no way from the street door to the mark ${key}`);
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

test('what you can tap says what it is in three languages, and you can walk up to it', () => {
  rooms.forEach(({ file, room }) => {
    const { built: r, nav } = built.get(file);
    if (room.arrive) assert.ok(words(room.arrive), `${file}: the arrival's caption in three languages`);
    room.things.forEach((t) => {
      if (t.did) assert.ok(t.look, `${file}: ${t.kind} is remembered but cannot be tapped`);
      if (!t.look) return;
      assert.ok(words(t.look) && (!t.did || words(t.did)), `${file}: ${t.kind} says itself in three languages`);
      // somewhere within arm's length and a step of it you can stand, and walk to from the door
      let near = null;
      for (let a = 0; a < 16 && !near; a++) {
        for (const d of [0.4, 0.6, 0.8, 1.0, 1.2]) {
          const p = { x: t.at[0] + Math.sin((a * Math.PI) / 8) * d, z: t.at[2] + Math.cos((a * Math.PI) / 8) * d };
          if (nav.walkable(p.x, p.z)) {
            near = new r.start.pos.constructor(p.x, nav.heightAt(p.x, p.z), p.z);
            break;
          }
        }
      }
      assert.ok(near && reachIn(room, nav, r.start.pos, near), `${file}: nobody can walk up to the ${t.kind}`);
    });
  });
});

test('every room is the stage of a place of the season, so a page set there finds it (world.json «stages»)', () => {
  const { stageOf } = require('./world.ts');
  const { roomOf } = require('./story.ts');
  const season = fs.readFileSync(path.join(WEB_ROOT, '..', 'app/services/season/world.py'), 'utf8');
  const known = new Set(Array.from(season.matchAll(/^    "([a-z_]+)": \{"name_fr"/gm), (m) => m[1]));
  assert.ok(known.size > 15);
  for (const file of files) {
    const id = file.replace(/\.json$/, '');
    const entry = WORLD.places.find((p) => p.room === id);
    assert.ok(entry, `${id} has no world entry`);
    assert.ok((entry.stages ?? []).length, `${id}: world.json gives it no «stages», so no page ever plays there`);
    for (const loc of [...entry.stages, ...(entry.sees ?? [])]) assert.ok(known.has(loc), `${id}: «${loc}» is not a place of the season`);
    for (const loc of entry.stages) {
      assert.equal(stageOf(loc)?.room, id, `${loc} does not play in ${id}`);
      assert.equal(roomOf({ kind: 'panel', id: 'x', lines: [], location_id: loc }), id);
    }
  }
  // the café and the quai are the hand-drawn quarter; a place nothing is built for has no stage yet
  assert.equal(stageOf('le_mistral')?.id, 'quai_de_valmy');
  assert.equal(stageOf('le_mistral')?.room ?? null, null);
  assert.equal(stageOf('mistral_back_room')?.room, 'arriere_salle');
  assert.equal(stageOf('marin_lila_flat')?.room, 'chez_marin_lila');
  assert.equal(stageOf('marchand_office')?.room, 'gerance_marchand');
  assert.equal(stageOf('gare_de_lest'), null);
});

test('Marin and Lila’s flat (T5, B without the key): the crate in the hallway, the card under the sardine, the canvas half wrapped', () => {
  const file = 'chez_marin_lila.json';
  const flat = rooms.find((r) => r.file === file);
  assert.ok(flat, 'the flat is built');
  const { room } = flat;
  const of = (kind) => room.things.find((t) => t.kind === kind);
  for (const k of ['crate', 'fridge', 'easel', 'canvas', 'kitchenette']) assert.ok(of(k), `the flat has no ${k}`);
  // the stencil P3 reads, and the card P4 reads: to Toi, its last line not finished
  assert.deepEqual(of('crate').text, ['FRAGILE', 'BERLIN', 'KÜNSTLERHAUS AM KANAL']);
  const [label, ...card] = of('fridge').text;
  assert.equal(label, 'LE MISTRAL À NOUS');
  assert.equal(card[0], 'À toi —');
  assert.match(card[card.length - 1], /Berlin.* et je$/);
  // the easel stands empty: its canvas is the one leaning on the wall, face to it
  assert.deepEqual(of('easel').size, [0, 0]);
  // on the third floor, its windows on the canal; you arrive in the hallway, by the crate (the
  // building's letterboxes are in its vestibule, on the ground floor)
  assert.ok(room.things.filter((t) => t.kind !== 'letterboxes').every((t) => t.at[1] >= 11.2 - 0.001));
  assert.ok(room.things.some((t) => t.kind === 'letterboxes' && t.text.some((l) => /Lévêque/.test(l) && /Bonnet/.test(l))), 'their names on the letterbox');
  assert.ok(room.canals?.length && room.windows.length >= 2);
  const { built: r } = built.get(file);
  assert.equal(r.inside(r.start.pos.x, r.start.pos.z), true);
  assert.ok(Math.hypot(r.start.pos.x - of('crate').at[0], r.start.pos.z - of('crate').at[2]) < 1.6, 'the crate is the first thing you see');
});

test('the gérance Marchand (T6 A): the key boards, the camp bed among the files, the Polaroid on the desk under one lamp', () => {
  const file = 'gerance_marchand.json';
  const office = rooms.find((r) => r.file === file);
  assert.ok(office, 'the gérance is built');
  const { room } = office;
  const all = (kind) => room.things.filter((t) => t.kind === kind);
  for (const k of ['keyboard', 'cabinet', 'desk', 'campbed', 'frame', 'armchair', 'chair']) assert.ok(all(k).length, `the gérance has no ${k}`);
  // walls of keys, filing cabinets, and the only chair for a visitor (P2)
  assert.ok(all('keyboard').length >= 4 && all('cabinet').length >= 2);
  assert.equal(all('chair').length, 1);
  // the Polaroid P3 reads, on the desk; the other frame is the portrait, without a caption
  const [polaroid, ...others] = all('frame').sort((a, b) => (b.text?.length ?? 0) - (a.text?.length ?? 0));
  assert.deepEqual(polaroid.text, ['Dimanche. M. rit. Enfin.']);
  assert.ok(others.every((f) => !f.text?.length));
  const desk = all('desk')[0];
  assert.ok(Math.abs(polaroid.at[1] - (desk.at[1] + 0.76)) < 0.01 && Math.hypot(polaroid.at[0] - desk.at[0], polaroid.at[2] - desk.at[2]) < 0.8);
  // «cold ink and grey, with one warm lamp»: the desk lamp is the room's only light
  assert.deepEqual(room.lights.map((l) => l.kind), ['desk']);
  // on the second floor, over the quai; you arrive at the landing's door and the camp bed is before you
  assert.ok(room.things.every((t) => t.at[1] >= 7.9 - 0.001));
  assert.ok(room.canals?.length && room.windows.length >= 2);
  const { built: r } = built.get(file);
  assert.equal(r.inside(r.start.pos.x, r.start.pos.z), true);
  const bed = all('campbed')[0];
  assert.ok(Math.hypot(r.start.pos.x - bed.at[0], r.start.pos.z - bed.at[2]) < 4.5, 'the camp bed is in sight from the door');
});

test('the back room (T5 B): the easel under its sheet, the board, the new plaster, and Marin’s plan by the door', () => {
  const file = 'arriere_salle.json';
  const back = rooms.find((r) => r.file === file);
  assert.ok(back, 'the back room is built');
  const { room } = back;
  const kinds = room.things.map((t) => t.kind);
  for (const k of ['easel', 'board', 'patch', 'crates', 'plan']) assert.ok(kinds.includes(k), `the back room has no ${k}`);
  // the plan's square says what P9 reads on it, and it hangs by the door the café is through
  const plan = room.things.find((t) => t.kind === 'plan');
  assert.ok(plan.text.includes('ATELIER DE LILA'));
  const door = room.doors[0];
  const wall = room.walls[door.wall];
  assert.ok(Math.abs(plan.at[0] - wall.a[0]) < 0.05, 'the plan is on the wall of the door');
  // the door into the café is where the café's own back door is (mistral.ts: x -37.6, z -18.1)
  const len = Math.hypot(wall.b[0] - wall.a[0], wall.b[1] - wall.a[1]);
  const mid = wall.a[1] + ((wall.b[1] - wall.a[1]) * (door.u0 + door.u1)) / 2 / len;
  assert.ok(Math.abs(wall.a[0] - -37.6) < 0.01 && Math.abs(mid - -18.1) < 0.05);
  // you arrive in it, indoors, the café's door behind you
  const { built: r } = built.get(file);
  assert.equal(r.inside(r.start.pos.x, r.start.pos.z), true);
});

test("a room in the quarter (the roof) lies on Le Mistral's roof, and you walk round its chimneys", () => {
  // a room on a roof: its ground is high above the street (a street of the quai is the next test's)
  const roofs = rooms.filter(({ room }) => room.quarter && room.floors.every((f) => f.y > 5));
  if (!roofs.length) return;
  const { buildQuai } = require('./quai.ts');
  const B = { dry: new Press(), fine: new Press(), wet: new Press(), lace: new LacePress(), glass: new Press(), cards: new CardPress(), signs: [], lamps: [], walk: [], blocks: [], rand: seeded(1102) };
  const { mistral } = buildQuai(B);
  const inside = (shape, x, z) => {
    let c = false;
    for (let i = 0, j = shape.length - 1; i < shape.length; j = i++) {
      const [ax, az] = shape[j];
      const [bx, bz] = shape[i];
      if (az > z !== bz > z && x < ((bx - ax) * (z - az)) / (bz - az) + ax) c = !c;
    }
    return c;
  };
  assert.ok(mistral.stacks.length >= 2, "Le Mistral's building has its chimney stacks");
  roofs.forEach(({ file, room }) => {
    room.floors.forEach((f) => {
      // the flat of the roof is the top of the mansard (its terrasson), inside the building's walls
      assert.ok(Math.abs(f.y - (mistral.ridge + 0.12)) < 0.05, `${file}: ${f.key} at ${f.y} m, the roof's flat is at ${(mistral.ridge + 0.12).toFixed(2)}`);
      f.shape.forEach(([x, z]) => assert.ok(inside(mistral.footprint, x - Math.sign(x + 40) * 0.01, z - Math.sign(z + 17) * 0.01), `${file}: ${f.key} reaches (${x}, ${z}), off the building`));
    });
    // the start, the marks and the things you tap stand clear of the building's own chimneys
    const { built: r } = built.get(file);
    const clear = (x, z, what) => mistral.stacks.forEach((s) => assert.ok(!inside(s, x, z), `${file}: ${what} stands in a chimney`));
    clear(r.start.pos.x, r.start.pos.z, 'the start');
    // a roof is out of doors: the camera sees as far as the night, the lamps glint
    assert.equal(r.inside(r.start.pos.x, r.start.pos.z), false, `${file}: the roof counts as indoors`);
    Object.entries(r.marks).forEach(([k, m]) => clear(m.x, m.z, `the mark ${k}`));
    room.things.forEach((t) => clear(t.at[0], t.at[2], `the ${t.kind}`));
  });
});

test('a room in a street of the quarter (the rue de Lancry) walks the ground the quai lays, and draws none of its own', () => {
  const streets = rooms.filter(({ room }) => room.quarter && room.floors.some((f) => f.y <= 5));
  if (!streets.length) return;
  const { buildQuai } = require('./quai.ts');
  const B = { dry: new Press(), fine: new Press(), wet: new Press(), lace: new LacePress(), glass: new Press(), cards: new CardPress(), signs: [], lamps: [], walk: [], blocks: [], rand: seeded(1102) };
  const quai = buildQuai(B);
  const inside = (shape, x, z) => {
    let c = false;
    for (let i = 0, j = shape.length - 1; i < shape.length; j = i++) {
      const [ax, az] = shape[j];
      const [bx, bz] = shape[i];
      if (az > z !== bz > z && x < ((bx - ax) * (z - az)) / (bz - az) + ax) c = !c;
    }
    return c;
  };
  // a point of the quai's own walked ground at that height (a pavement at the kerb, the road at 0)
  const onQuai = (x, z, y) => B.walk.some((w) => Math.abs(w.y - y) < 0.02 && inside(w.shape, x, z));
  streets.forEach(({ file, room }) => {
    room.floors.forEach((f) => {
      assert.ok(f.y <= 5, `${file}: ${f.key} is a street's and a roof's at once`);
      assert.equal(f.drawn, false, `${file}: ${f.key} lays the street over the quai's own`);
      const [cx, cz] = f.shape.reduce(([sx, sz], [x, z]) => [sx + x / f.shape.length, sz + z / f.shape.length], [0, 0]);
      f.shape.forEach(([x, z]) => {
        const px = x + (cx - x) * 0.02;
        const pz = z + (cz - z) * 0.02;
        assert.ok(onQuai(px, pz, f.y), `${file}: ${f.key} reaches (${x}, ${z}), off the quai's ground at ${f.y} m`);
      });
    });
    const { built: r } = built.get(file);
    // a street is out of doors, and «L.»'s window is there to look up at
    assert.equal(r.inside(r.start.pos.x, r.start.pos.z), false, `${file}: the street counts as indoors`);
    assert.ok(quai.easel, 'the quai has «L.»\'s window');
    const gaze = room.things.find((t) => t.kind === 'gaze');
    if (gaze) assert.ok(Math.hypot(gaze.at[0] - quai.easel.center.x, gaze.at[1] - quai.easel.center.y, gaze.at[2] - quai.easel.center.z) < 0.5, `${file}: what you look up at is not «L.»'s window`);
  });
});
