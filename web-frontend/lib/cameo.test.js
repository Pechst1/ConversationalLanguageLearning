// node --test lib/cameo.test.js
//
// Les apparitions: the cast walks in on the app. The director decides when,
// who and what they say; these tests hold its rhythm so the cameos stay a
// surprise and never a nuisance.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));

const {
  AMBIENT_COOLDOWN_MS,
  CAMEO_CAST,
  INITIAL_CAMEO_STATE,
  IDLE_COOLDOWN_MS,
  cameoGloss,
  castFor,
  decideCameo,
} = require('./cameo.ts');

const never = () => 0.99; // dice that never photobomb
const always = () => 0; // dice that always do

function run(events, rand = never, start = 1_000_000, from = INITIAL_CAMEO_STATE) {
  let state = from;
  const out = [];
  events.forEach((event, i) => {
    const now = typeof event.at === 'number' ? event.at : start + i * 1000;
    const result = decideCameo(state, event, now, rand);
    state = result.state;
    out.push(result.cameo);
  });
  return { state, out };
}

const right = (coachId) => ({ type: 'answer', correct: true, coachId });
const wrong = (coachId) => ({ type: 'answer', correct: false, coachId });

test('every cameo character has a drawn rig', () => {
  const rigs = fs.readdirSync(path.join(WEB_ROOT, 'components/cast/rigs'))
    .map((file) => fs.readFileSync(path.join(WEB_ROOT, 'components/cast/rigs', file), 'utf8'))
    .join('\n');
  CAMEO_CAST.forEach((who) => assert.ok(rigs.includes(`id: '${who.id}'`), who.id));
});

test('three right in a row brings a colleague of the coach (who is acting in the verdict), with their gag', () => {
  for (let seed = 0; seed < 6; seed += 1) {
    const rand = () => 0.3 + seed * 0.11; // high enough that nobody photobombs the first two
    const { out } = run([right('augustin_de_roncourt'), right('augustin_de_roncourt'), right('augustin_de_roncourt')], rand);
    assert.equal(out[0], null);
    assert.equal(out[1], null);
    assert.equal(out[2].trigger, 'streak');
    assert.equal(out[2].kind, 'solo');
    const who = out[2].figures[0].id;
    assert.notEqual(who, 'augustin_de_roncourt', 'never a second Gus beside the one in the verdict');
    assert.equal(out[2].gag, CAMEO_CAST.find((c) => c.id === who).gag, 'their own gag');
  }
});

test('six right in a row brings the troupe up from the bottom', () => {
  const { out } = run(Array.from({ length: 6 }, () => right()));
  const six = out[5];
  assert.equal(six.kind, 'troupe');
  assert.equal(six.edge, 'bottom');
  assert.ok(six.figures.length >= 3);
  assert.equal(new Set(six.figures.map((f) => f.line.fr)).size, six.figures.length, 'nobody says the same word twice');
});

test('a mistake breaks the streak', () => {
  const { out } = run([right(), right(), wrong(), right(), right()]);
  assert.deepEqual(out, [null, null, null, null, null]);
});

test('the second mistake in a row gets somebody on the learner’s side, never the cross coach', () => {
  for (let seed = 0; seed < 6; seed += 1) {
    const rand = () => seed / 6;
    const { out } = run([wrong('marin_leveque'), wrong('marin_leveque')], rand);
    assert.equal(out[0], null);
    assert.equal(out[1].trigger, 'comfort');
    assert.notEqual(out[1].figures[0].id, 'marin_leveque');
  }
});

test('photobombs respect the cooldown', () => {
  const t0 = 5_000_000;
  const { out } = run([
    { ...right(), at: t0 },
    { ...right(), at: t0 + 1000 },
    { ...wrong(), at: t0 + 2000 },
    { ...right(), at: t0 + AMBIENT_COOLDOWN_MS + 1 },
  ], always);
  assert.equal(out[0].trigger, 'photobomb');
  assert.equal(out[1], null, 'second right answer, still cooling down');
  assert.equal(out[3].trigger, 'photobomb');
});

test('two cameos in a row are two different people', () => {
  const t0 = 9_000_000;
  const { out } = run([
    { ...right(), at: t0 },
    { ...wrong(), at: t0 + 1 },
    { ...right(), at: t0 + AMBIENT_COOLDOWN_MS + 2 },
  ], always);
  assert.notEqual(out[0].figures[0].id, out[2].figures[0].id);
});

