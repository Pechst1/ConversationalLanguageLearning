// node --test lib/quartier/details.test.js
//
// Le Quartier · Le Mistral's details, written from the canon. A detail waits on a season flag
// the story engine sets, stands in Le Mistral's room (the cup on the zinc, not in the air), and is
// laid only when asked for: the quarter shows none of them until the story reaches it. Every
// value the season offers for its flag builds.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..');
const REPO = path.resolve(WEB_ROOT, '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));

const { CardPress, LacePress, Press, seeded } = require('./geo.ts');
const { buildDetail, detailThings } = require('./details.ts');
const { ROOM } = require('./mistral.ts');
const { WORLD, mapPlaces } = require('./world.ts');

const DIR = path.join(__dirname, 'world', 'details');
const files = fs.readdirSync(DIR).filter((f) => f.endsWith('.json'));
const details = files.map((f) => ({ file: f, spec: JSON.parse(fs.readFileSync(path.join(DIR, f), 'utf8')) }));
const SEASON = JSON.parse(fs.readFileSync(path.join(REPO, 'app/data/season/s1/season.json'), 'utf8'));
const BRIDGES = fs.readFileSync(path.join(REPO, 'app/data/season/s1/bridges.json'), 'utf8');

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
    assert.ok(SEASON.flags.some((f) => f.id === spec.flag.key), `${file}: the season has no flag ${spec.flag.key}`);
    assert.ok(spec.flag.example, `${file}: a value to show when none is given`);
    assert.ok(WORLD.places.some((p) => p.id === spec.in) && pins.has(spec.in), `${file}: in ${spec.in}, a place on the map`);
    assert.ok(index.indexOf(`  ${spec.id}: () => import('./${spec.id}.json')`) >= 0, `details/index.ts does not load ${spec.id}`);
  });
});

test("a detail stands in Le Mistral's room, on something, and every value the season offers builds", () => {
  details.forEach(({ file, spec }) => {
    spec.things.forEach((t) => {
      const [x, y, z] = t.at;
      assert.ok(x > ROOM.x0 && x < ROOM.x1 && z > ROOM.z0 && z < ROOM.z1, `${file}: ${t.kind} is outside Le Mistral's room`);
      assert.ok(y >= ROOM.floor && y < ROOM.ceiling, `${file}: ${t.kind} at ${y} m`);
    });
    const values = [spec.flag.example, ...valuesOf(spec.flag.key)];
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
