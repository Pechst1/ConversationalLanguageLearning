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
const { BACK_TABLES, MARKS, ROOM, SHELVES, TILL, ZINC } = require('./mistral.ts');
const { buildRoom, polaroidWall } = require('./room.ts');
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

test("Romy's tuque, beside the closed blue folder on the back table: laid once a page left it at Le Mistral", () => {
  const tuque = details.find(({ spec }) => spec.id === 'tuque_romy').spec;
  assert.equal(tuque.in, 'quai_de_valmy');
  assert.deepEqual(tuque.mark, { name_fr: 'La tuque de Romy', location_id: 'le_mistral' });
  const laid = (marks) => setBy([tuque], { flags: {}, marks }).map((d) => d.spec.id);
  assert.deepEqual(laid([{ kind: 'thing', name_fr: 'la tuque de Romy', location_id: 'le_mistral' }]), ['tuque_romy']);
  assert.deepEqual(laid([{ kind: 'thing', name_fr: 'La tuque de Romy', location_id: 'marin_lila_flat' }]), []);
  const hat = tuque.things.find((t) => t.kind === 'tuque');
  const folder = tuque.things.find((t) => t.kind === 'folder');
  assert.ok(hat && folder, 'a tuque and the folder it rests beside');
  assert.equal(folder.tone, 'dossier', 'the folder is blue');
  assert.ok(!folder.text?.[0], "closed, nobody's name on it");
  // both on the left back table's marble, inside its edge, clear of Marin's bowl of soup
  const tx = BACK_TABLES.xs[0];
  const r = hat.size[0];
  // the folder 0.33 by 0.245, turned: the half-extents of its footprint along x and z
  const fx = (0.33 / 2) * Math.abs(Math.cos(folder.rot)) + (0.245 / 2) * Math.abs(Math.sin(folder.rot));
  const fz = (0.33 / 2) * Math.abs(Math.sin(folder.rot)) + (0.245 / 2) * Math.abs(Math.cos(folder.rot));
  for (const [t, hx, hz] of [[hat, r, r], [folder, fx, fz]]) {
    assert.ok(Math.abs(t.at[1] - BACK_TABLES.top) < 0.005, `the ${t.kind} lies on the table's top`);
    assert.ok(Math.abs(t.at[0] - tx) + hx < BACK_TABLES.w / 2 && Math.abs(t.at[2] - BACK_TABLES.z) + hz < BACK_TABLES.d / 2, `the ${t.kind} is on the table, not over its edge`);
    assert.ok(t.at[0] + hx < BACK_TABLES.bowl.x - BACK_TABLES.bowl.r, `the ${t.kind} keeps clear of the bowl`);
  }
  // beside each other, not on top of each other
  assert.ok(Math.abs(hat.at[0] - folder.at[0]) >= r + fx - 0.01, 'the tuque beside the folder, not on it');
  assert.ok(Math.hypot(hat.at[0] - folder.at[0], hat.at[2] - folder.at[2]) < 0.4, 'and close by it');
});

