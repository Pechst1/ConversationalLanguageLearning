// node --test lib/quartier/stage.test.js
//
// Le Quartier · the 3D stage plays the season's days, T1 day a first. These tests hold the
// director to the season's own file: it has blocking for every movement, in the page's order, and
// every silent beat is acted; and every walk the scene asks for has a way through the streets.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));

const { GUESTS, OUTSIDE, STAGED, SILENT_BEATS, personOf, withoutCaptions } = require('./stage.ts');
const { T1A_COPY: T1A } = require('./story.ts');

test('the copy of the day in the frontend is the season file, word for word', () => {
  const season = JSON.parse(fs.readFileSync(path.join(WEB_ROOT, '..', 'app/data/season/s1/t1.json'), 'utf8'));
  const day = season.days.find((d) => d.day === 'a');
  assert.deepEqual(T1A.movements, day.movements, 'run node scripts/quartier/sync-scene.mjs t1 a');
});

test('the director has blocking for every movement of the day, in the order the page plays them', () => {
  const ids = T1A.movements.map((m) => m.id);
  for (const id of ids) assert.ok(STAGED.includes(id), `${id} has no blocking`);
  assert.deepEqual(ids, STAGED.filter((id) => ids.includes(id)));
});

test('the hook has its lines to play', () => {
  const hook = T1A.movements.find((m) => m.id === 'a.hook');
  assert.ok(hook.panel.lines.length >= 3);
  assert.equal(hook.panel.lines[0].who, 'camille_marchand');
});

test('every silent beat of a reply is acted out', () => {
  // a turn's replies, and the options of «Le choix» asked as a question
  for (const turn of T1A.movements.filter((m) => m.kind === 'turn' || m.kind === 'solve')) {
    const beats = [...(turn.replies ?? turn.options ?? []).flatMap((r) => r.beats), ...(turn.after ?? [])];
    for (const beat of beats) {
      if (!beat.silence) continue;
      const acted = Object.values(SILENT_BEATS).some((re) => re.test(beat.id));
      assert.ok(acted, `${beat.id} is silent and nothing acts it`);
    }
  }
});

test('the slide of the cup is acted, so its caption is left to the reply thread', () => {
  const caption = { who: 'caption', kind: 'caption', text_fr: "Margaux pousse la tasse jusqu'au tabouret d'Odile." };
  const said = { who: 'margaux_barman', kind: 'speech', text_fr: 'Bien.' };
  const beat = { kind: 'panel', id: 'a.cafe.declined.r1', silence: true, lines: [caption, said] };
  assert.deepEqual(withoutCaptions(beat).lines, [said]);
  assert.deepEqual(beat.lines, [caption, said]);
});

test('the café crème and the key are acted from the reply the engine read', () => {
  assert.ok(SILENT_BEATS.slide.test('a.cafe.declined.r1'));
  assert.ok(SILENT_BEATS.pocket.test('a.key.take.r1'));
  assert.ok(!SILENT_BEATS.pocket.test('a.key.leave.r1'));
  assert.ok(!SILENT_BEATS.cup.test('a.cafe.drink.r1'));
  assert.ok(SILENT_BEATS.cup.test('a.turn1.a.r1') && SILENT_BEATS.cup.test('a.turn1.c.r2'));
});

