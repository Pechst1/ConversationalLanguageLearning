// node --test lib/quartier/details.test.js
//
// Le Quartier · Le Mistral's details, written from the canon. A detail waits on a season flag
// the story engine sets, stands in Le Mistral's room (the cup on the zinc, not in the air), and is
// laid only once the learner's own story set its flag (the server's world-state): the quarter
// shows none of them before. Every value the season offers for its flag builds.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..');
const REPO = path.resolve(WEB_ROOT, '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));

const { CardPress, LacePress, Press, seeded } = require('./geo.ts');
const { buildDetail, detailThings, flagValue, foldName, setBy } = require('./details.ts');
const { ROOM } = require('./mistral.ts');
const { buildRoom } = require('./room.ts');
const { WORLD, mapPlaces } = require('./world.ts');

const DIR = path.join(__dirname, 'world', 'details');
const files = fs.readdirSync(DIR).filter((f) => f.endsWith('.json'));
const details = files.map((f) => ({ file: f, spec: JSON.parse(fs.readFileSync(path.join(DIR, f), 'utf8')) }));
const SEASON = JSON.parse(fs.readFileSync(path.join(REPO, 'app/data/season/s1/season.json'), 'utf8'));
const BRIDGES = fs.readFileSync(path.join(REPO, 'app/data/season/s1/bridges.json'), 'utf8');
const STAGES = JSON.parse(fs.readFileSync(path.join(REPO, 'app/data/season/s1/stages.json'), 'utf8')).stages;
const ROOM_DIR = path.join(__dirname, 'world', 'rooms');
const ROOMS = Object.fromEntries(
  fs.readdirSync(ROOM_DIR).filter((f) => f.endsWith('.json')).map((f) => [f.replace(/\.json$/, ''), JSON.parse(fs.readFileSync(path.join(ROOM_DIR, f), 'utf8'))]),
);

const words = (w) => Boolean(w && w.fr && w.en && w.de);
const press = () => ({ dry: new Press(), fine: new Press(), wet: new Press(), lace: new LacePress(), glass: new Press(), cards: new CardPress(), signs: [], lamps: [], walk: [], blocks: [], rand: seeded(1102) });

/** Every value the season's bridges offer for a flag («un café crème», «un thé»…). */
function valuesOf(key) {
  const re = new RegExp(`"${key.replace('.', '\\.')}"\\s*:\\s*"([^"]+)"`, 'g');
  return [...new Set([...BRIDGES.matchAll(re)].map((m) => m[1]))];
}

test('there is at least one detail, and each names itself after its file, its flag and its canon', () => {
  assert.ok(details.length >= 1);
  const index = fs.readFileSync(path.join(DIR, 'index.ts'), 'utf8');
  const pins = new Set(mapPlaces().map((p) => p.id));
  details.forEach(({ file, spec }) => {
    assert.equal(`${spec.id}.json`, file);
    assert.equal(spec.kind, 'detail', file);
    assert.equal(spec.version, 1, file);
    assert.ok(words(spec.title), `${file}: its title in three languages`);
    assert.ok(spec.moment, `${file}: the line of the ladder it is`);
    assert.ok(fs.existsSync(path.join(REPO, spec.provenance.canon)), `${file}: no canon file ${spec.provenance.canon}`);
    assert.ok(spec.provenance.scenes.length, `${file}: the scenes it is written from`);
    assert.ok(Boolean(spec.flag) !== Boolean(spec.mark), `${file}: waits on a season flag or on a mark the story left, one of them`);
    if (spec.flag) {
      assert.ok(SEASON.flags.some((f) => f.id === spec.flag.key), `${file}: the season has no flag ${spec.flag.key}`);
      assert.ok(spec.flag.example, `${file}: a value to show when none is given`);
    } else {
      // a story order: the mark as a page leaves it, in a season place this built place stages
      assert.ok(spec.mark.name_fr && spec.mark.name_fr.length <= 80, `${file}: the mark's French name`);
      assert.equal(STAGES[spec.mark.location_id], spec.in, `${file}: «${spec.mark.location_id}» does not play in ${spec.in} (app/data/season/s1/stages.json)`);
      assert.ok(spec.things.every((t) => !(t.text ?? []).some((line) => line.includes('{value}'))), `${file}: a mark has no value to write in`);
    }
    const room = ROOMS[spec.in];
    assert.ok(WORLD.places.some((p) => p.id === spec.in) && (pins.has(spec.in) || room), `${file}: in ${spec.in}, a place of the world`);
    assert.ok(index.indexOf(`  ${spec.id}: () => import('./${spec.id}.json')`) >= 0, `details/index.ts does not load ${spec.id}`);
  });
});

test('a detail stands inside its place (Le Mistral\'s room, or a room of the season), and every value the season offers builds', () => {
  details.forEach(({ file, spec }) => {
    const room = ROOMS[spec.in];
    const inside = room ? buildRoom(press(), room).bounds : ROOM;
    spec.things.forEach((t) => {
      const [x, y, z] = t.at;
      assert.ok(x > inside.x0 && x < inside.x1 && z > inside.z0 && z < inside.z1, `${file}: ${t.kind} is outside ${room ? spec.in : "Le Mistral's room"}`);
      if (!room) assert.ok(y >= ROOM.floor && y < ROOM.ceiling, `${file}: ${t.kind} at ${y} m`);
    });
    const values = spec.flag ? [spec.flag.example, ...valuesOf(spec.flag.key)] : [undefined];
    values.forEach((v) => {
      const B = press();
      buildDetail(B, spec, v);
      assert.ok(B.dry.geometry().getAttribute('position').count > 0, `${file}: nothing built for «${v}»`);
      detailThings(spec, v).forEach((t) => (t.text ?? []).forEach((s) => assert.ok(s.indexOf('{value}') < 0, `${file}: «{value}» left in its text`)));
    });
  });
});

test("the cup is the learner's own order: a different order, a different cup", () => {
  const cup = details.find(({ spec }) => spec.id === 'tasse_habituelle');
  assert.ok(cup, 'the usual cup is written');
  const count = (v) => {
    const B = press();
    buildDetail(B, cup.spec, v);
    return B.dry.geometry().getAttribute('position').count;
  };
  const orders = valuesOf('user.usual_order');
  assert.ok(orders.length >= 3, 'the season offers several usual orders');
  // a tea's tag hangs over its rim: it has more to it than a café crème
  assert.ok(count('un thé') > count('un café crème'));
  assert.equal(detailThings(cup.spec, 'un noisette')[0].text[0], 'un noisette');
  assert.equal(detailThings(cup.spec)[0].text[0], cup.spec.flag.example);
});

test("the quarter lays a detail once the learner's story set its flag, with its value", () => {
  const specs = details.map(({ spec }) => spec);
  const cup = specs.find((spec) => spec.id === 'tasse_habituelle');
  // nothing set: nothing laid
  assert.deepEqual(setBy(specs, null), []);
  assert.deepEqual(setBy(specs, { flags: {}, marks: [] }), []);
  assert.deepEqual(setBy(specs, { flags: { 'user.usual_order': '  ' } }), []);
  assert.deepEqual(setBy(specs, { flags: { 'user.usual_order': false } }), []);
  // the learner's order: their cup, with their order on it
  const laid = setBy(specs, { flags: { 'user.usual_order': ' un thé ', 'perm.photo.romy': 'granted' } });
  assert.deepEqual(laid.map((d) => [d.spec.id, d.value]), [['tasse_habituelle', 'un thé']]);
  assert.equal(detailThings(laid[0].spec, laid[0].value)[0].text[0], 'un thé');
  // a flag that is only true lays the detail with its example
  assert.equal(flagValue({ [cup.flag.key]: true }, cup.flag.key), '');
  assert.equal(setBy([cup], { flags: { [cup.flag.key]: true } })[0].value, undefined);
  assert.equal(flagValue({ n: 2 }, 'n'), '2');
  assert.equal(flagValue({ l: ['a'] }, 'l'), null);
});

test('a story order is laid once a page of the learner\'s own story left it there', () => {
  const petition = {
    ...details[0].spec,
    id: 'petition_gus',
    flag: undefined,
    mark: { name_fr: 'la pétition de Gus', location_id: 'le_mistral' },
    things: [{ kind: 'drink', at: [-35.05, 1.262, -12.95], rot: 0 }],
  };
  const left = (marks) => setBy([petition], { flags: {}, marks }).map((d) => d.spec.id);
  assert.deepEqual(left([{ kind: 'thing', name_fr: 'La  Pétition de Gus', location_id: 'le_mistral' }]), ['petition_gus']);
  // left somewhere else, or only named as a place: not this one
  assert.deepEqual(left([{ kind: 'thing', name_fr: 'la pétition de Gus', location_id: 'stairwell' }]), []);
  assert.deepEqual(left([{ kind: 'place', name_fr: 'la pétition de Gus', location_id: 'le_mistral' }]), []);
  assert.deepEqual(left([]), []);
  assert.equal(foldName('  La   Pétition '), 'la pétition');
});

test("Lila's banner, rolled behind the zinc: laid once a page left it at Le Mistral, not where her flat has its own", () => {
  const banner = details.find(({ spec }) => spec.id === 'banderole_lila').spec;
  assert.deepEqual(banner.mark, { name_fr: 'la banderole de Lila', location_id: 'le_mistral' });
  const laid = (marks) => setBy([banner], { flags: {}, marks }).map((d) => d.spec.id);
  assert.deepEqual(laid([{ kind: 'thing', name_fr: 'la banderole de Lila', location_id: 'le_mistral' }]), ['banderole_lila']);
  // the same name left in Marin and Lila's flat is another thing (a cloth banner drying there)
  assert.deepEqual(laid([{ kind: 'thing', name_fr: 'la banderole de Lila', location_id: 'marin_lila_flat' }]), []);
  // a roll standing on the floor at the zinc's far end, by the booth, its top no higher than the zinc
  const [roll] = banner.things;
  assert.equal(roll.kind, 'roll');
  assert.ok(Math.abs(roll.at[1] - ROOM.floor) < 0.01, 'it stands on the floor');
  assert.ok(roll.at[2] < -17.4 && roll.at[2] > ROOM.z0, 'between the zinc and the north wall, by the booth');
  assert.ok(roll.size[0] * Math.cos(0.33) < 1.3, 'it leans on the zinc, not over it');
});

test("Lila's banner in her flat, drying over two chairs: laid once a page left it there, standing clear of the room's things", () => {
  const banner = details.find(({ spec }) => spec.id === 'banderole_lila_seche').spec;
  assert.equal(banner.in, 'chez_marin_lila');
  assert.deepEqual(banner.mark, { name_fr: 'la banderole de Lila', location_id: 'marin_lila_flat' });
  const laid = (marks) => setBy([banner], { flags: {}, marks }).map((d) => d.spec.id);
  assert.deepEqual(laid([{ kind: 'thing', name_fr: 'La  banderole de Lila', location_id: 'marin_lila_flat' }]), ['banderole_lila_seche']);
  // the same name left at Le Mistral is the rolled paper one, not this
  assert.deepEqual(laid([{ kind: 'thing', name_fr: 'la banderole de Lila', location_id: 'le_mistral' }]), []);
  const room = ROOMS.chez_marin_lila;
  const sejour = room.floors.find((f) => f.key === 'sejour');
  const [[sx0, sz0], , [sx1, sz1]] = sejour.shape;
  const drape = banner.things.find((t) => t.kind === 'drape');
  const chairs = banner.things.filter((t) => t.kind === 'chair');
  assert.equal(chairs.length, 2, 'two chairs to dry it on');
  assert.ok(drape.text.join(' ').includes('25 ANS DU MISTRAL'), 'it reads «Les 25 ans du Mistral»');
  banner.things.forEach((t) => {
    assert.ok(Math.abs(t.at[1] - sejour.y) < 0.01, `${t.kind} stands on the séjour's floor`);
    assert.ok(t.at[0] > sx0 + 0.3 && t.at[0] < sx1 - 0.3 && t.at[2] > sz0 + 0.3 && t.at[2] < sz1 - 0.3, `${t.kind} inside the séjour, off its walls`);
  });
  // the chairs' top rails are where the cloth hangs: one at each end of the span
  const half = drape.size[0] / 2;
  chairs.forEach((c) => {
    assert.ok(Math.abs(c.at[2] - 0.185 - drape.at[2]) < 0.01, 'its back under the cloth');
    assert.ok(Math.abs(Math.abs(c.at[0] - drape.at[0]) - (half - 0.21)) < 0.01, 'at an end of the span');
  });
  // clear of the room's own furniture (the walk keeps to what the room blocks)
  const B = press();
  buildRoom(B, room);
  const before = B.blocks.length;
  const D = press();
  buildDetail(D, banner);
  const box = (poly) => poly.reduce((b, [x, z]) => [Math.min(b[0], x), Math.min(b[1], z), Math.max(b[2], x), Math.max(b[3], z)], [Infinity, Infinity, -Infinity, -Infinity]);
  const [bx0, bz0, bx1, bz1] = box(D.blocks[0]);
  B.blocks.slice(0, before).forEach((poly) => {
    const [x0, z0, x1, z1] = box(poly);
    assert.ok(x1 <= bx0 || x0 >= bx1 || z1 <= bz0 || z0 >= bz1, `the banner's chairs stand in a thing of the room at ${[x0, z0, x1, z1].map((v) => v.toFixed(2))}`);
  });
  // the room's marks stay where you can stand
  Object.entries(room.marks).forEach(([name, [mx, , mz]]) => assert.ok(!(mx > bx0 && mx < bx1 && mz > bz0 && mz < bz1), `the mark ${name} is under the banner`));
  // the flat's cards and the banner's words all print
  buildDetail(B, banner);
  const want = B.signs.reduce((n, s) => n + (s.width * (s.density ?? 150) + 4) * (s.height * (s.density ?? 150) + 4), 0);
  assert.ok(want < 2048 * 2048 * 0.6, `the flat's lettering and the banner's words fit the sign atlas (${(want / (2048 * 2048)).toFixed(2)})`);
});

test("Odile's burnt frying pan, soaking in her sink with a tea towel over the tap: laid once a page left it in her flat", () => {
  const pan = details.find(({ spec }) => spec.id === 'poele_odile').spec;
  assert.equal(pan.in, 'odile_flat');
  assert.deepEqual(pan.mark, { name_fr: "la poêle brûlée d'Odile", location_id: 'odile_flat' });
  const laid = (marks) => setBy([pan], { flags: {}, marks }).map((d) => d.spec.id);
  assert.deepEqual(laid([{ kind: 'thing', name_fr: "La poêle brûlée d'Odile", location_id: 'odile_flat' }]), ['poele_odile']);
  assert.deepEqual(laid([{ kind: 'thing', name_fr: "la poêle brûlée d'Odile", location_id: 'le_mistral' }]), []);
  // the flat's own sink, against the kitchen's east wall beside the window: the pan in its basin,
  // the towel on its tap's arm (`sink`: the basin's inside at local x -w/2 + 0.3, z 0.26, floor
  // 0.86 m, 0.46 by 0.36; the arm from the wall to z 0.2 at 1.18 m)
  const room = ROOMS.odile_flat;
  const sink = room.things.find((t) => t.kind === 'sink');
  assert.ok(sink, "Odile's kitchen has a sink");
  const toWorld = ([lx, ly, lz]) => [
    sink.at[0] + lx * Math.cos(sink.rot) + lz * Math.sin(sink.rot),
    sink.at[1] + ly,
    sink.at[2] - lx * Math.sin(sink.rot) + lz * Math.cos(sink.rot),
  ];
  const near = (a, b, tol, what) => a.forEach((v, i) => assert.ok(Math.abs(v - b[i]) < tol, `${what}: ${a} is not at ${b.map((n) => n.toFixed(2))}`));
  const bx = -sink.size[0] / 2 + 0.3;
  const soak = pan.things.find((t) => t.kind === 'soak');
  near(soak.at, toWorld([bx, 0.86, 0.26]), 0.02, 'the pan lies on the basin floor');
  assert.equal(soak.rot, sink.rot, 'its handle toward the room');
  assert.ok(soak.size[0] <= 0.46 && soak.size[1] <= 0.36, 'the pan is kept inside the basin');
  const towel = pan.things.find((t) => t.kind === 'towel');
  near(towel.at, toWorld([bx, 1.18, 0.12]), 0.02, "the towel hangs on the tap's arm");
  assert.ok(towel.size[0] <= 0.18, "no wider than the tap's arm is long");
  assert.ok(towel.at[1] - towel.size[1] > sink.at[1] + 0.86, "and clear of the basin's floor");
  // beside the kitchen's window, in its light, and off the calendar's mark
  const [wx] = room.walls.find((w) => w.key === 'cuisine.e').a;
  assert.ok(Math.abs(sink.at[0] - wx) < 0.01, 'its back on the east wall, the window wall');
  const [, , cz] = room.marks.calendrier;
  assert.ok(sink.at[2] - sink.size[0] / 2 - 0.02 > cz, 'the calendar can still be read from its mark');
});

test("the stairwell's view into Odile's kitchen has her flat's things, where her flat has them", () => {
  const flat = ROOMS.odile_flat;
  const stair = ROOMS.escalier_mistral;
  const key = (t) => `${t.kind}@${t.at.map((v) => v.toFixed(2)).join(',')}`;
  const kitchen = (t) => t.at[2] < -14.9 && t.at[2] > -18.75 && t.at[0] > -31.8 && t.at[0] <= -27.26 && t.at[1] >= 4.5 && t.at[1] < 7.6;
  const seen = new Set(stair.things.filter(kitchen).map(key));
  flat.things.filter(kitchen).forEach((t) => assert.ok(seen.has(key(t)), `the stairwell's kitchen has no ${key(t)}`));
});