test("Odile's bank card, beside Margaux's lease letter on the zinc: laid once a page left it at Le Mistral", () => {
  const spec = details.find(({ spec }) => spec.id === 'carte_odile').spec;
  assert.equal(spec.in, 'quai_de_valmy');
  assert.deepEqual(spec.mark, { name_fr: 'La carte bleue d’Odile', location_id: 'le_mistral' });
  const laid = (marks) => setBy([spec], { flags: {}, marks }).map((d) => d.spec.id);
  assert.deepEqual(laid([{ kind: 'thing', name_fr: 'La carte bleue d’Odile', location_id: 'le_mistral' }]), ['carte_odile']);
  assert.deepEqual(laid([{ kind: 'thing', name_fr: 'La carte bleue d’Odile', location_id: 'odile_flat' }]), []);
  const card = spec.things.find((t) => t.kind === 'carte');
  const letter = spec.things.find((t) => t.kind === 'recommande');
  assert.ok(card && letter, 'a card and the letter it lies beside');
  assert.ok(card.text[0].includes('ODILE'), 'her name on the card');
  // the lease letter is Margaux's from Marchand's office: «le bail expire le 31 mars»
  assert.ok(letter.text.join(' ').includes('le bail expire le 31 mars'), 'the lease ends on 31 March');
  assert.ok(letter.text[0].includes('MARCHAND'), "on the gérance's letterhead");
  // both on the zinc's top, within it, between where the key lies and Odile's stool
  const cup = details.find(({ spec: d }) => d.id === 'tasse_habituelle').spec.things[0];
  for (const [t, reach] of [[card, 0.05], [letter, 0.2]]) {
    assert.ok(Math.abs(t.at[1] - ZINC.top) < 0.005, `the ${t.kind} lies on the zinc's top`);
    assert.ok(t.at[0] - reach > ZINC.back && t.at[0] + reach < ZINC.front, `the ${t.kind} is on the zinc, not over its edge`);
    assert.ok(t.at[2] + reach < MARKS.atZinc.z - 0.2 && t.at[2] + reach < cup.at[2] - 0.2, `the ${t.kind} keeps clear of the key and your cup`);
    assert.ok(t.at[2] - reach > MARKS.odileStool.z + 0.3, `the ${t.kind} short of Odile's place`);
  }
  // beside the letter, not on it
  const gap = Math.abs(card.at[2] - letter.at[2]);
  assert.ok(gap > 0.105 + 0.045 && gap < 0.45, 'the card beside the letter, close by');
});

test("Odile's card, her name in Lila's hand, pinned on the wall by the corner booth: laid once a page left it at Le Mistral", () => {
  const spec = details.find(({ spec }) => spec.id === 'carte_nom_odile').spec;
  assert.equal(spec.in, 'quai_de_valmy');
  assert.deepEqual(spec.mark, { name_fr: "la carte d'Odile", location_id: 'le_mistral' });
  const laid = (marks) => setBy([spec], { flags: {}, marks }).map((d) => d.spec.id);
  assert.deepEqual(laid([{ kind: 'thing', name_fr: "La carte d'Odile", location_id: 'le_mistral' }]), ['carte_nom_odile']);
  assert.deepEqual(laid([{ kind: 'thing', name_fr: "la carte d'Odile", location_id: 'odile_flat' }]), []);
  // not her bank card on the zinc: another order, another thing
  assert.notEqual(foldName(spec.mark.name_fr), foldName(details.find(({ spec: d }) => d.id === 'carte_odile').spec.mark.name_fr));
  const [card] = spec.things;
  assert.equal(card.kind, 'pinned');
  assert.equal(card.text[0], 'Odile', 'her name on it');
  const [w, h] = card.size;
  assert.ok(w <= 0.2 && h <= 0.15, 'a small card');
  // on the north wall's face, facing the room, behind the booth
  assert.equal(card.rot, 0);
  assert.ok(card.at[2] - ROOM.z0 > 0 && card.at[2] - ROOM.z0 < 0.03, "on the wall's face");
  // above the booth's back (its rail at 1.38 m off the floor) and under the old poster's frame
  // (1.06 m tall, centred at 2.5 m: mistral.ts), by Gus's corner seat, short of the east wall
  assert.ok(card.at[1] - h / 2 > ROOM.floor + 1.45, "above the booth's back");
  assert.ok(card.at[1] + h / 2 < 2.5 - 0.53 - 0.05, "under the poster's frame");
  assert.ok(Math.abs(card.at[0] - MARKS.boothCorner.x) < 0.8 && card.at[0] + w / 2 < ROOM.x1 - 0.2, 'beside the corner seat, off the corner');
});

