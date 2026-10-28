// node --test lib/quartier/stage.test.js
//
// Le Quartier · the 3D stage plays T1 day a from the season's own file. These tests hold the
// director to that file: every movement is staged, every silent beat is acted, every reply's
// example reads as that reply, and every walk the scene asks for has a way through the streets.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));

const { STAGED, SILENT_BEATS, T1A, classify } = require('./stage.ts');

test('the copy of the day in the frontend is the season file, word for word', () => {
  const season = JSON.parse(fs.readFileSync(path.join(WEB_ROOT, '..', 'app/data/season/s1/t1.json'), 'utf8'));
  const day = season.days.find((d) => d.day === 'a');
  assert.deepEqual(T1A.movements, day.movements, 'run node scripts/quartier/sync-scene.mjs t1 a');
});

test('the director stages every movement of the day, in order', () => {
  assert.deepEqual(T1A.movements.map((m) => m.id), STAGED);
});

test('the hook has its lines to play', () => {
  const hook = T1A.movements.find((m) => m.id === 'a.hook');
  assert.ok(hook.panel.lines.length >= 3);
  assert.equal(hook.panel.lines[0].who, 'camille_marchand');
});

test('every silent beat of a reply is acted out', () => {
  // a «Le choix» (the café crème, the key) has options where a turn has replies
  for (const turn of T1A.movements.filter((m) => m.kind === 'turn' || m.kind === 'solve')) {
    for (const reply of turn.replies || turn.options) {
      for (const beat of reply.beats) {
        if (!beat.silence) continue;
        const acted = Object.values(SILENT_BEATS).some((re) => re.test(beat.id));
        assert.ok(acted, `${beat.id} is silent and nothing acts it`);
      }
    }
  }
});

test("each reply's examples read as that reply", () => {
  // the café crème and the key are choices: the engine reads them, not this prototype's reader
  for (const turn of T1A.movements.filter((m) => m.kind === 'turn' && !m.choice)) {
    for (const reply of turn.replies) {
      for (const example of reply.examples) {
        assert.equal(classify(turn.id, example), reply.id, `${turn.id}: «${example}»`);
      }
    }
  }
});

test('what a beginner might type finds a sensible reply', () => {
  const t1 = (s) => classify('a.turn1', s);
  const t2 = (s) => classify('a.turn2', s);
  assert.equal(t1('Je suis la petite-fille d’Odile.'), 'a');
  assert.equal(t1('Odile était ma grand-mère, je viens pour l’appartement.'), 'a');
  assert.equal(t1('Je vends l’appartement.'), 'b');
  assert.equal(t1('Bonsoir'), 'c');
  assert.equal(t1('grand-mère… clé…'), 'c');
  assert.equal(t1('Et vous, monsieur ? Qui êtes-vous ?'), 'd');
  assert.equal(t2('Oui, ce soir.'), 'tonight');
  assert.equal(t2('Non, pas ce soir.'), 'dont_know');
  assert.equal(t2('Je ne sais pas encore.'), 'dont_know');
  assert.equal(t2('Je vais vendre et partir dans une semaine.'), 'sell_and_leave');
  assert.equal(t2('Demain, peut… j’ai peur.'), 'clumsy');
  assert.equal(t2('Hmm'), 'dont_know');
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
