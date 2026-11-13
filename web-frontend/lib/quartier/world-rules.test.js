// node --test lib/quartier/world-rules.test.js
//
// Le Quartier · the two rules every place of the world keeps (owner, 13 Nov 2026), held over the
// register (`world/world.json`) and the built places:
//
// 1. On foot. A built place the story uses is entered on foot from the walkable quarter: its
//    `entrance` is a door on ground you walk in the place it is entered from (a flat through its
//    building's street door and up its stairwell), and from just inside that door the place's own
//    ground leads to everything the story stands people at and everything you can tap (its walking
//    grid, and its `passages` where the grid cannot go). A new place without one fails here.
// 2. On the map. A place gets a pin of its own only `MAP_PIN_MIN_METRES` or more from every other
//    pin; a place nearer to a pin than that is inside it (`in`) and reached through it.
//
// The nightly forge runs the same rules (`scripts/forge/forge.py check`), and its PRs run these.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..');
const REPO = path.resolve(WEB_ROOT, '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));

const { Vector3 } = require('three');
const { CardPress, LacePress, Press, seeded } = require('./geo.ts');
const { Nav } = require('./nav.ts');
const { buildQuai } = require('./quai.ts');
const { buildMistral } = require('./mistral.ts');
const { buildRoom } = require('./room.ts');
const { HOME_PLACE, MAP_PIN_MIN_METRES, WORLD, doorsAt, mapPlaces, metresBetween, playedHere } = require('./world.ts');

const ROOMS = path.join(__dirname, 'world', 'rooms');
const roomFile = (id) => JSON.parse(fs.readFileSync(path.join(ROOMS, `${id}.json`), 'utf8'));

/**
 * The places built before the rule that are not walked into yet, and why. The list only shrinks:
 * a place given its door leaves it (the test below says so), and no place is ever added to it. The
 * forge keeps the same list (`WAITS_FOR_A_WAY` in scripts/forge/forge.py).
 */
const WAITS_FOR_A_WAY = {
  escalier_mistral: 'its door with the «1» opens once in T1 R2: on foot it would play the scene out of turn',
  user_apartment: 'the sixth floor: Le Mistral’s stairs stop at the first',
  notaire: 'the boulevard by the mairie is not built',
  odile_flat: 'behind the door the story opens in T2',
  toit_mistral: 'through the fifth floor’s skylight: the stairs stop at the first',
  arriere_salle: 'through Le Mistral’s back door, which the café’s plan does not open yet',
  gerance_marchand: 'the second floor over Le Mistral: the stairs stop at the first',
  rue_de_lancry: 'the quai already lays this street; its room is the story’s staging of it',
};

const pins = () => WORLD.places.filter((p) => !p.in);
const builtInside = () => WORLD.places.filter((p) => p.in && (p.room || p.site));

/* ---- the walking grids ---------------------------------------------------------------------- */

const press = () => ({ dry: new Press(), fine: new Press(), wet: new Press(), lace: new LacePress(), glass: new Press(), cards: new CardPress(), signs: [], lamps: [], walk: [], blocks: [], rand: seeded(1102) });
const grids = new Map();

/** The walking grid of a place: the quai as the engine builds it, or a room's. */
function gridOf(id) {
  if (grids.has(id)) return grids.get(id);
  let g = null;
  if (id === HOME_PLACE) {
    const B = press();
    const quai = buildQuai(B);
    buildMistral(B, quai.mistral);
    g = { nav: new Nav(B.walk, B.blocks, { x0: -182, z0: -212, x1: 32, z1: 212 }), passages: [] };
  } else {
    const place = WORLD.places.find((p) => p.id === id);
    if (place?.room) {
      const spec = roomFile(place.room);
      const B = press();
      if (spec.quarter) {
        buildQuai(B);
        B.walk.length = 0;
        B.blocks.length = 0;
      }
      const built = buildRoom(B, spec);
      g = { nav: new Nav(B.walk, B.blocks, built.bounds), built, spec, passages: spec.passages ?? [] };
    }
  }
  grids.set(id, g);
  return g;
}

const v = (x, z) => new Vector3(x, 0, z);

/** Can you walk from a to b on this grid (arriving at b's height)? */
function walk(nav, a, b) {
  if (!nav.walkable(a.x, a.z) || !nav.walkable(b.x, b.z)) return false;
  if (Math.hypot(a.x - b.x, a.z - b.z) < 0.3) return true;
  const way = nav.path(a, b);
  if (!way || !way.length) return false;
  const end = way[way.length - 1];
  return Math.hypot(end.x - b.x, end.z - b.z) < 0.8 && Math.abs(nav.heightAt(end.x, end.z) - nav.heightAt(b.x, b.z)) < 0.35;
}

/** Everywhere you reach from `from` on a place's grid, its passages taken both ways: a test for each point. */
function reachable(g, from) {
  const ends = g.passages.flatMap((p) => [v(...p.a), v(...p.b)]);
  const seen = [from];
  const queue = [from];
  while (queue.length) {
    const at = queue.shift();
    g.passages.forEach((p) => {
      for (const [x, y] of [[p.a, p.b], [p.b, p.a]]) {
        const there = v(...y);
        if (seen.some((s) => s.distanceTo(there) < 0.01)) continue;
        if (walk(g.nav, at, v(...x))) {
          seen.push(there);
          queue.push(there);
        }
      }
    });
  }
  void ends;
  return (b) => seen.some((s) => walk(g.nav, s, b));
}

/* ---- the rules, as functions the tests below hold the register to --------------------------- */

/** What breaks the rule «on foot» for a place, if anything. */
function onFootProblems(place, world = WORLD) {
  const e = place.entrance;
  if (!e) return WAITS_FOR_A_WAY[place.id] ? [] : [`${place.id}: no entrance: a place the story uses is walked into from the quarter (world.json «entrance»)`];
  const out = [];
  const from = world.places.find((p) => p.id === e.from);
  if (!from) return [`${place.id}: entered from ${e.from}, which is not a place of the world`];
  // the door leads back to a pin on the map, door by door
  let up = from;
  const chain = new Set([place.id]);
  while (up && up.in && !chain.has(up.id)) {
    chain.add(up.id);
    up = up.entrance ? world.places.find((p) => p.id === up.entrance.from) : null;
  }
  if (!up || up.in) out.push(`${place.id}: its doors do not lead back to a place on the map`);
  for (const k of ['enter', 'leave']) if (!(e[k] && e[k].fr && e[k].en && e[k].de)) out.push(`${place.id}: the door's «${k}» in three languages`);
  if (Math.hypot(e.outside[0] - e.door[0], e.outside[1] - e.door[1]) > 2.5 || Math.hypot(e.inside[0] - e.door[0], e.inside[1] - e.door[1]) > 2.5) {
    out.push(`${place.id}: you stand within 2.5 m of the door, outside and inside`);
  }
  const outer = gridOf(e.from);
  if (!outer) out.push(`${place.id}: entered from ${e.from}, which has no walking grid to stand on`);
  else if (!outer.nav.walkable(e.outside[0], e.outside[1])) out.push(`${place.id}: outside its door, ${e.outside}, is not ground you walk in ${e.from}`);
  else if (e.from === HOME_PLACE && !walk(outer.nav, v(-15.6, 17), v(...e.outside))) out.push(`${place.id}: the quai's start does not walk to its door`);
  const inner = gridOf(place.id);
  if (!inner) return out.concat(`${place.id}: nothing built to walk into`);
  if (!inner.nav.walkable(e.inside[0], e.inside[1])) return out.concat(`${place.id}: inside its door, ${e.inside}, is not ground you walk`);
  // from inside the door, everywhere the story stands people and everything you can tap
  const reach = reachable(inner, v(...e.inside));
  if (!reach(inner.built.start.pos)) out.push(`${place.id}: the door does not lead to where the story starts`);
  Object.entries(inner.built.marks).forEach(([key, m]) => {
    if (!inner.nav.walkable(m.x, m.z) || Math.abs(inner.nav.heightAt(m.x, m.z) - m.y) > 0.3) return;
    if (!reach(m)) out.push(`${place.id}: the door does not lead to the mark ${key}`);
  });
  inner.passages.forEach((p) => {
    for (const end of [p.a, p.b]) if (!inner.nav.walkable(end[0], end[1])) out.push(`${place.id}: passage ${p.key} ends off the ground at ${end}`);
  });
  return out;
}

/** What breaks the rule «on the map», if anything. */
function mapProblems(world = WORLD) {
  const out = [];
  const shown = world.places.filter((p) => !p.in);
  shown.forEach((p, i) =>
    shown.slice(i + 1).forEach((q) => {
      const d = metresBetween(p, q);
      if (d < MAP_PIN_MIN_METRES) out.push(`${p.id} and ${q.id} are ${Math.round(d)} m apart: the nearer one is inside the other (\`in\`), not a pin`);
    }),
  );
  world.places
    .filter((p) => p.in)
    .forEach((p) => {
      const host = shown.find((q) => q.id === p.in);
      if (!host) out.push(`${p.id}: inside ${p.in}, which is not a pin on the map`);
      else if (metresBetween(p, host) >= MAP_PIN_MIN_METRES) out.push(`${p.id}: ${Math.round(metresBetween(p, host))} m from ${p.in}, far enough for a pin of its own`);
    });
  return out;
}

/* ---- the tests ------------------------------------------------------------------------------ */

test('on the map: the pins stand far enough apart, and every place inside one is next door to it', () => {
  assert.deepEqual(mapProblems(), []);
  // what the map shows, and what it reaches through a pin (the PR's list)
  const lines = WORLD.places.map((p) => {
    if (!p.in) return `pin   ${p.id}`;
    return `in    ${p.id} → ${p.in} (${Math.round(metresBetween(p, WORLD.places.find((q) => q.id === p.in)))} m)`;
  });
  assert.ok(lines.length > 5, lines.join('\n'));
});

test('the threshold is one constant, the same for the forge', () => {
  assert.equal(MAP_PIN_MIN_METRES, 300);
  const forge = fs.readFileSync(path.join(REPO, 'scripts/forge/forge.py'), 'utf8');
  assert.match(forge, new RegExp(`^MAP_PIN_MIN_METRES = ${MAP_PIN_MIN_METRES}$`, 'm'), 'scripts/forge/forge.py keeps the same MAP_PIN_MIN_METRES');
});

test('Marin and Lila’s flat is no pin: 44 m from the quai, it is reached through it', () => {
  const flat = WORLD.places.find((p) => p.id === 'chez_marin_lila');
  const quai = WORLD.places.find((p) => p.id === HOME_PLACE);
  assert.ok(metresBetween(flat, quai) < MAP_PIN_MIN_METRES);
  assert.equal(flat.in, HOME_PLACE);
  assert.ok(!mapPlaces().some((p) => p.id === 'chez_marin_lila'));
});

test('a new place next door to a pin gets no pin; one far enough away does', () => {
  const quai = WORLD.places.find((p) => p.id === HOME_PLACE);
  const near = { ...quai, id: 'boulangerie_test', in: undefined, lat: quai.lat + 0.001, lon: quai.lon };
  const far = { ...quai, id: 'bastille_test', in: undefined, lat: 48.8532, lon: 2.3692 };
  assert.ok(mapProblems({ ...WORLD, places: [...WORLD.places, near] }).some((m) => m.includes('boulangerie_test')));
  assert.deepEqual(mapProblems({ ...WORLD, places: [...WORLD.places, far] }), []);
  // a place the news names next door to a pin is reached through it too
  const news = [{ id: 'news_quai', name_fr: 'Sur le quai', lat: quai.lat + 0.0005, lon: quai.lon, article: { id: 'a', title_fr: 'x', week: null, topic: null } }];
  assert.ok(!mapPlaces(WORLD, news).some((p) => p.id === 'news_quai'));
  const away = [{ ...news[0], id: 'news_far', lat: 48.8532, lon: 2.3692 }];
  assert.ok(mapPlaces(WORLD, away).some((p) => p.id === 'news_far'));
});

test('on foot: every built place inside a pin is walked into from the quarter, door by door', () => {
  const problems = builtInside().flatMap((p) => onFootProblems(p));
  assert.deepEqual(problems, []);
});

test('the places waiting for their door only shrink: none is added, and one given its door leaves the list', () => {
  const waiting = builtInside().filter((p) => !p.entrance).map((p) => p.id).sort();
  assert.deepEqual(waiting, Object.keys(WAITS_FOR_A_WAY).sort(), 'a place given its door leaves WAITS_FOR_A_WAY (here and in forge.py); a new place comes with its door');
  const forge = fs.readFileSync(path.join(REPO, 'scripts/forge/forge.py'), 'utf8');
  const block = forge.slice(forge.indexOf('WAITS_FOR_A_WAY = {'), forge.indexOf('}', forge.indexOf('WAITS_FOR_A_WAY = {')));
  assert.deepEqual(Array.from(block.matchAll(/^    "([a-z_]+)":/gm), (m) => m[1]).sort(), Object.keys(WAITS_FOR_A_WAY).sort(), 'forge.py keeps the same list');
});

test('a new room with no door fails the rule', () => {
  const quai = WORLD.places.find((p) => p.id === HOME_PLACE);
  const fresh = { id: 'librairie_test', name: quai.name, lat: quai.lat, lon: quai.lon, status: 'locked', kind: 'story', why: quai.why, room: 'librairie_test', in: HOME_PLACE, stages: ['librairie_test'] };
  assert.match(onFootProblems(fresh).join('\n'), /no entrance/);
  // and a door that opens onto nothing you can walk fails as well
  const flat = WORLD.places.find((p) => p.id === 'chez_marin_lila');
  const wrong = { ...flat, entrance: { ...flat.entrance, outside: [-27.6, 17.08] } };
  assert.match(onFootProblems(wrong).join('\n'), /not ground you walk in quai_de_valmy/);
});

test('the walk to Marin and Lila’s: the quai, the street door, the stairwell, the third floor, the flat', () => {
  const flat = WORLD.places.find((p) => p.id === 'chez_marin_lila');
  // the door is the quai's own street door: the corner house south of the rue de Lancry, bay 3
  assert.equal(flat.entrance.from, HOME_PLACE);
  assert.ok(flat.entrance.door[0] === -27 && flat.entrance.door[1] > 15.85 && flat.entrance.door[1] < 18.32);
  const quaiWays = doorsAt(HOME_PLACE);
  assert.ok(quaiWays.some((w) => w.to === 'chez_marin_lila'), 'the quai has the door into the building');
  assert.ok(doorsAt('chez_marin_lila').some((w) => w.to === HOME_PLACE), 'and the building has the door back out');
  const g = gridOf('chez_marin_lila');
  const inside = v(...flat.entrance.inside);
  // on the grid you climb to the first floor; the climb on to the third and the flat's door are passages
  const premier = v(-29.5, 17.75);
  assert.ok(walk(g.nav, inside, premier), 'up the flight to the first floor');
  assert.ok(Math.abs(g.nav.heightAt(premier.x, premier.z) - 4.6) < 0.1);
  const keys = g.passages.map((p) => p.key);
  assert.deepEqual(keys, ['escalier', 'porte']);
  const door = g.passages.find((p) => p.key === 'porte');
  assert.equal(door.until, 'story', 'the flat opens on foot once the story has played there (no spoiler of T5)');
  assert.ok(Math.abs(g.nav.heightAt(...door.a) - 11.2) < 0.1, 'the landing before the flat’s door is on the third floor');
  assert.ok(reachable(g, inside)(g.built.marks.caisse), 'through the door, the crate in the hallway');
});

test('played here: the story’s visit opens the flat’s door, a visit on foot does not', () => {
  const log = (day) => [{ day, at: 0, effect: { kind: 'place', id: 'chez_marin_lila', status: 'visited' } }];
  assert.equal(playedHere(log('room.chez_marin_lila'), 'chez_marin_lila'), false);
  assert.equal(playedHere(log('t5b'), 'chez_marin_lila'), true);
  assert.equal(playedHere([], 'chez_marin_lila'), false);
});