test("the drawing «Maîtresse à Berlin», pinned beside Odile's Polaroid by the corner booth: laid once a page left it at Le Mistral", () => {
  const spec = details.find(({ spec }) => spec.id === 'dessin_maitresse').spec;
  assert.equal(spec.in, 'quai_de_valmy');
  assert.deepEqual(spec.mark, { name_fr: 'le dessin « Maîtresse à Berlin »', location_id: 'le_mistral' });
  const laid = (marks) => setBy([spec], { flags: {}, marks }).map((d) => d.spec.id);
  assert.deepEqual(laid([{ kind: 'thing', name_fr: 'Le dessin « Maîtresse à Berlin »', location_id: 'le_mistral' }]), ['dessin_maitresse']);
  assert.deepEqual(laid([{ kind: 'thing', name_fr: 'le dessin « Maîtresse à Berlin »', location_id: 'marin_lila_flat' }]), []);
  const drawing = spec.things.find((t) => t.kind === 'drawing');
  const photo = spec.things.find((t) => t.kind === 'snapshot');
  assert.ok(drawing && photo, 'the drawing and the portrait it hangs beside');
  // the pupils' words, and the date Lila leaves (her card on Marin's fridge: «le 8 janvier»)
  assert.equal(drawing.text[0], 'Maîtresse à Berlin');
  assert.match(drawing.text[1], /8 janvier/);
  const fridge = ROOMS.chez_marin_lila.things.find((t) => t.kind === 'fridge');
  assert.ok(fridge.text.join(' ').includes('8 janvier'), 'the same date as her card');
  // each on the north wall's face, facing the room, above the booth's back, under nothing
  const box = (t) => {
    const [w, h] = t.kind === 'snapshot' ? [0.088, 0.107] : t.size;
    return { x0: t.at[0] - w / 2, x1: t.at[0] + w / 2, y0: t.at[1] - h / 2, y1: t.at[1] + h / 2 };
  };
  for (const t of [drawing, photo]) {
    assert.equal(t.rot, 0);
    assert.ok(t.at[2] - ROOM.z0 > 0 && t.at[2] - ROOM.z0 < 0.03, `the ${t.kind} on the wall's face`);
    const b = box(t);
    assert.ok(b.y0 > ROOM.floor + 1.45, `the ${t.kind} above the booth's back`);
    assert.ok(b.x1 < ROOM.x1 - 0.05, `the ${t.kind} short of the corner`);
    // clear of the old poster's frame (x -28.3, 0.78 by 1.06, centred at 2.5 m: mistral.ts)
    assert.ok(b.x0 > -28.3 + 0.39 || b.y1 < 2.5 - 0.53, `the ${t.kind} clear of the poster`);
  }
  // beside each other, not overlapping, and clear of Odile's name card should a page leave both
  const overlap = (a, b) => a.x0 < b.x1 && b.x0 < a.x1 && a.y0 < b.y1 && b.y0 < a.y1;
  assert.ok(!overlap(box(drawing), box(photo)), 'the drawing beside the photo, not over it');
  assert.ok(Math.abs(drawing.at[0] - photo.at[0]) < 0.4, 'and close by it');
  const name = details.find(({ spec: d }) => d.id === 'carte_nom_odile').spec.things[0];
  const nameBox = { x0: name.at[0] - name.size[0] / 2, x1: name.at[0] + name.size[0] / 2, y0: name.at[1] - name.size[1] / 2, y1: name.at[1] + name.size[1] / 2 };
  for (const t of [drawing, photo]) assert.ok(!overlap(box(t), nameBox), `the ${t.kind} clear of Odile's name card`);
  // her name card sits under her photo, as the cards sit under the Polaroids on the party's wall
  assert.ok(Math.abs(name.at[0] - photo.at[0]) < 0.02 && nameBox.y1 < box(photo).y0, 'the photo above her name card');
});

