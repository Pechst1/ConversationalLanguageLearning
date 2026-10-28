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

const { STAGED, SILENT_BEATS } = require('./stage.ts');
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