test('every walk the scene asks for has a way through the streets', () => {
  const { Vector3 } = require('three');
  const { CardPress, LacePress, Press, seeded } = require('./geo.ts');
  const { buildQuai, PLAN } = require('./quai.ts');
  const { buildMistral, MARKS } = require('./mistral.ts');
  const { Nav } = require('./nav.ts');
  const B = { dry: new Press(), fine: new Press(), wet: new Press(), lace: new LacePress(), glass: new Press(), cards: new CardPress(), signs: [], lamps: [], walk: [], blocks: [], rand: seeded(1102) };
  const quai = buildQuai(B);
  buildMistral(B, quai.mistral);
  const nav = new Nav(B.walk, B.blocks, { x0: -182, z0: -212, x1: 32, z1: 212 });
  const from = (v) => new Vector3(v.x, 0, v.z);
  const ways = [
    ['the start to the door', PLAN.start.pos, MARKS.doorOut],
    ['the door into the café', MARKS.doorOut, MARKS.doorIn],
    ['the door to the zinc', MARKS.doorIn, MARKS.atZinc],
    ['the booth to beside you', MARKS.boothMiddle, MARKS.zincBeside],
    ['the booth to the chair', MARKS.boothMiddle, MARKS.pulledChair],
    // a day without blocking: whoever a question is put to comes over, and goes back after
    ['the booth corner to beside you', MARKS.boothCorner, MARKS.zincBeside],
    ['the booth’s end to beside you', MARKS.boothLeft, MARKS.zincBeside],
    ['Camille’s table to beside you', new Vector3(-33.95, 0, -11.0), MARKS.zincBeside],
    // a guest (M. Marchand, Romy, Odile) comes in from the street to the zinc
    ['the street to beside you', MARKS.doorOut, MARKS.zincBeside],
    // out on the quai: whoever the moment is with walks the last steps to beside you
    ...OUTSIDE.beside.map((spot, i) => [`a few steps off to beside you on the quai (${i})`, spot.clone().add(OUTSIDE.approach), spot]),
  ];
  for (const [label, a, b] of ways) {
    const start = nav.nearest(a.x, a.z, 3);
    assert.ok(start, `${label}: nowhere to stand at the start`);
    const p = nav.path(new Vector3(start[0], 0, start[1]), from(b));
    assert.ok(p && p.length, `${label}: no way`);
    const end = p[p.length - 1];
    assert.ok(Math.hypot(end.x - b.x, end.z - b.z) < 0.9, `${label}: ends ${Math.hypot(end.x - b.x, end.z - b.z).toFixed(2)} m short`);
  }
  // the floor of the café is the café's floor, not the pavement
  assert.ok(Math.abs(nav.heightAt(MARKS.atZinc.x, MARKS.atZinc.z) - MARKS.atZinc.y) < 0.05);
});

test('day b: the director has blocking for every movement, in order, and the stairwell is a room of the season', () => {
  const season = JSON.parse(fs.readFileSync(path.join(WEB_ROOT, '..', 'app/data/season/s1/t1.json'), 'utf8'));
  const day = season.days.find((d) => d.day === 'b');
  const ids = day.movements.map((m) => m.id);
  for (const id of ids) assert.ok(STAGED.includes(id), `${id} has no blocking`);
  assert.deepEqual(ids, STAGED.filter((id) => ids.includes(id)));
  const { STAGED_DAYS, inRoom, roomOf } = require('./story.ts');
  assert.ok(STAGED_DAYS.includes('t1.b'));
  // the café hands the page over at R1, to the stairwell the forge built; the café's panels stay in the café
  const first = day.movements.find((m) => m.kind === 'panel' && roomOf(m));
  assert.equal(first.id, 'b.r1');
  assert.equal(roomOf(first), 'escalier_mistral');
  // R1 to R4 play on there: R2 is Odile's kitchen, seen through her open door from the landing
  const played = day.movements.filter((m) => m.kind === 'panel' && inRoom(m, 'escalier_mistral')).map((m) => m.id);
  assert.deepEqual(played, ['b.r1', 'b.r2', 'b.r3', 'b.r4']);
  const room = JSON.parse(fs.readFileSync(path.join(__dirname, 'world', 'rooms', `${roomOf(first)}.json`), 'utf8'));
  for (const mark of ['streetDoor', 'lilaStep', 'landing', 'door', 'threshold', 'inside']) assert.ok(room.marks[mark], `the stairwell has no «${mark}» mark`);
  // every silent beat of a reply is acted
  for (const turn of day.movements.filter((m) => m.kind === 'turn' || m.kind === 'solve')) {
    const beats = [...(turn.replies ?? turn.options ?? []).flatMap((r) => r.beats ?? []), ...(turn.after ?? [])];
    for (const beat of beats) {
      if (!beat.silence || (beat.lines ?? []).length) continue;
      assert.ok(Object.values(SILENT_BEATS).some((re) => re.test(beat.id)), `${beat.id} is silent and nothing acts it`);
    }
  }
});