test("the learner's coat, on the hook under Odile's Polaroid in the corner by the zinc: laid once a page left it at Le Mistral", () => {
  const spec = details.find(({ spec }) => spec.id === 'manteau_mistral').spec;
  assert.equal(spec.in, 'quai_de_valmy');
  assert.deepEqual(spec.mark, { name_fr: 'le manteau du Mistral', location_id: 'le_mistral' });
  const laid = (marks) => setBy([spec], { flags: {}, marks }).map((d) => d.spec.id);
  assert.deepEqual(laid([{ kind: 'thing', name_fr: 'Le manteau du Mistral', location_id: 'le_mistral' }]), ['manteau_mistral']);
  assert.deepEqual(laid([{ kind: 'thing', name_fr: 'le manteau du Mistral', location_id: 'odile_flat' }]), []);
  const coat = spec.things.find((t) => t.kind === 'coat');
  const photo = spec.things.find((t) => t.kind === 'snapshot');
  assert.ok(coat && photo, 'the coat and the portrait it hangs under');
  // the learner's own coat, not Odile's green one (the coat's default tone)
  assert.ok(coat.tone && coat.tone !== 'coat', "the learner's coat in a colour of its own");
  // another photo of Odile than the one by the booth: by day, with its caption
  assert.ok(photo.text?.[0], 'a captioned Polaroid, not the same photo twice');
  // both on the north wall's face, facing the room
  for (const t of [coat, photo]) {
    assert.equal(t.rot, 0);
    assert.ok(t.at[2] - ROOM.z0 > 0 && t.at[2] - ROOM.z0 < 0.03, `the ${t.kind} on the wall's face`);
  }
  // in the corner the zinc's north end makes with the booth's end (mistral.ts: the booth's end
  // panel stands from x -33.8): the coat, 0.6 m across, hangs between them, its hem off the floor
  const coatBox = { x0: coat.at[0] - 0.3, x1: coat.at[0] + 0.3, y0: coat.at[1] - 1.0, y1: coat.at[1] + 0.03 };
  assert.ok(coatBox.x0 > ZINC.front - 0.4 && coatBox.x1 < -33.8, 'the coat between the zinc and the booth');
  assert.ok(ZINC.north - ROOM.z0 > 0.2, 'the zinc stops short of the wall, so the coat hangs clear of it');
  assert.ok(coatBox.y0 > ROOM.floor + 0.5 && coatBox.y1 < ZINC.top + 0.75, 'the coat hangs at a hook, its hem off the floor');
  // the photo just above the hook, centred on it, clear of the clock over the zinc's far end
  const [pw, ph] = [0.088, 0.107];
  const photoBox = { x0: photo.at[0] - pw / 2, x1: photo.at[0] + pw / 2, y0: photo.at[1] - ph / 2, y1: photo.at[1] + ph / 2 };
  assert.ok(Math.abs(photo.at[0] - coat.at[0]) < 0.02, 'the photo over the hook');
  assert.ok(photoBox.y0 > coatBox.y1 && photoBox.y0 - coatBox.y1 < 0.15, 'just above it');
  assert.ok(photoBox.x0 > -35.9 + 0.26 || photoBox.y1 < 3.05 - 0.26, 'clear of the clock');
});

