// node --test lib/quartier/round-three.test.js
//
// P12 round 3 · Le Quartier as the second integration walk met it (17 Nov, walk2-integration-a1):
// 1. the end card and the carnet said «Tu as dit que tu viens pour vendre» of «Je suis Jonas. Je
//    venir pour la apartement.» (shot 082, `a1-d3-q-carnet`), reproduced from the stored day-1 turns;
// 2. «Im Quartier spielen» on day 1 only: day 3 (notaire) and day 5 (user_apartment) were written
//    at night in built places;
// 3. a stray tap left the scene, and coming back started it from the top;
// 4. map labels touched the frame and the red ring (`a1-d3-q-map`);
// 5. endings that change language halfway («… und reste avec toi dans l’attente …»).

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));
const resolve = Module._resolveFilename;
Module._resolveFilename = function alias(request, ...rest) {
  if (typeof request === 'string' && request.startsWith('@/')) return resolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  return resolve.call(this, request, ...rest);
};
const apiPath = Module._resolveFilename('@/services/api', module, false);
require.cache[apiPath] = { id: apiPath, filename: apiPath, loaded: true, exports: { __esModule: true, default: {}, apiService: {} } };

// the phone's storage, for the scene's place
const stored = new Map();
global.window = global.window ?? {};
global.window.localStorage = {
  getItem: (k) => (stored.has(k) ? stored.get(k) : null),
  setItem: (k, v) => stored.set(k, String(v)),
  removeItem: (k) => stored.delete(k),
};

const { JourneyStory, pageOfJourney, todayOf } = require('./journey-story.ts');
const { replyEffects } = require('./agency.ts');

const DAY1 = require('./fixtures/walk2-a1-day1-turns.json');

const line = (who, text_fr) => ({ who, name: null, kind: who === 'caption' ? 'caption' : 'speech', mood: 'neutral', direction: null, text_fr, text_native: null });
const STAGE = {
  season_id: 's1',
  segment: 't1',
  day: 'a',
  key: 't1.a',
  number: 1,
  title_fr: 'Le mauvais accueil',
  location_id: 'le_mistral',
  movements: [
    { kind: 'panel', id: 'a.p1', location_id: 'quai_de_valmy', in_frame: ['toi'], lines: [line('caption', 'Il pleut.')] },
    { kind: 'panel', id: 'a.p2', location_id: 'le_mistral', in_frame: [], lines: [line('augustin_de_roncourt', 'Augustin, vous êtes trop élégant !')] },
    { kind: 'turn', id: 'a.turn1', to: 'augustin_de_roncourt', to_name: 'Gus', task_native: 'Sag, wer du bist.', choice: false, only_after: null, panel: { kind: 'panel', id: 'a.p6', lines: [line('augustin_de_roncourt', 'Et pourquoi ici ?')] } },
    { kind: 'turn', id: 'a.turn2', to: 'margaux_barman', to_name: 'Margaux', task_native: 'Sag Margaux, ob du hochgehst.', choice: false, only_after: null, panel: { kind: 'panel', id: 'a.p7', lines: [line('margaux_barman', 'Tu vas monter ?')] } },
    { kind: 'turn', id: 'a.key', to: 'margaux_barman', to_name: 'Margaux', task_native: 'Nimm den Schlüssel.', choice: true, only_after: null, panel: { kind: 'panel', id: 'a.key.p', lines: [] } },
    { kind: 'hook', id: 'a.hook', role: 'midpoint', panel: { kind: 'panel', id: 'a.p8', lines: [line('camille_marchand', 'Bonsoir.')] } },
  ],
  storylets: [],
};

function journey({ revision = 3, current = 'talk', turn = 0, id = 'j-walk2' } = {}) {
  const at = ['scene', 'talk', 'end'].indexOf(current);
  const state = (i) => (i < at ? 'completed' : i === at ? 'active' : 'pending');
  return {
    id,
    revision,
    status: 'active',
    current_step_id: current,
    steps: [
      { id: 'scene', kind: 'scene', ordinal: 0, status: state(0), prompt: { objective_native: '', stage: STAGE } },
      { id: 'talk', kind: 'respond', ordinal: 1, status: state(1), prompt: { turn_index: turn, help_available: [], targets: [], choices: [], objective_native: '', character_line_fr: 'Et pourquoi ici ?' } },
      { id: 'end', kind: 'resolution', ordinal: 2, status: state(2), prompt: {} },
    ],
  };
}

