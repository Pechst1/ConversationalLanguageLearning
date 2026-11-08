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