test("Odile's wall: rows of her Polaroids above the booth, Lila's card under each, the burnt one alone in a gap: laid once a page left it at Le Mistral", () => {
  const spec = details.find(({ spec }) => spec.id === 'mur_odile').spec;
  assert.equal(spec.in, 'quai_de_valmy');
  assert.deepEqual(spec.mark, { name_fr: "le mur d'Odile", location_id: 'le_mistral' });
  const laid = (marks) => setBy([spec], { flags: {}, marks }).map((d) => d.spec.id);
  assert.deepEqual(laid([{ kind: 'thing', name_fr: "Le mur d'Odile", location_id: 'le_mistral' }]), ['mur_odile']);
  assert.deepEqual(laid([{ kind: 'thing', name_fr: "le mur d'Odile", location_id: 'odile_flat' }]), []);
  assert.equal(spec.things.length, 1);
  const wall = spec.things[0];
  assert.equal(wall.kind, 'polaroidwall');
  // the burnt Polaroid's own words (04-la-photographie.md, P6)
  assert.deepEqual(wall.text, ["14 mars. 23 h. J'ai oublié. Encore."]);
  const { photos, centre } = polaroidWall(wall.size);
  // about sixty of them (the canon's «sixty»), round the one in the gap
  assert.ok(photos.length + 1 >= 55 && photos.length + 1 <= 70, `${photos.length + 1} photos`);
  // on the north wall's face, facing the room
  assert.equal(wall.rot, 0);
  assert.ok(wall.at[2] - ROOM.z0 > 0 && wall.at[2] - ROOM.z0 < 0.03, "on the wall's face");
  // each photo (8.8 by 10.7 cm, a hand's shift and tilt aside) and Lila's card under it
  const reach = { u: 0.044 + 0.015, top: 0.0535 + 0.01, low: 0.09 + 0.018 + 0.006 };
  const boxes = [...photos, centre].map(([u, v]) => ({ x0: wall.at[0] + u - reach.u, x1: wall.at[0] + u + reach.u, y0: wall.at[1] + v - reach.low, y1: wall.at[1] + v + reach.top }));
  const overlap = (a, b) => a.x0 < b.x1 && b.x0 < a.x1 && a.y0 < b.y1 && b.y0 < a.y1;
  // the booth's back (its rail at 1.54 m) under them, the ceiling over them
  for (const b of boxes) assert.ok(b.y0 > ROOM.floor + 1.45 && b.y1 < ROOM.ceiling - 0.3, 'above the booth, under the ceiling');
  // between the two old posters (x -32.15 and -28.3, 0.78 by 1.06, centred at 2.5 m: mistral.ts)
  const posters = [-32.15, -28.3].map((x) => ({ x0: x - 0.39, x1: x + 0.39, y0: 2.5 - 0.53, y1: 2.5 + 0.53 }));
  for (const b of boxes) for (const p of posters) assert.ok(!overlap(b, p), 'clear of the posters');
  // the booth's sconce (x -30.2, its bowl from 2.08 to 2.28 m) hangs in the gap, under the burnt one
  const sconce = { x0: -30.2 - 0.13, x1: -30.2 + 0.13, y0: 2.06, y1: 2.3 };
  for (const b of boxes) assert.ok(!overlap(b, sconce), 'clear of the sconce');
  const burnt = boxes[boxes.length - 1];
  assert.ok(Math.abs(wall.at[0] + centre[0] - -30.2) < 0.05 && burnt.y0 > sconce.y1, 'the burnt one over the sconce, at the very centre');
  // and clear of what other pages leave on that wall: Odile's name card, her Polaroid, the drawing
  for (const id of ['carte_nom_odile', 'dessin_maitresse']) {
    for (const t of details.find(({ spec: d }) => d.id === id).spec.things) {
      const [w, h] = t.kind === 'snapshot' ? [0.088, 0.107] : t.size;
      const tb = { x0: t.at[0] - w / 2, x1: t.at[0] + w / 2, y0: t.at[1] - h / 2, y1: t.at[1] + h / 2 };
      for (const b of boxes) assert.ok(!overlap(b, tb), `clear of ${id}'s ${t.kind}`);
    }
  }
});

test("M. Marchand's reply, «J'y serai. M.», propped against the till: laid once the learner had him invited", () => {
  const spec = details.find(({ spec }) => spec.id === 'carte_marchand').spec;
  assert.equal(spec.in, 'quai_de_valmy');
  assert.equal(spec.flag.key, 's1.marchand_invited');
  // a flag that is only true: laid when he was invited, not before, not when he was not
  assert.deepEqual(setBy([spec], { flags: { 's1.marchand_invited': true } }).map((d) => d.spec.id), ['carte_marchand']);
  assert.deepEqual(setBy([spec], { flags: { 's1.marchand_invited': false } }), []);
  assert.deepEqual(setBy([spec], { flags: {} }), []);
  const card = spec.things.find((t) => t.kind === 'replycard');
  assert.ok(card && spec.things.length === 1, 'one card');
  // his words, as the gap gives them: «J'y serai. M.»
  assert.deepEqual(card.text, ["J'y serai.", 'M.']);
  // standing on the zinc's top, its words to the room, leaned back against the till's front
  assert.ok(Math.abs(card.at[1] - ZINC.top) < 0.01, 'on the zinc');
  assert.ok(Math.abs(card.rot - Math.PI / 2) < 0.01, 'facing the room');
  assert.ok(card.at[0] > TILL.front && card.at[0] - TILL.front < 0.03, "at the till's front");
  assert.ok(card.at[0] < ZINC.front, 'on the counter, not over its edge');
  assert.ok(Math.abs(card.at[2] - TILL.z) + 0.07 < TILL.half, "within the till's length");
  // clear of the other things left on the zinc: the usual cup, Odile's card and the lease letter
  for (const id of ['tasse_habituelle', 'carte_odile']) {
    for (const t of details.find(({ spec: d }) => d.id === id).spec.things) assert.ok(Math.abs(t.at[2] - card.at[2]) > 0.5, `clear of ${id}`);
  }
});