function storyOn(j, handlers) {
  const svc = {};
  for (const m of ['get', 'resume', 'advance', 'attempt', 'help', 'finish', 'choose']) {
    svc[m] = async (...args) => {
      if (!handlers[m]) throw new Error(`unexpected ${m}`);
      return handlers[m](...args);
    };
  }
  return new JourneyStory(j, pageOfJourney(j), { service: svc, sleep: async () => undefined });
}

/** What the engine answered each stored turn: its route, its outcome, and whether it was a card. */
const attempted = (t, i, chosen = false) => ({
  pending: false,
  task_outcome: t.task_outcome,
  journey: journey({ revision: 4 + i, turn: i + 1 }),
  correction: null,
  character_lines: [],
  next_turn: { step_id: 'talk' },
  stage: { turn_id: t.turn, reply_id: t.reply, beats: [], next_turn_id: DAY1.turns[i + 1]?.turn ?? null, closing: false, chosen },
});

const journal = (effects) => effects.filter((e) => e.kind === 'journal').map((e) => e.words.fr);

/* ---- 1 · «Tu as dit …» says only what the learner said -------------------------------------- */

test('1 · the walk’s day 1, replayed from its stored turns: no «Tu as dit …» of a route the learner did not say', async () => {
  const lines = [];
  const chosen = [];
  let n = 0;
  const story = storyOn(journey(), { attempt: async () => attempted(DAY1.turns[n], n) });
  for (const [i, t] of DAY1.turns.entries()) {
    n = i;
    const heard = await story.answer(t.turn, t.learner);
    assert.equal(heard.reply, t.reply);
    lines.push(...journal(replyEffects(t.turn, heard.reply, { understood: heard.understood, chosen: heard.chosen })));
    chosen.push(heard.chosen);
  }
  // observed: «Tu as dit que tu viens pour vendre.» and «Tu as gardé la clé.»
  assert.ok(!lines.includes('Tu as dit que tu viens pour vendre.'), lines.join(' / '));
  assert.ok(lines.every((l) => !/^Tu as dit\b/.test(l)), lines.join(' / '));
  // what happened in the room, from the characters’ side, and what the learner did
  assert.deepEqual(lines, ["Gus a compris : tu viens pour l'appartement.", 'Tu as gardé la clé.']);
  // the learner’s own words contain what the room took them to mean
  assert.match(DAY1.turns[0].learned.find((l) => l.key === 'why_here').quote, /apartement/);
  assert.deepEqual(chosen, [false, false, false], 'all three were typed, none was a card');
});

test('1 · a card chosen word for word is what the learner said; a fallback says nothing; the facts follow the engine', async () => {
  const card = { ...DAY1.turns[0], learner: 'Je viens pour vendre.' };
  const heard = await storyOn(journey(), { attempt: async () => attempted(card, 0, true) }).answer('a.turn1', card.learner);
  assert.equal(heard.chosen, true);
  assert.deepEqual(journal(replyEffects('a.turn1', 'b', heard)), ['Tu as dit que tu viens pour vendre.']);
  assert.deepEqual(journal(replyEffects('a.turn1', 'b', { understood: false })), []);
  assert.ok(replyEffects('a.turn1', 'b', { understood: true }).some((e) => e.kind === 'fact' && e.value === 'selling'));
  // every line that restates the learner’s words is marked, and none of their stand-ins says «Tu as dit»
  const { REPLY_EFFECTS } = require('./agency.ts');
  for (const [key, effects] of Object.entries(REPLY_EFFECTS)) {
    for (const e of effects.filter((x) => x.kind === 'journal')) {
      if (/^Tu as (dit|demandé|retourné|voulu|refusé)|^Tu voulais|^Tu ne sais pas/.test(e.words.fr)) assert.equal(e.said, true, `${key}: ${e.words.fr}`);
      if (e.heard) assert.doesNotMatch(e.heard.fr, /^Tu as dit/, key);
    }
  }
  // the stage hands the engine’s card flag on, and the server sends it
  const stage = fs.readFileSync(path.join(WEB_ROOT, 'lib/quartier/stage.ts'), 'utf8');
  assert.match(stage, /replyEffects\(turn\.id, heard\.reply, \{ understood: heard\.understood, chosen: heard\.chosen \}\)/);
});

/* ---- 2 · a day written at night, in a built place, is offered ------------------------------- */

