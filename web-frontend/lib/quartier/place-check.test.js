// node --test lib/quartier/place-check.test.js
//
// P12 stage 6 · a place is finished, or it is not served (owner rule of 13 Nov 2026, made
// testable). Observed 17 Nov: the stairwell of «Là-haut» (T2 day a) opened on a blank wall over a
// tilted floor with one light switch. This is a check over the data, not a redesign: for every
// place the quarter builds (the hand-drawn quai and Le Mistral, each room of the season, each site
// the forge surveyed) it asserts what the files can say:
//
// - it has ground to walk (a floor), and a room has the walls its bounds imply (a wall along each
//   side of its walkable floors' box);
// - you start on that ground;
// - the camera's first target is over the place, on the storey you stand on (not behind a wall, in
//   the void under a landing);
// - every mark where the stage stands someone, or that the camera looks at, is over the place's
//   ground (within a doorway's 0.35 m), at a height a person or a look can have there.
//
// A place that fails is marked `unfinished` in the register (`world/world.json`, with the reason):
// it stages nothing (`stageOf`), so a day set there is the Feuilleton's page and Home offers no
// «Jouer dans le Quartier» for it, until the nightly «Quartier forge» finishes it. A place marked
// unfinished that passes must lose the mark (the list only shrinks). Every day of the season the
// quarter can stage, and every `STAGED_DAYS` day, plays only in places that pass.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..');
const REPO = path.resolve(WEB_ROOT, '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
const resolve = Module._resolveFilename;
Module._resolveFilename = function alias(request, ...rest) {
  if (typeof request === 'string' && request.startsWith('@/')) return resolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  return resolve.call(this, request, ...rest);
};
// the axios transport is never reached here (`todayOf`, `quartierCanStage` read a snapshot)
const apiPath = Module._resolveFilename('@/services/api', module, false);
require.cache[apiPath] = { id: apiPath, filename: apiPath, loaded: true, exports: { __esModule: true, default: {}, apiService: {} } };

const { CardPress, LacePress, Press, seeded } = require('./geo.ts');
const { Nav } = require('./nav.ts');
const { PLAN, buildQuai } = require('./quai.ts');
const { MARKS, ROOM, buildMistral } = require('./mistral.ts');
const { buildRoom, flightPlan } = require('./room.ts');
const { HOME_PLACE, WORLD, stageOf } = require('./world.ts');
const { STAGED_DAYS } = require('./story.ts');

const ROOMS = path.join(__dirname, 'world', 'rooms');
const SITES = path.join(__dirname, 'world', 'sites');
const read = (file) => JSON.parse(fs.readFileSync(file, 'utf8'));

/* ---- geometry read off the files (nothing modelled here) ------------------------------------- */

function inRing(x, z, ring) {
  let c = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, zi] = ring[i];
    const [xj, zj] = ring[j];
    if (zi > z !== zj > z && x < ((xj - xi) * (z - zi)) / (zj - zi) + xi) c = !c;
  }
  return c;
}

/** (x, z) and the points around it within `r` (a doorway, a mark on a threshold). */
function around(x, z, r = 0.35) {
  const out = [[x, z]];
  for (let a = 0; a < 8; a++) out.push([x + r * Math.cos((a * Math.PI) / 4), z + r * Math.sin((a * Math.PI) / 4)]);
  return out;
}

const press = () => ({ dry: new Press(), fine: new Press(), wet: new Press(), lace: new LacePress(), glass: new Press(), cards: new CardPress(), signs: [], lamps: [], walk: [], blocks: [], rand: seeded(1102) });

/** A room's grounds: its floors (every zone: what you see is the place too) and its flights. */
function groundsOf(spec) {
  return [
    ...spec.floors.map((f) => ({ key: f.key, shape: f.shape, y0: f.y, y1: f.y, walk: (f.zone ?? 'room') === 'room' && f.walk !== false })),
    ...spec.flights.map((F) => ({ key: F.key, shape: flightPlan(F).shape, y0: Math.min(F.y0, F.y1), y1: Math.max(F.y0, F.y1), walk: true })),
  ];
}

/** Is the point over the room's ground, on its storey (from its floor to a storey's height above)? */
function overGround(spec, nav, [x, y, z], headroom = 3.2) {
  const near = around(x, z);
  if (groundsOf(spec).some((g) => near.some(([a, b]) => inRing(a, b, g.shape)) && y >= g.y0 - 0.25 && y <= g.y1 + headroom)) return true;
  // a room in the quarter's own streets walks the quai's ground
  return near.some(([a, b]) => nav.walkable(a, b) && y >= nav.heightAt(a, b) - 0.25 && y <= nav.heightAt(a, b) + headroom);
}