test("Lila's painting of the omelette, smoke and all, propped against the bottles behind the zinc: laid once a page left it at Le Mistral", () => {
  const spec = details.find(({ spec }) => spec.id === 'tableau_omelette').spec;
  assert.equal(spec.in, 'quai_de_valmy');
  assert.deepEqual(spec.mark, { name_fr: "le tableau de l'omelette de Lila", location_id: 'le_mistral' });
  const laid = (marks) => setBy([spec], { flags: {}, marks }).map((d) => d.spec.id);
  assert.deepEqual(laid([{ kind: 'thing', name_fr: "le tableau de l'omelette de Lila", location_id: 'le_mistral' }]), ['tableau_omelette']);
  assert.deepEqual(laid([{ kind: 'thing', name_fr: "le tableau de l'omelette de Lila", location_id: 'odile_flat' }]), []);
  assert.equal(spec.things.length, 1);
  const p = spec.things[0];
  assert.equal(p.kind, 'oilsketch');
  // no words on its face: its back (Odile's name) faces the bottles, and no signature could be
  // taken for «L.»'s on the painting above the zinc
  assert.equal(p.text, undefined);
  const [w, h] = p.size;
  // a small canvas: smaller than «L.»'s, larger than a card
  assert.ok(w <= 0.45 && h <= 0.35 && w > h, 'a small landscape canvas');
  // standing on the lower shelf, its face to the room
  assert.ok(Math.abs(p.at[1] - (ROOM.floor + SHELVES.rows[0] + 0.015)) < 0.003, 'on the lower shelf');
  assert.ok(Math.abs(p.rot - Math.PI / 2) < 0.01, 'facing the room');
  // its foot on the shelf, in front of the bottles; leaned back 0.14 rad on its 1.8 cm stretcher
  // (room.ts), its top rests on them without going through
  assert.ok(p.at[0] < SHELVES.x + SHELVES.depth / 2 && p.at[0] > SHELVES.x + SHELVES.bottle, "its foot on the shelf's front");
  const topBack = p.at[0] - h * Math.sin(0.14) - 0.018;
  assert.ok(topBack >= SHELVES.x + SHELVES.bottle - 0.003 && topBack < SHELVES.x + SHELVES.bottle + 0.02, 'against the bottles');
  // under the upper shelf, along the zinc where the shelves run, clear of the coffee machine
  assert.ok(p.at[1] + h < ROOM.floor + SHELVES.rows[1] - 0.015, 'under the upper shelf');
  assert.ok(p.at[2] - w / 2 > ZINC.north + 0.5 && p.at[2] + w / 2 < ZINC.south - 0.4, 'where the bottles stand');
  assert.ok(Math.abs(p.at[2] - SHELVES.machineZ) > 0.375 + w / 2 + 0.1, 'clear of the coffee machine');
  // and below «L.»'s painting, which stays where it hangs above the mirror
  assert.ok(MARKS.painting.y - 0.31 > p.at[1] + h + 0.5, "well under «L.»'s painting");
});