test('2 · Home offers the Quartier on a gap day the night wrote in a built place, not in an unbuilt one', () => {
  const door = require('./home-door.ts');
  const offer = (stage) => ({ kind: 'offer', scenario: { scenario_key: 'story_next', location_id: '' }, envelope: { headline: { stage } } });
  // walk days 3 and 5: «Chez le notaire», «Ton appartement» (pilot_events, written before Start)
  assert.equal(door.quartierCanStage(offer({ key: 'jour.g1', location_id: 'notaire', locations: [] }), true), true);
  assert.equal(door.quartierCanStage(offer({ key: 'jour.g1', location_id: 'user_apartment', locations: [] }), true), true);
  assert.equal(door.quartierCanStage(offer({ key: 'jour.g1', location_id: 'le_mistral', locations: [] }), true), true);
  // no room for the mairie; day 2 goes up the unfinished stairwell
  assert.equal(door.quartierCanStage(offer({ key: 'jour.g1', location_id: 'mairie', locations: [] }), true), false);
  assert.equal(door.quartierCanStage(offer({ key: 't1.b', location_id: 'le_mistral', locations: ['le_mistral', 'stairwell', 'odile_flat'] }), true), false);
  // not written yet: nothing to offer
  assert.equal(door.quartierCanStage(offer(null), true), false);
});

/* ---- 3 · leaving mid-scene and coming back plays on ----------------------------------------- */

test('3 · back in the Quartier mid-scene, the scene plays on where this device left it', async () => {
  stored.clear();
  // left before the first answer, at Gus's bow: the scene picks up there, not on the quai
  const before = storyOn(journey({ current: 'scene' }), {});
  before.keepPlace({ from: 'a.p2', routes: {}, asking: 'a.turn1' });
  assert.deepEqual(storyOn(journey({ current: 'scene' }), {}).keptPlace(), { from: 'a.p2', routes: {}, asking: 'a.turn1' });
  // left after the first answer: the engine has turn 1; the quarter kept its route and the next question
  const after = storyOn(journey({ turn: 1 }), {});
  after.keepPlace({ from: 'a.turn2', routes: { 'a.turn1': 'b' }, asking: 'a.turn2' });
  assert.deepEqual(todayOf(journey({ turn: 1 })).kind, 'play', 'Home and /quartier play on, not hand the day to the Feuilleton');
  const back = storyOn(journey({ turn: 1 }), {});
  assert.deepEqual(back.keptPlace(), { from: 'a.turn2', routes: { 'a.turn1': 'b' }, asking: 'a.turn2' });
  // answered elsewhere since (the engine is at turn 2): this device's place is stale
  assert.equal(storyOn(journey({ turn: 2 }), {}).keptPlace(), null);
  assert.deepEqual(todayOf(journey({ turn: 2 })), { kind: 'handoff', why: 'midway' });
  // another journey never reads it
  assert.equal(storyOn(journey({ turn: 1, id: 'j-other' }), {}).keptPlace(), null);
  // the stage starts from the kept place when nothing else hands it one
  const stage = fs.readFileSync(path.join(WEB_ROOT, 'lib/quartier/stage.ts'), 'utf8');
  assert.match(stage, /const resume = this\.resume \?\? this\.story\.keptPlace\?\.\(\) \?\? null;/);
  assert.match(stage, /this\.story\.keepPlace\?\.\(\{ from: id, routes: this\.routes, asking: this\.asking \}\)/);
});

test('3 · the scene played to its hook keeps nothing', async () => {
  stored.clear();
  const s = storyOn(journey({ turn: 1 }), {});
  s.keepPlace({ from: 'a.turn2', routes: { 'a.turn1': 'b' }, asking: 'a.turn2' });
  await s.close().catch(() => undefined);
  assert.equal(storyOn(journey({ turn: 1 }), {}).keptPlace(), null);
});

/* ---- 4 · La Carte measures its labels ------------------------------------------------------- */