test('idle cameos come at most every three minutes', () => {
  const t0 = 20_000_000;
  const { out } = run([
    { type: 'idle', at: t0 },
    { type: 'idle', at: t0 + 60_000 },
    { type: 'idle', at: t0 + IDLE_COOLDOWN_MS + 1 },
  ]);
  assert.equal(out[0].trigger, 'idle');
  assert.equal(out[1], null);
  assert.equal(out[2].trigger, 'idle');
});

test('poking escalates: joke, «Encore ?», «Arrête !», then they give in', () => {
  const t0 = 30_000_000;
  const pokes = Array.from({ length: 5 }, (_, i) => ({ type: 'poke', id: 'lila_bonnet', at: t0 + i * 500 }));
  const { out } = run(pokes);
  assert.equal(out[0].figures[0].line.fr, 'Hé ! Ça chatouille !');
  assert.equal(out[1].figures[0].line.fr, 'Encore ?');
  assert.equal(out[2].figures[0].mood, 'fachee');
  assert.equal(out[4].figures[0].mood, 'emue');
  assert.ok(out.every((cameo) => cameo.kind === 'poke'));
});

test('a poke on someone outside the cast does nothing', () => {
  const { out } = run([{ type: 'poke', id: 'user' }]);
  assert.equal(out[0], null);
});

const everyoneMet = { ...INITIAL_CAMEO_STATE, met: CAMEO_CAST.map((c) => c.id) };

test('the finale is the whole troupe, and Marin cries', () => {
  const { out } = run([{ type: 'finale' }], never, 1_000_000, everyoneMet);
  assert.equal(out[0].trigger, 'finale');
  assert.equal(out[0].figures.length, CAMEO_CAST.length);
  assert.equal(out[0].figures.find((f) => f.id === 'marin_leveque').mood, 'emue');
});

test('the day’s own person takes the bow in the middle of the line', () => {
  for (const lead of CAMEO_CAST.map((c) => c.id)) {
    const { out } = run([{ type: 'finale', lead }], never, 1_000_000, everyoneMet);
    const ids = out[0].figures.map((f) => f.id);
    assert.equal(ids.length, CAMEO_CAST.length);
    assert.equal(new Set(ids).size, ids.length, 'everyone once');
    assert.equal(ids[Math.floor((ids.length - 1) / 2)], lead, lead);
  }
});

test('every line is French with a German and an English gloss, short enough for a bubble', () => {
  const source = fs.readFileSync(path.join(__dirname, 'cameo.ts'), 'utf8');
  const lines = [...source.matchAll(/L\('([^']+)', '([^']+)', '([^']+)'\)/g)];
  assert.ok(lines.length > 40);
  lines.forEach(([, fr, de, en]) => {
    assert.ok(fr.length <= 52, `too long for a bubble: ${fr}`);
    assert.ok(de && en, fr);
  });
  assert.equal(cameoGloss({ fr: 'Bravo !', de: 'Bravo!', en: 'Bravo!' }, 'fr'), null);
  assert.equal(cameoGloss({ fr: 'Chapeau !', de: 'Hut ab!', en: 'Hats off!' }, 'de'), 'Hut ab!');
});

test('the layer is mounted once and switchable in Réglages', () => {
  const app = fs.readFileSync(path.join(WEB_ROOT, 'pages/_app.tsx'), 'utf8');
  assert.match(app, /<CameoLayer \/>/);
  assert.match(app, /styles\/cameo\.css/);
  const settings = fs.readFileSync(path.join(WEB_ROOT, 'pages/settings.tsx'), 'utf8');
  assert.match(settings, /setCameosEnabled\(next\)/);
});

test('#155: Romy never walks in before the learner has met her, and does after', () => {
  const answers = Array.from({ length: 40 }, () => right(null));
  for (let seed = 0; seed < 40; seed += 1) {
    const rand = () => ((seed * 7 + 3) % 40) / 40;
    const { out } = run([...answers, { type: 'finale' }], rand);
    out.filter(Boolean).forEach((cameo) =>
      cameo.figures.forEach((figure) => assert.notEqual(figure.id, 'romy_tremblay')),
    );
  }
  const state = decideCameo(INITIAL_CAMEO_STATE, { type: 'met', ids: ['romy_tremblay', null] }, 1).state;
  assert.deepEqual(state.met, ['romy_tremblay']);
  assert.ok(castFor(state).some((who) => who.id === 'romy_tremblay'));
  assert.ok(!castFor(INITIAL_CAMEO_STATE).some((who) => who.id === 'romy_tremblay'));
  const finale = decideCameo(state, { type: 'finale' }, 2, () => 0.5).cameo;
  assert.equal(finale.figures.length, castFor(state).length);
});