test('the Christmas note for M. Marchand, propped against his desk lamp with the paper bag beside it: laid once a page left it in his office', () => {
  const spec = details.find(({ spec }) => spec.id === 'mot_noel_marchand').spec;
  assert.equal(spec.in, 'gerance_marchand');
  assert.deepEqual(spec.mark, { name_fr: 'le mot de Noël pour Marchand', location_id: 'marchand_office' });
  const laid = (marks) => setBy([spec], { flags: {}, marks }).map((d) => d.spec.id);
  assert.deepEqual(laid([{ kind: 'thing', name_fr: 'Le mot de Noël pour Marchand', location_id: 'marchand_office' }]), ['mot_noel_marchand']);
  assert.deepEqual(laid([{ kind: 'thing', name_fr: 'le mot de Noël pour Marchand', location_id: 'le_mistral' }]), []);
  const card = spec.things.find((t) => t.kind === 'notecard');
  const bag = spec.things.find((t) => t.kind === 'paperbag');
  assert.ok(card && bag && spec.things.length === 2, 'a card and a paper bag');
  // the learner's words to a stranger: vous or nothing, Christmas and the croissants, no name
  const words = card.text.join(' ');
  assert.match(words, /Joyeux Noël/);
  assert.match(words, /croissants/);
  assert.match(words, /Marchand/);
  assert.doesNotMatch(words.toLowerCase(), /\b(tu|te|toi|ton|ta|tes|t')\b/, 'a stranger gets vous');
  // on his desk's top (`desk`: its top at 0.76 m), within it
  const room = ROOMS.gerance_marchand;
  const desk = room.things.find((t) => t.kind === 'desk');
  const [dw, dd] = desk.size;
  const toDesk = ([x, , z]) => {
    const dx = x - desk.at[0];
    const dz = z - desk.at[2];
    return [dx * Math.cos(desk.rot) - dz * Math.sin(desk.rot), dx * Math.sin(desk.rot) + dz * Math.cos(desk.rot)];
  };
  for (const t of [card, bag]) {
    assert.ok(Math.abs(t.at[1] - (desk.at[1] + 0.76)) < 0.005, `the ${t.kind} on the desk's top`);
    const [lx, lz] = toDesk(t.at);
    assert.ok(Math.abs(lx) < dw / 2 - 0.08 && Math.abs(lz) < dd / 2 - 0.08, `the ${t.kind} within the desk`);
  }
  // the desk lamp's round foot (room.ts: 0.24 m behind its shade's mouth, 0.095 m across): the
  // card stands just outside it, its back to the lamp, so it leans on the stem
  const lamp = room.lights.find((l) => l.kind === 'desk');
  const [fx, fz] = lamp.facing;
  const foot = [lamp.at[0] - 0.24 * fx, lamp.at[2] - 0.24 * fz];
  const off = [card.at[0] - foot[0], card.at[2] - foot[1]];
  const dist = Math.hypot(...off);
  assert.ok(dist > 0.095 && dist < 0.12, `the card at the lamp's foot (${dist.toFixed(3)} m)`);
  const facing = [Math.sin(card.rot), Math.cos(card.rot)];
  assert.ok((facing[0] * off[0] + facing[1] * off[1]) / dist > 0.95, 'its back to the lamp');
  // out from under the shade (0.12 m round its mouth), so it can be read from the visitor's side
  assert.ok(Math.hypot(card.at[0] - lamp.at[0], card.at[2] - lamp.at[2]) > 0.12 + 0.03, 'not under the shade');
  // the bag beside it, clear of the lamp's foot, the shade, the files and the framed Polaroids
  const bagReach = Math.hypot(bag.size[0], bag.size[0] * 0.6) / 2;
  assert.ok(Math.hypot(bag.at[0] - card.at[0], bag.at[2] - card.at[2]) < 0.4, 'beside the card');
  assert.ok(Math.hypot(bag.at[0] - foot[0], bag.at[2] - foot[1]) > 0.095 + bagReach, "clear of the lamp's foot");
  assert.ok(Math.hypot(bag.at[0] - lamp.at[0], bag.at[2] - lamp.at[2]) > 0.12 + bagReach || bag.size[1] < lamp.at[1] - 0.13 - bag.at[1], 'under or clear of the shade');
  for (const f of room.things.filter((t) => t.kind === 'frame')) assert.ok(Math.hypot(bag.at[0] - f.at[0], bag.at[2] - f.at[2]) > bagReach + 0.08, 'clear of a framed Polaroid');
  const [blx] = toDesk(bag.at);
  // (`desk`: the files at local x -w/2 + 0.24, 0.33 m long)
  assert.ok(blx > -dw / 2 + 0.24 + 0.165 + bagReach, "clear of the files at the desk's end");
  // the office's lettering and the card's words all print
  const B = press();
  buildRoom(B, room);
  buildDetail(B, spec);
  const want = B.signs.reduce((n, s) => n + (s.width * (s.density ?? 150) + 4) * (s.height * (s.density ?? 150) + 4), 0);
  assert.ok(want < 2048 * 2048 * 0.6, `the office's lettering and the card fit the sign atlas (${(want / (2048 * 2048)).toFixed(2)})`);
});