/* ---- the check ---------------------------------------------------------------------------- */

function roomProblems(id) {
  const spec = read(path.join(ROOMS, `${id}.json`));
  const B = press();
  if (spec.quarter) {
    buildQuai(B);
    B.walk.length = 0;
    B.blocks.length = 0;
  }
  const built = buildRoom(B, spec);
  const nav = new Nav(B.walk, B.blocks, built.bounds);
  const out = [];
  const walkable = groundsOf(spec).filter((g) => g.walk);
  if (!walkable.length && !spec.quarter) out.push('no floor to walk');
  // the walls its bounds imply: one along each side of the box of its walkable floors (a room in the street has none)
  if (!spec.quarter && walkable.length) {
    const xs = walkable.flatMap((g) => g.shape.map((p) => p[0]));
    const zs = walkable.flatMap((g) => g.shape.map((p) => p[1]));
    const box = { x0: Math.min(...xs), x1: Math.max(...xs), z0: Math.min(...zs), z1: Math.max(...zs) };
    const along = (axis, at) => spec.walls.some((w) => Math.abs(w.a[axis] - at) < 0.15 && Math.abs(w.b[axis] - at) < 0.15);
    for (const [side, axis, at] of [['west', 0, box.x0], ['east', 0, box.x1], ['north', 1, box.z0], ['south', 1, box.z1]]) {
      if (!along(axis, at)) out.push(`no wall on its ${side} side (${axis ? 'z' : 'x'} = ${at})`);
    }
  }
  const [sx, sz] = spec.start.pos;
  if (!nav.walkable(sx, sz)) out.push(`you start off the ground, at ${JSON.stringify(spec.start.pos)}`);
  // under the sky (a room in the quarter's own streets, the roof) the camera may look out: inside the place, or over the quai and its canal
  const b = built.bounds;
  const [lx, , lz] = spec.start.look;
  const inQuai = lx >= PLAN.valmy.face && lx <= PLAN.jemmapes.face && lz >= PLAN.zMin && lz <= PLAN.zMax;
  const lookIn = spec.quarter ? (lx >= b.x0 && lx <= b.x1 && lz >= b.z0 && lz <= b.z1) || inQuai : overGround(spec, nav, spec.start.look);
  if (!lookIn) {
    out.push(`the camera's first target ${JSON.stringify(spec.start.look)} is over no ground of the storey you stand on: you face a wall`);
  }
  Object.entries(spec.marks).forEach(([key, m]) => {
    if (!overGround(spec, nav, m)) out.push(`the mark «${key}» ${JSON.stringify(m)} is over no ground of the place`);
  });
  return out;
}

function siteProblems(id) {
  const site = read(path.join(SITES, `${id}.json`));
  const onWalk = ([x, z]) => site.walk.some((p) => inRing(x, z, p.outer) && !(p.holes ?? []).some((h) => inRing(x, z, h)));
  const out = [];
  if (!site.walk.length || !site.walk.some((p) => p.outer.length >= 3)) out.push('no ground to walk');
  if (!onWalk(site.start.pos)) out.push(`you start off the ground, at ${JSON.stringify(site.start.pos)}`);
  const [lx, , lz] = site.start.look;
  if (Math.hypot(lx - site.start.pos[0], lz - site.start.pos[1]) > site.radius.build) out.push('the camera’s first target is outside the place');
  (site.people ?? []).forEach((p) => {
    if (p.pos && !around(p.pos[0], p.pos[1], 0.5).some(onWalk)) out.push(`${p.key} stands off the ground`);
  });
  return out;
}

let home = null;
function homeProblems() {
  if (home) return home;
  const B = press();
  const quai = buildQuai(B);
  buildMistral(B, quai.mistral);
  const nav = new Nav(B.walk, B.blocks, { x0: -182, z0: -212, x1: 32, z1: 212 });
  const inCafe = (m) => m.x >= ROOM.x0 && m.x <= ROOM.x1 && m.z >= ROOM.z0 && m.z <= ROOM.z1 && m.y >= ROOM.floor - 0.05 && m.y <= ROOM.ceiling;
  const out = [];
  if (!nav.walkable(PLAN.start.pos.x, PLAN.start.pos.z)) out.push('you start off the quai');
  Object.entries(MARKS).forEach(([key, m]) => {
    if (!inCafe(m) && !around(m.x, m.z, 0.5).some(([x, z]) => nav.walkable(x, z))) out.push(`the mark «${key}» is neither in the café nor on the quai`);
  });
  home = out;
  return out;
}