test('a day without blocking plays in the places the world has built for it, and a card names the place', () => {
  const { PLACE_NAMES, placeCard, placesOf, unbuiltOf } = require('./story.ts');
  const page = (movements, location_id = null) => ({ key: 'x.y', location_id, movements });
  const at = (id, location_id) => ({ kind: 'panel', id, location_id, lines: [] });
  // the café and the quai are the hand-drawn quarter; a room of the season is the room the forge built
  assert.deepEqual(placesOf(page([at('p1', 'le_mistral'), at('p2', 'quai_de_valmy'), at('p3', 'stairwell'), at('p4', 'odile_flat'), at('p5', 'le_mistral')])), [
    'quai_de_valmy',
    'quai_de_valmy',
    'escalier_mistral',
    'odile_flat',
    'quai_de_valmy',
  ]);
  // a movement that names no place plays where the page is; the first, where the page says it is set; a page that names none, at the café
  assert.deepEqual(placesOf(page([at('p1', null), at('p2', null)], 'user_apartment')), ['user_apartment', 'user_apartment']);
  assert.deepEqual(placesOf(page([at('p1', null), { kind: 'hook', id: 'h', panel: at('h.p', null) }])), ['quai_de_valmy', 'quai_de_valmy']);
  assert.equal(unbuiltOf(page([at('p1', null)])), null);
  // somewhere nothing is built for yet: no place plays it, and the page says where
  assert.deepEqual(placesOf(page([at('p1', 'gare_de_lest'), at('p2', null), at('p3', 'le_mistral')])), [null, null, 'quai_de_valmy']);
  assert.equal(unbuiltOf(page([at('p1', 'le_mistral'), at('p2', 'gare_de_lest')])), 'gare_de_lest');
  assert.equal(unbuiltOf(page([at('p1', null)], 'gus_loft')), 'gus_loft');
  assert.equal(unbuiltOf(page([at('p1', 'somewhere_new')])), 'somewhere_new');
  // the season's own pages: T2 climbs the stairwell into Odile's flat; the roof (g3) plays on the roof the forge built
  // (the season file's own movements: a solve the server poses as a question has no place of its own)
  const staged = (movements) => movements.filter((m) => m.kind === 'panel' || m.panel);
  const season = (file, day) => {
    const d = JSON.parse(fs.readFileSync(path.join(WEB_ROOT, '..', 'app/data/season/s1', file), 'utf8')).days.find((x) => x.day === day);
    return { ...d, movements: staged(d.movements) };
  };
  const t2a = season('t2.json', 'a');
  assert.equal(unbuiltOf(t2a), null);
  assert.deepEqual(Array.from(new Set(placesOf(t2a))), ['escalier_mistral', 'odile_flat']);
  const t2b = season('t2.json', 'b');
  assert.equal(unbuiltOf(t2b), null);
  assert.deepEqual(Array.from(new Set(placesOf(t2b))), ['odile_flat', 'escalier_mistral', 'quai_de_valmy']);
  const g3 = JSON.parse(fs.readFileSync(path.join(WEB_ROOT, '..', 'app/data/season/s1/bridges.json'), 'utf8')).bridges.find((b) => b.gap === 'g3');
  const g3page = { location_id: g3.location_id, movements: staged(g3.moments.flatMap((m) => m.movements)) };
  assert.equal(unbuiltOf(g3page), null);
  assert.ok(placesOf(g3page).includes('toit_mistral'), 'the pages of the roof play on the roof');
  // T5 B: the portrait is shown in the back room the forge built, and its R2 goes up to Marin and Lila's flat
  const t5b = season('t5.json', 'b');
  assert.ok(placesOf(t5b).includes('arriere_salle'), 'the portrait plays in the back room');
  assert.ok(placesOf(t5b).includes('chez_marin_lila'), 'the door Marin opens is his flat’s');
  // the card
  assert.equal(placeCard('le_mistral'), null);
  assert.equal(placeCard('mistral_back_room'), null);
  assert.equal(placeCard('toit').fr, 'Le toit de l’immeuble');
  assert.equal(placeCard('toit').de, 'Das Dach des Hauses');
  assert.equal(placeCard('somewhere_new', 'La péniche').fr, 'La péniche');
  assert.equal(placeCard('somewhere_new'), null);
  // every place of the season has its name for the card
  const world = fs.readFileSync(path.join(WEB_ROOT, '..', 'app/services/season/world.py'), 'utf8');
  const ids = Array.from(world.matchAll(/^    "([a-z_]+)": \{"name_fr": "([^"]+)"/gm));
  assert.ok(ids.length > 15);
  for (const [, id, name] of ids) {
    if (id === 'le_mistral' || id === 'mistral_back_room') continue;
    assert.ok(PLACE_NAMES[id], `${id} has no name for the card`);
    assert.equal(PLACE_NAMES[id].fr.replace(/’/g, "'"), name, `${id}: the card's name is not the season's`);
  }
});

test('in a room the forge built, the moment’s people stand in front of you on your floor, apart', () => {
  const { Vector3 } = require('three');
  const { groundIn, HEIGHTS, GUESTS } = require('./stage.ts');
  const { buildRoom } = require('./room.ts');
  const { CardPress, LacePress, Press, seeded } = require('./geo.ts');
  const { Nav } = require('./nav.ts');
  for (const id of ['escalier_mistral', 'odile_flat', 'user_apartment', 'notaire']) {
    const spec = JSON.parse(fs.readFileSync(path.join(__dirname, 'world', 'rooms', `${id}.json`), 'utf8'));
    const B = { dry: new Press(), fine: new Press(), wet: new Press(), lace: new LacePress(), glass: new Press(), cards: new CardPress(), signs: [], lamps: [], walk: [], blocks: [], rand: seeded(7) };
    const room = buildRoom(B, spec);
    const nav = new Nav(B.walk, B.blocks, room.bounds);
    const g = groundIn(room.start, nav);
    assert.ok(g.beside.length >= 2, `${id}: room for ${g.beside.length} beside you`);
    assert.equal(g.approach, null, `${id}: nobody walks in from the street`);
    const ahead = new Vector3(room.start.look.x - g.you.x, 0, room.start.look.z - g.you.z).normalize();
    g.beside.forEach((b, i) => {
      assert.ok(nav.standable(b.x, b.z), `${id}: place ${i} is not on the floor`);
      assert.ok(Math.abs(b.y - g.you.y) < 0.5, `${id}: place ${i} is on another floor`);
      const d = Math.hypot(b.x - g.you.x, b.z - g.you.z);
      assert.ok(d > 0.8 && d < 2.6, `${id}: place ${i} is ${d.toFixed(2)} m away`);
      assert.ok((b.x - g.you.x) * ahead.x + (b.z - g.you.z) * ahead.z > 0, `${id}: place ${i} is behind you`);
      for (const c of g.beside.slice(i + 1)) assert.ok(Math.hypot(b.x - c.x, b.z - c.z) >= 0.7, `${id}: two places on top of each other`);
    });
  }
  // everyone with a body can be stood up in a room, where the troupe starts empty
  for (const k of ['augustin_de_roncourt', 'marin_leveque', 'lila_bonnet', 'margaux_barman', 'camille_marchand', ...Object.keys(GUESTS)]) assert.ok(HEIGHTS[k] > 1.4, `${k} has no height`);
});

test('the bridges’ people who are not regulars come on as guests with a body (M. Marchand on the roof)', () => {
  const bridges = JSON.parse(fs.readFileSync(path.join(WEB_ROOT, '..', 'app/data/season/s1/bridges.json'), 'utf8'));
  const people = new Set();
  const walk = (x) => {
    if (Array.isArray(x)) return x.forEach(walk);
    if (!x || typeof x !== 'object') return;
    if (typeof x.who === 'string') people.add(x.who);
    if (x.kind === 'turn' && typeof x.to === 'string') people.add(x.to);
    for (const k of x.in_frame ?? []) people.add(k);
    Object.values(x).forEach(walk);
  };
  walk(bridges.bridges);
  assert.ok(people.has('landlord_marchand'));
  // everyone in the round (cast3d/people) is a regular or a guest, and has their name on the cards;
  // a passer-by without a body (the clerk) keeps the name the page gives
  const bodies = ['margaux_barman', 'augustin_de_roncourt', 'lila_bonnet', 'marin_leveque', 'romy_tremblay', 'landlord_marchand', 'camille_marchand', 'odile_ferrand'];
  const regulars = ['margaux_barman', 'augustin_de_roncourt', 'lila_bonnet', 'marin_leveque', 'camille_marchand'];
  for (const who of bodies) {
    assert.ok(personOf(who), `${who} has no name on the cards`);
    assert.ok(regulars.includes(who) || GUESTS[who] > 1.4, `${who} has a body and never comes on`);
  }
});