test('4 · La Carte, measured: every name inside the frame, clear of every pin and ring, never «Le q…»', () => {
  const { projectPoint } = require('@/components/carte/carte-projection');
  const { mapPlaces } = require('./world.ts');
  const { LABEL, HALO, CUT_MIN, pinReach } = require('./map-labels.ts');
  const { WHOLE_BOX, labelsFor, pinsIn, quarterBox } = require('@/components/quartier/QuartierMap.tsx');
  const raw = mapPlaces()
    .map((p) => ({ p, xy: projectPoint('paris', p.lat, p.lon) }))
    .filter((x) => x.xy);
  // the phone's serif italic ran wider than the estimate: «Le q…» reached the frame
  const measure = (text, size) => Array.from(text).length * 0.62 * size;
  for (const [zoom, box, whole] of [
    ['Ton quartier', quarterBox(raw.map((x) => x.xy)), false],
    ['Tout Paris', WHOLE_BOX, true],
  ]) {
    const u = box[2] / 100;
    const here = 'quai_de_valmy';
    const pins = pinsIn(raw, box, here);
    const labels = labelsFor(pins, box, here, measure, whole);
    assert.ok(labels.length >= 3, zoom);
    for (const l of labels) {
      // the box the text really covers, from where it is drawn and its measured width
      const w = measure(l.text, LABEL.size * u) + 2 * HALO * u;
      const x0 = l.anchor === 'start' ? l.x - HALO * u : l.anchor === 'end' ? l.x + HALO * u - w : l.x - w / 2;
      const r = [x0, l.y - LABEL.size * u * 0.6, x0 + w, l.y + LABEL.size * u * 0.6];
      assert.ok(r[0] >= box[0] && r[2] <= box[0] + box[2] && r[1] >= box[1] && r[3] <= box[1] + box[3], `${zoom}: ${l.text} leaves the frame`);
      for (const pin of pins) {
        const reach = pinReach(pin.p.id === here) * u;
        const nx = Math.max(r[0], Math.min(pin.xy[0], r[2]));
        const ny = Math.max(r[1], Math.min(pin.xy[1], r[3]));
        assert.ok(Math.hypot(nx - pin.xy[0], ny - pin.xy[1]) >= reach - 1e-6, `${zoom}: «${l.text}» touches ${pin.p.id}`);
      }
      if (l.text.endsWith('…')) assert.ok(Array.from(l.text).length - 1 >= CUT_MIN, `${zoom}: «${l.text}»`);
    }
  }
  // the map measures where it can, before paint, and falls back to the estimate
  const map = fs.readFileSync(path.join(WEB_ROOT, 'components/quartier/QuartierMap.tsx'), 'utf8');
  assert.match(map, /measureText/);
  assert.match(map, /labelsFor\(pins, box, here, measure, whole\)/);
});

/* ---- 5 · an ending in one language ---------------------------------------------------------- */

test('5 · an ending that turns French halfway, or a French line in German, is left out', () => {
  const { frenchOrNothing, nativeOrNothing } = require('@/lib/line-language.ts');
  // stored on day 3 (summary_native) and day 4 (callback_fr) of the walk
  const day3 = 'Du fliegst am Mittwoch nach Hause und möchtest morgen mit Gus sprechen. Lila behält das im Kopf und reste avec toi dans l’attente des prochaines nouvelles.';
  const day4 = 'Tu hast gesagt, dass dir kalt ist; Marin hat eine Suppe und eine Wärmflasche gebracht.';
  assert.equal(nativeOrNothing(day3), '');
  assert.equal(frenchOrNothing(day4), '');
  // one language throughout stays, quotations included
  assert.equal(nativeOrNothing('Du hast Camille «Pas ce soir» gesagt.'), 'Du hast Camille «Pas ce soir» gesagt.');
  assert.equal(nativeOrNothing('You stayed at Chez Maître Vasseur and kept the letter.'), 'You stayed at Chez Maître Vasseur and kept the letter.');
  assert.equal(frenchOrNothing('Le chat ne décide pas ; tu pars mercredi.'), 'Le chat ne décide pas ; tu pars mercredi.');
  assert.equal(nativeOrNothing('Le chat ne décide pas. Tu restes.'), 'Le chat ne décide pas. Tu restes.', 'a French summary on a French-chrome day');
  // where the endings are read
  const { storyFinaleStage } = require('@/components/atelier-v2/journey/story-episode-model.ts');
  const fin = storyFinaleStage('end', { character_line_fr: 'Alors, tu pars mercredi.', summary_native: day3 }, { id: 'lila_bonnet', name: 'Lila' });
  assert.equal(fin.finale.summary, '');
  const recap = fs.readFileSync(path.join(WEB_ROOT, 'components/atelier-v2/journey/journey-recap-model.ts'), 'utf8');
  assert.match(recap, /lineFr: frenchOrNothing\(recap\.story_outcome\?\.callback_fr\) \|\| null/);
});