/** What keeps a place of the register from being finished, if anything. */
function placeProblems(place) {
  if (place.id === HOME_PLACE) return homeProblems();
  if (place.room) return roomProblems(place.room);
  if (place.site) return siteProblems(place.site);
  return [];
}

const builtPlaces = () => WORLD.places.filter((p) => p.kind === 'home' || p.room || p.site);

/** Every place of the season a day is set at, or moves to (`location_id` anywhere in its page). */
function seasonDays() {
  const dir = path.join(REPO, 'app', 'data', 'season', 's1');
  const out = [];
  for (const file of fs.readdirSync(dir).filter((f) => /^t\d+\.json$/.test(f))) {
    const tentpole = read(path.join(dir, file));
    for (const day of tentpole.days ?? []) {
      const locations = new Set();
      const scan = (x) => {
        if (Array.isArray(x)) x.forEach(scan);
        else if (x && typeof x === 'object') Object.entries(x).forEach(([k, v]) => (k === 'location_id' && typeof v === 'string' ? locations.add(v) : scan(v)));
      };
      scan(day);
      out.push({ key: `${tentpole.id}.${day.day}`, title: day.title_fr, locations: [...locations] });
    }
  }
  return out;
}

/* ---- the tests ---------------------------------------------------------------------------- */

test('every built place is finished, or marked unfinished in the register with the reason', () => {
  const failing = [];
  for (const place of builtPlaces()) {
    const problems = placeProblems(place);
    if (problems.length && !place.unfinished) failing.push(`${place.id}: ${problems.join('; ')}`);
  }
  assert.deepEqual(failing, [], `a place that fails the check is marked «unfinished» in world/world.json:\n${failing.join('\n')}`);
});

test('a place marked unfinished still fails the check (the list only shrinks), and says why', () => {
  for (const place of WORLD.places.filter((p) => p.unfinished)) {
    assert.ok(typeof place.unfinished === 'string' && place.unfinished.length > 20, `${place.id}: the reason, for the forge`);
    assert.ok(placeProblems(place).length, `${place.id} passes the check now: take its «unfinished» off`);
  }
});

test('«Là-haut» (T2 day a): the stairwell fails the check, so the day is the page’s, and Home offers no Quartier', () => {
  const problems = roomProblems('escalier_mistral');
  assert.ok(problems.some((p) => /camera's first target/.test(p)), problems.join('; '));
  assert.equal(stageOf('stairwell'), null, 'an unfinished place stages nothing');
  const { quartierCanStage } = require('./home-door.ts');
  assert.equal(quartierCanStage({ kind: 'offer', scenario: { location_id: 'stairwell' } }, true), false);
  assert.equal(quartierCanStage({ kind: 'offer', scenario: { location_id: 'le_mistral' } }, true), true);
});

test('every day the quarter stages plays only in finished places (STAGED_DAYS too)', () => {
  const offered = [];
  for (const day of seasonDays()) {
    const places = day.locations.map((l) => stageOf(l));
    // a day with a place nothing (finished) stages is the Feuilleton's: not the quarter's to play
    if (places.some((p) => !p)) continue;
    offered.push(day.key);
    for (const p of places) assert.deepEqual(placeProblems(p), [], `${day.key} «${day.title}» plays in ${p.id}`);
  }
  assert.ok(offered.includes('t1.a'), 'T1 day a, the first episode, is still the quarter’s');
  assert.ok(!offered.includes('t2.a'), '«Là-haut» goes to the stairwell');
  for (const key of STAGED_DAYS) {
    const day = seasonDays().find((d) => d.key === key);
    assert.ok(day, key);
  }
});

test('a staged day that goes to an unfinished place falls back to the page', () => {
  const { todayOf } = require('./journey-story.ts');
  const journey = (key, location) => ({
    id: 'j',
    status: 'active',
    revision: 1,
    edition_no: 9,
    steps: [
      {
        id: 'scene',
        kind: 'scene',
        status: 'active',
        ordinal: 1,
        prompt: {
          stage: {
            season_id: 's1',
            segment: key.split('.')[0],
            day: key.split('.')[1],
            key,
            number: 2,
            title_fr: 'x',
            location_id: location,
            movements: [{ kind: 'panel', id: `${key[3]}.p1`, location_id: location, lines: [] }],
            storylets: [],
          },
        },
      },
    ],
    current_step_id: 'scene',
  });
  const t1b = todayOf(journey('t1.b', 'stairwell'));
  assert.equal(t1b.kind, 'handoff', 'T1 day b climbs the stairwell: the page tells it');
  assert.equal(t1b.place, 'stairwell');
  assert.equal(todayOf(journey('t2.a', 'stairwell')).kind, 'handoff');
});
