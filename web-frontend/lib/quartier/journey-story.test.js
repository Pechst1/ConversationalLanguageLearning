// node --test lib/quartier/journey-story.test.js
//
// Le Quartier · today's journey as the story the quarter stages (`journey-story.ts`): the page off
// the scene step, what /quartier does with each state of the day, and the journey moved on the
// way the Feuilleton moves it (the scene acknowledged before the first answer, each answer an
// attempt at the revision the last one handed back, help recorded, the day closed once).

const assert = require('node:assert/strict');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));

const resolve = Module._resolveFilename;
Module._resolveFilename = function alias(request, ...rest) {
  if (typeof request === 'string' && request.startsWith('@/')) return resolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  return resolve.call(this, request, ...rest);
};
// the axios transport is never reached: every test hands the story its own service
const apiPath = Module._resolveFilename('@/services/api', module, false);
require.cache[apiPath] = { id: apiPath, filename: apiPath, loaded: true, exports: { __esModule: true, default: {}, apiService: {} } };

const { JourneyStory, StoryLost, blockedPage, pageOfJourney, pageOfStage, stagedPageOf, todayOf } = require('./journey-story.ts');

const line = (who, text_fr, extra = {}) => ({ who, name: null, kind: who === 'caption' ? 'caption' : 'speech', mood: 'neutral', direction: null, text_fr, text_native: null, ...extra });

/** A page as the server resolves it (`steps[kind=scene].prompt.stage`). */
const STAGE = {
  season_id: 's1',
  segment: 't1',
  day: 'a',
  key: 't1.a',
  number: 1,
  title_fr: 'Le mauvais accueil',
  story_date_fr: 'mercredi 11 novembre',
  location_id: 'le_mistral',
  can_do_native: 'Say who you are and why you came.',
  band: 'A2',
  language: 'en',
  movements: [
    { kind: 'panel', id: 'a.p1', location_id: 'quai_de_valmy', in_frame: ['toi'], visual: 'Night rain.', silence: false, lines: [line('caption', 'Paris. Le 11 novembre.', { text_native: 'Paris. 11 November.' })] },
    { kind: 'turn', id: 'a.turn1', to: 'augustin_de_roncourt', to_name: 'Gus', task_native: 'Tell Gus who you are.', choice: false, only_after: null, panel: { kind: 'panel', id: 'a.p6', lines: [line('augustin_de_roncourt', 'Et vous êtes ?')] } },
    { kind: 'turn', id: 'a.cafe', to: 'margaux_barman', to_name: 'Margaux', task_native: 'The cup in front of you.', choice: true, only_after: { 'a.turn1': ['a', 'c'] }, panel: { kind: 'panel', id: 'a.cafe.p', lines: [] } },
    { kind: 'solve', id: 'a.enquete' },
    { kind: 'panel', lines: [] },
    { kind: 'hook', id: 'a.hook', role: 'midpoint', panel: { kind: 'panel', id: 'a.p8', lines: [line('camille_marchand', 'Bonsoir.')] } },
  ],
  storylets: [
    { id: 'walk_out', cue: 'walk_out', who: 'margaux_barman', after_seconds: null, lines: [{ role: 'asked', during: null, ...line('margaux_barman', 'Tu pars déjà ?') }, { role: 'back', during: 'a.p2', ...line('augustin_de_roncourt', 'Bon. Où en étais-je ?') }], chips: [], people: [] },
    { id: 'margaux_text', cue: 'away', who: 'margaux_barman', after_seconds: 40, lines: [{ role: 'text', from_fr: 'Numéro inconnu', kind: 'sms', text_fr: 'C’est Margaux. Ta valise est toujours là.' }], chips: ['J’arrive.'], people: [] },
    { id: 'talk', cue: 'talk', who: null, after_seconds: null, lines: [], chips: [], people: [{ who: 'margaux_barman', name: 'Margaux', register: 'tu', bye: null }, { who: 'augustin_de_roncourt', name: 'Gus', register: 'vous', hello: line('augustin_de_roncourt', 'Ah, vous revoilà.') }] },
  ],
};

const TARGETS = [
  { id: 'l1', kind: 'lexeme', label_fr: 'la petite-fille', label_native: 'the granddaughter', concept_title: false },
  { id: 'l2', kind: 'lexeme', label_fr: 'la clé', label_native: 'the key', concept_title: false },
  { id: 'c1', kind: 'concept', label_fr: 'Se présenter', label_native: null, concept_title: true },
];

/** Today's journey: the scene, its talk, the ending, and the words after it. */
function journey({ revision = 3, status = 'active', current = 'scene', turn = 0, talk = 'active', help = ['hint', 'suggested_response'], choices = [], pending = false, stage = STAGE } = {}) {
  const at = ['scene', 'talk', 'end', 'words'].indexOf(current);
  const state = (i) => (current === null || i < at ? 'completed' : i === at ? 'active' : 'pending');
  return {
    id: 'j1',
    revision,
    status,
    current_step_id: current,
    steps: [
      { id: 'scene', kind: 'scene', ordinal: 0, status: state(0), prompt: { objective_native: 'Meet the regulars.', stage } },
      {
        id: 'talk',
        kind: 'respond',
        ordinal: 1,
        status: current === 'talk' ? talk : state(1),
        prompt: { turn_index: turn, help_available: help, targets: TARGETS, choices, objective_native: 'Say who you are.', character_line_fr: 'Et vous êtes ?' },
      },
      { id: 'end', kind: 'resolution', ordinal: 2, status: state(2), prompt: { story_pending: pending } },
      { id: 'words', kind: 'recall', ordinal: 3, status: state(3), prompt: {} },
    ],
  };
}

/** A service that answers each call from `handlers` and keeps the calls. */
function service(handlers) {
  const calls = [];
  const svc = {};
  for (const m of ['get', 'resume', 'advance', 'attempt', 'help', 'finish', 'choose']) {
    svc[m] = async (...args) => {
      calls.push({ m, args });
      if (!handlers[m]) throw new Error(`unexpected ${m}`);
      return handlers[m](...args);
    };
  }
  return { svc, calls, of: (m) => calls.filter((c) => c.m === m) };
}

const conflict = (code = 'journey_version_conflict') => Object.assign(new Error(code), { response: { status: 409, data: { detail: { code, message: code } } } });
const noSleep = async () => undefined;

function storyOn(j, handlers, opts = {}) {
  const s = service(handlers);
  const snapshots = [];
  const story = new JourneyStory(j, pageOfJourney(j), { service: s.svc, sleep: noSleep, onSnapshot: (x) => snapshots.push(x.revision), ...opts });
  return { story, ...s, snapshots };
}

/** A day the story engine wrote: a rule first, then the scene's panels, then the talk with Lila. */
function written({ revision = 3, current = 'rule', turn = 0 } = {}) {
  const order = ['rule', 'scene', 'talk', 'end'];
  const at = order.indexOf(current);
  const state = (i) => (i < at ? 'completed' : i === at ? 'active' : 'pending');
  return {
    id: 'j2',
    revision,
    status: 'active',
    local_date: '2026-10-30',
    edition_no: 17,
    current_step_id: current,
    scenario: { title_fr: 'La clé d’Odile', location_id: 'le_mistral', objective_native: 'Ask Lila about the key.' },
    steps: [
      { id: 'rule', kind: 'rule', ordinal: 0, status: state(0), prompt: {} },
      {
        id: 'scene',
        kind: 'scene',
        ordinal: 1,
        status: state(1),
        prompt: {
          objective_native: 'Ask Lila about the key.',
          setup_fr: 'Le soir, au Mistral.',
          stage: null,
          panels: [
            { id: 'p1', index: 0, narration_fr: 'Le soir tombe sur le quai.', dialogue: [] },
            { id: 'p2', index: 1, narration_fr: '', dialogue: [{ character_id: 'lila_bonnet', character_name: 'Lila', mood: 'happy', text_fr: 'Tu as la clé ?', text_native: 'Do you have the key?' }, { character_id: 'marin_leveque', character_name: 'Marin', mood: null, text_fr: ' ', text_native: null }] },
            { id: 'p3', index: 2, narration_fr: '', dialogue: [] },
          ],
        },
      },
      { id: 'talk', kind: 'respond', ordinal: 2, status: state(2), prompt: { turn_index: turn, help_available: ['hint'], targets: TARGETS, choices: [], objective_native: 'Tell Lila where the key is.', character_id: 'lila_bonnet', character_name: 'Lila', character_line_fr: 'Alors, elle est où ?' } },
      { id: 'end', kind: 'resolution', ordinal: 3, status: state(3), prompt: { story_pending: false } },
    ],
  };
}

test('a scene the engine wrote today is a page the quarter plays: its panels, then the talk', () => {
  const page = pageOfJourney(written());
  assert.equal(page.key, 'jour.2026-10-30');
  assert.equal(page.number, 17);
  assert.equal(page.title_fr, 'La clé d’Odile');
  assert.equal(page.can_do_native, 'Ask Lila about the key.');
  assert.deepEqual(page.movements.map((m) => [m.kind, m.id]), [['panel', 'jour.p1'], ['panel', 'jour.p2'], ['turn', 'jour.talk']], 'an empty panel and an empty line are left out');
  assert.deepEqual(page.movements[0].lines.map((l) => [l.who, l.kind, l.text_fr]), [['caption', 'caption', 'Le soir tombe sur le quai.']]);
  assert.deepEqual(page.movements[1].lines.map((l) => [l.who, l.name, l.mood, l.text_native]), [['lila_bonnet', 'Lila', 'happy', 'Do you have the key?']]);
  assert.deepEqual(page.movements[1].in_frame, ['lila_bonnet']);
  const talk = page.movements[2];
  assert.deepEqual([talk.to, talk.to_name, talk.task_native, talk.choice], ['lila_bonnet', 'Lila', 'Tell Lila where the key is.', false]);
  assert.deepEqual(talk.panel.lines.map((l) => [l.who, l.text_fr]), [['lila_bonnet', 'Alors, elle est où ?']]);
  assert.deepEqual(page.storylets, []);
  assert.equal(blockedPage(page), false);
  assert.equal(blockedPage(pageOfStage(STAGE)), true);
});

test('a talk the engine keeps open goes on turn after turn, then closes', async () => {
  const said = (revision, turn, text, open) => ({
    pending: false,
    journey: written({ revision, current: 'talk', turn }),
    correction: null,
    character_lines: [{ speaker_id: 'lila_bonnet', speaker_name: 'Lila', text_fr: text }],
    next_turn: open ? { step_id: 'talk' } : null,
    stage: null,
  });
  const replies = [said(5, 1, 'Sous le paillasson ? Vraiment ?', true), said(6, 2, 'Bon. Merci !', false)];
  const { story } = storyOn(written({ current: 'scene' }), { advance: async () => written({ revision: 4, current: 'talk' }), attempt: async () => replies.shift() });
  const first = await story.answer('jour.talk', 'Elle est sous le paillasson.');
  assert.deepEqual([first.next, first.goesOn, first.reply], ['jour.talk', true, null]);
  assert.deepEqual(first.beats[0].lines.map((l) => [l.who, l.text_fr]), [['lila_bonnet', 'Sous le paillasson ? Vraiment ?']]);
  const last = await story.answer('jour.talk', 'Oui, vraiment.');
  assert.deepEqual([last.next, last.goesOn, last.closing], [null, false, true]);
  assert.notEqual(first.beats[0].id, last.beats[0].id, 'each turn’s lines are their own beat');
});

test('the scene picks the day up where the warm-up left it', async () => {
  const { story, of } = storyOn(written({ current: 'rule' }), { advance: async () => written({ revision: 6, current: 'talk' }) });
  story.follow(written({ revision: 2, current: 'rule' }));
  assert.equal(story.snapshot.revision, 3, 'an older read is not taken');
  story.follow(written({ revision: 5, current: 'scene' }));
  await story.ask('jour.talk');
  assert.deepEqual(of('advance').map((c) => [c.args[1].currentStepId, c.args[1].expectedRevision]), [['scene', 5]]);
});

test('the page off the scene step: what the quarter can stage, field by field', () => {
  const page = pageOfStage(STAGE);
  assert.equal(page.key, 't1.a');
  assert.equal(page.number, 1);
  assert.equal(page.can_do_native, 'Say who you are and why you came.');
  assert.deepEqual(page.movements.map((m) => m.id), ['a.p1', 'a.turn1', 'a.cafe', 'a.hook'], 'what is not a page movement is left out');
  const cafe = page.movements[2];
  assert.equal(cafe.choice, true);
  assert.deepEqual(cafe.only_after, { 'a.turn1': ['a', 'c'] });
  assert.equal(page.movements[0].lines[0].text_native, 'Paris. 11 November.');
  const text = page.storylets.find((s) => s.id === 'margaux_text');
  assert.equal(text.lines[0].who, 'margaux_barman', 'a line without a speaker is the storylet’s');
  assert.equal(text.lines[0].from_fr, 'Numéro inconnu');
  const people = page.storylets.find((s) => s.id === 'talk').people;
  assert.deepEqual(people.map((p) => [p.who, p.register, p.hello?.text_fr ?? null]), [['margaux_barman', 'tu', null], ['augustin_de_roncourt', 'vous', 'Ah, vous revoilà.']]);
  assert.equal(pageOfStage(null), null);
  assert.equal(pageOfStage({ key: 't1.a', movements: [{ kind: 'solve', id: 'x' }] }), null);
  assert.equal(pageOfJourney(journey({ stage: null })).key, 'jour.j1', 'off an authored page: the scene written today');
  assert.equal(pageOfJourney({ ...journey({ stage: null }), steps: journey({ stage: null }).steps.filter((x) => x.kind !== 'respond') }), null, 'nothing to answer, nothing to play');
});

test('what /quartier does with each state of the day', () => {
  const kind = (j) => {
    const t = todayOf(j);
    return t.kind === 'handoff' ? `handoff:${t.why}` : t.kind;
  };
  assert.equal(kind(null), 'start');
  assert.equal(kind(journey({ status: 'preparing' })), 'preparing');
  assert.equal(kind(journey({ status: 'completed', current: null })), 'done');
  assert.equal(kind(journey({ status: 'ended_early', current: null })), 'done');
  assert.equal(kind(journey({ status: 'unavailable' })), 'handoff:unavailable');
  assert.equal(kind(journey({ stage: null })), 'play', 'off an authored page: the scene written today');
  assert.equal(kind(journey({ stage: { ...STAGE, key: 't1.b' } })), 'play', 'a day with no blocking');
  assert.equal(kind(written({ current: 'rule' })), 'before', 'a warm-up before the scene, over the quarter');
  assert.equal(kind(written({ current: 'scene' })), 'play');
  assert.equal(kind({ ...journey(), steps: journey().steps.filter((x) => x.kind !== 'scene') }), 'handoff:day', 'a day without a scene');
  assert.equal(kind(journey()), 'play');
  assert.equal(kind(journey({ status: 'paused' })), 'play');
  assert.equal(kind(journey({ current: 'talk' })), 'play', 'nothing answered yet');
  assert.equal(kind(journey({ current: 'talk', turn: 2 })), 'handoff:midway');
  assert.equal(kind(journey({ current: 'talk', turn: 3, talk: 'completed' })), 'practice', 'answered, not yet acknowledged');
  assert.equal(kind(journey({ current: 'end' })), 'practice');
  assert.equal(kind(journey({ current: 'words' })), 'practice');
  assert.equal(kind(journey({ current: null })), 'practice', 'every step done, the day not yet finished');
});

test('a day the quarter stages keeps its page wherever it stands: its people talk through the engine all day', () => {
  for (const j of [journey(), journey({ current: 'talk', turn: 2 }), journey({ current: 'words' }), journey({ status: 'completed', current: null })]) {
    assert.equal(stagedPageOf(j)?.key, 't1.a', `${j.status} at ${j.current_step_id}`);
  }
  assert.equal(stagedPageOf(journey({ stage: { ...STAGE, key: 't1.b' } }))?.key, 't1.b', 'a day with no blocking plays as written');
  assert.equal(stagedPageOf(journey({ stage: null }))?.key, 'jour.j1');
  assert.equal(stagedPageOf(null), null);
});

test('the first question acknowledges the scene, and offers help in steps', async () => {
  const { story, of, snapshots } = storyOn(journey(), { advance: async () => journey({ revision: 4, current: 'talk' }) });
  const ask = await story.ask('a.turn1');
  assert.equal(of('advance').length, 1);
  assert.deepEqual(of('advance')[0].args.slice(0, 1), ['j1']);
  assert.equal(of('advance')[0].args[1].currentStepId, 'scene');
  assert.equal(of('advance')[0].args[1].expectedRevision, 3);
  assert.deepEqual(ask, { task: 'Tell Gus who you are.', help: ['hint', 'words', 'example'] });
  assert.deepEqual(snapshots, [4]);
  // asked again: the scene is not acknowledged twice
  await story.ask('a.turn1');
  assert.equal(of('advance').length, 1);
});

test('an answer is an attempt at the revision the last call handed back, read back as the room plays it', async () => {
  const result = {
    pending: false,
    journey: journey({ revision: 5, current: 'talk', turn: 1 }),
    correction: { span_fr: 'la famille de Odile', corrected_fr: "la famille d'Odile", note_native: 'de becomes d’ before a vowel.' },
    character_lines: [],
    next_turn: { step_id: 'talk' },
    stage: {
      turn_id: 'a.turn1',
      reply_id: 'a',
      beats: [{ kind: 'panel', id: 'a.turn1.ack', lines: [line('augustin_de_roncourt', 'Ah ! La famille !')] }, { kind: 'panel', id: 'a.turn1.a.r1', silence: true, lines: [] }],
      next_turn_id: 'a.cafe',
      closing: false,
    },
  };
  const { story, of } = storyOn(journey(), { advance: async () => journey({ revision: 4, current: 'talk' }), attempt: async () => result });
  const heard = await story.answer('a.turn1', 'Je suis la famille de Odile.');
  const [jid, sid, body] = of('attempt')[0].args;
  assert.deepEqual([jid, sid, body.expectedRevision, body.input], ['j1', 'talk', 4, { mode: 'text', text: 'Je suis la famille de Odile.' }]);
  assert.equal(heard.turn, 'a.turn1');
  assert.equal(heard.reply, 'a');
  assert.deepEqual(heard.beats.map((b) => [b.id, Boolean(b.silence)]), [['a.turn1.ack', false], ['a.turn1.a.r1', true]]);
  assert.equal(heard.next, 'a.cafe');
  assert.equal(heard.closing, false);
  assert.deepEqual(heard.mend, { span: 'la famille de Odile', corrected: "la famille d'Odile", note: 'de becomes d’ before a vowel.' });
  assert.equal(story.snapshot.revision, 5);
});

test('grading that did not happen is sent again as it was, then said', async () => {
  let n = 0;
  const graded = { pending: false, journey: journey({ revision: 5, current: 'talk', turn: 1 }), correction: null, character_lines: [], next_turn: null, stage: { turn_id: 'a.turn1', reply_id: 'b', beats: [], next_turn_id: null, closing: true } };
  const { story, of } = storyOn(journey({ revision: 4, current: 'talk' }), {
    attempt: async () => (++n < 3 ? { pending: true, journey: journey({ revision: 4, current: 'talk' }) } : graded),
  });
  const heard = await story.answer('a.turn1', 'Je vends.');
  const sent = of('attempt').map((c) => c.args[2]);
  assert.equal(sent.length, 3);
  assert.equal(new Set(sent.map((b) => b.mutationId)).size, 1, 'the same key each time');
  assert.deepEqual(sent.map((b) => b.expectedRevision), [4, 4, 4]);
  assert.equal(heard.closing, true);

  const stuck = storyOn(journey({ revision: 4, current: 'talk' }), { attempt: async () => ({ pending: true, journey: journey({ revision: 4, current: 'talk' }) }) });
  await assert.rejects(stuck.story.answer('a.turn1', 'Je vends.'), /grading_pending/);
});

test('a conflict reads the journey again: the same question is sent again, a moved talk is lost', async () => {
  const graded = { pending: false, journey: journey({ revision: 7, current: 'talk', turn: 1 }), correction: null, character_lines: [], next_turn: null, stage: { turn_id: 'a.turn1', reply_id: 'c', beats: [], next_turn_id: 'a.cafe', closing: false } };
  let first = true;
  const again = storyOn(journey({ revision: 4, current: 'talk' }), {
    attempt: async () => {
      if (first) {
        first = false;
        throw conflict();
      }
      return graded;
    },
    get: async () => journey({ revision: 6, current: 'talk' }),
  });
  const heard = await again.story.answer('a.turn1', 'Bonsoir.');
  const sent = again.of('attempt').map((c) => c.args[2]);
  assert.deepEqual(sent.map((b) => b.expectedRevision), [4, 6]);
  assert.notEqual(sent[0].mutationId, sent[1].mutationId, 'a new key for the journey as it now stands');
  assert.equal(heard.reply, 'c');

  let lost = 0;
  const moved = storyOn(
    journey({ revision: 4, current: 'talk' }),
    { attempt: async () => Promise.reject(conflict()), get: async () => journey({ revision: 6, current: 'talk', turn: 1 }) },
    { onLost: () => lost++ },
  );
  await assert.rejects(moved.story.answer('a.turn1', 'Bonsoir.'), StoryLost);
  assert.equal(lost, 1);
  assert.equal(moved.of('attempt').length, 1, 'never sent to a question already answered');
});

test('help: the hint and the example are recorded, the words are the talk’s own', async () => {
  const { story, of } = storyOn(journey({ revision: 4, current: 'talk' }), {
    help: async (_j, _s, o) => ({ content_fr: o.helpKind === 'suggested_response' ? "Je suis la petite-fille d'Odile." : null, content_native: o.helpKind === 'hint' ? 'Say how you know Odile.' : null, journey: journey({ revision: 5, current: 'talk' }) }),
  });
  assert.deepEqual(await story.help('a.turn1', 'hint'), { step: 'hint', text: null, native: 'Say how you know Odile.', words: [] });
  assert.deepEqual(await story.help('a.turn1', 'words'), { step: 'words', text: null, native: null, words: ['la petite-fille', 'la clé'] });
  const example = await story.help('a.turn1', 'example');
  assert.equal(example.text, "Je suis la petite-fille d'Odile.");
  assert.deepEqual(of('help').map((c) => [c.args[1], c.args[2].helpKind, c.args[2].expectedRevision]), [['talk', 'hint', 4], ['talk', 'suggested_response', 5]]);

  // the café crème, once the engine asks it: a choice, whose words are its options
  const choices = [{ id: 'drink', label_fr: 'Merci.', label_native: null }, { id: 'declined', label_fr: 'Non merci.', label_native: null }];
  const toCafe = { pending: false, journey: journey({ revision: 5, current: 'talk', turn: 1, help: [], choices }), correction: null, character_lines: [], next_turn: { step_id: 'talk' }, stage: { turn_id: 'a.turn1', reply_id: 'a', beats: [], next_turn_id: 'a.cafe', closing: false } };
  const choice = storyOn(journey({ revision: 4, current: 'talk' }), { attempt: async () => toCafe });
  await choice.story.answer('a.turn1', "Je suis la petite-fille d'Odile.");
  assert.deepEqual((await choice.story.ask('a.cafe')).help, ['words']);
  assert.deepEqual((await choice.story.help('a.cafe', 'words')).words, ['Merci.', 'Non merci.']);
  assert.equal(await choice.story.help('a.cafe', 'example'), null, 'no example on offer: nothing asked');
  assert.equal(choice.of('help').length, 0);
});

test('a question the engine is not asking is never answered here: the Feuilleton has it', async () => {
  const graded = { pending: false, journey: journey({ revision: 5, current: 'talk', turn: 1 }), correction: null, character_lines: [], next_turn: { step_id: 'talk' }, stage: { turn_id: 'a.turn1', reply_id: 'a', beats: [], next_turn_id: 'a.cafe', closing: false } };
  let lost = 0;
  const { story, of } = storyOn(journey({ revision: 4, current: 'talk' }), { attempt: async () => graded }, { onLost: () => lost++ });
  await story.answer('a.turn1', "Je suis la famille d'Odile.");
  // the scene played again from the top (a ride across the map and back): Gus asks again, while the engine asks the café crème
  await assert.rejects(story.ask('a.turn1'), StoryLost);
  await assert.rejects(story.help('a.turn1', 'hint'), StoryLost);
  await assert.rejects(story.answer('a.turn1', "Je suis la famille d'Odile."), StoryLost);
  assert.equal(lost, 3);
  assert.equal(of('attempt').length, 1, 'the answer to Gus is never graded as the café crème');
  assert.equal(of('help').length, 0);

  // a talk already past its first question is not picked up here at all
  const midway = storyOn(journey({ revision: 6, current: 'talk', turn: 2 }), {});
  await assert.rejects(midway.story.ask('a.turn1'), StoryLost);
  assert.equal(midway.calls.length, 0);
});

test('a gesture goes to the engine as it was made, and comes back as panels and flags', async () => {
  const { story, of } = storyOn(journey({ revision: 4, current: 'talk' }), {
    choose: async (_j, o) => ({
      contract_version: 1,
      storylet_id: o.storyletId,
      beats: [{ kind: 'panel', id: 'talk.margaux.odile', lines: [line('margaux_barman', 'Tous les matins, au bout du zinc.')] }],
      chips: ['Pourquoi elle est partie ?'],
      heard: 'margaux.odile',
      learned: [{ id: 'margaux.odile', text_fr: 'Odile prenait un café crème tous les matins.', text_native: 'Odile had a café crème every morning.' }, { id: 7 }],
      sets: { 'user.walked_out': true, 's1.nothing': null },
    }),
  });
  const a = await story.gesture({ storylet: 'talk', to: 'margaux_barman', text: 'Tu connaissais bien Odile ?' });
  assert.deepEqual(of('choose')[0].args[1].storyletId, 'talk');
  assert.equal(of('choose')[0].args[1].to, 'margaux_barman');
  assert.equal(of('choose')[0].args[1].text, 'Tu connaissais bien Odile ?');
  assert.ok(of('choose')[0].args[1].mutationId);
  assert.equal(a.heard, 'margaux.odile');
  assert.deepEqual(a.learned.map((l) => l.id), ['margaux.odile']);
  assert.deepEqual(a.sets, { 'user.walked_out': true });
  assert.equal(a.beats[0].lines[0].text_fr, 'Tous les matins, au bout du zinc.');
  await story.gesture({ storylet: 'walk_out', at: 'a.p2' });
  assert.equal(of('choose')[1].args[1].at, 'a.p2');
  assert.equal(of('choose')[1].args[1].text, undefined);
  assert.equal(of('advance').length + of('attempt').length, 0, 'a gesture does not move the journey');

  const down = storyOn(journey(), { choose: async () => Promise.reject(new Error('offline')) });
  assert.equal(await down.story.gesture({ storylet: 'margaux_text', text: 'J’arrive.' }), null);
});

test('closing the day: the talk and the ending acknowledged, a day with nothing left finished, once', async () => {
  const steps = { talk: journey({ revision: 8, current: 'end' }), end: { ...journey({ revision: 9, current: null }) } };
  const { story, of } = storyOn(journey({ revision: 7, current: 'talk', turn: 3, talk: 'completed' }), {
    advance: async (_j, o) => steps[o.currentStepId],
    finish: async () => ({ ...journey({ revision: 10, current: null }), status: 'completed' }),
  });
  await Promise.all([story.close(), story.close()]);
  assert.deepEqual(of('advance').map((c) => [c.args[1].currentStepId, c.args[1].expectedRevision]), [['talk', 7], ['end', 8]]);
  assert.deepEqual(of('finish').map((c) => [c.args[1].finishKind, c.args[1].expectedRevision]), [['complete', 9]]);
  assert.equal(story.snapshot.status, 'completed');

  // the words are still to come: the day stays open for them
  const words = storyOn(journey({ revision: 7, current: 'talk', turn: 3, talk: 'completed' }), {
    advance: async (_j, o) => (o.currentStepId === 'talk' ? journey({ revision: 8, current: 'end' }) : journey({ revision: 9, current: 'words' })),
  });
  await words.story.close();
  assert.deepEqual(words.of('advance').map((c) => c.args[1].currentStepId), ['talk', 'end']);
  assert.equal(words.of('finish').length, 0);

  // an ending still being written is the Feuilleton's to wait for
  const writing = storyOn(journey({ revision: 7, current: 'talk', turn: 3, talk: 'completed' }), { advance: async () => journey({ revision: 8, current: 'end', pending: true }) });
  await writing.story.close();
  assert.deepEqual(writing.of('advance').map((c) => c.args[1].currentStepId), ['talk']);
});

/* ---- one T1 day a through the real engine, as the story engine's own tests recorded it ---- */

const RECORDED = require('./fixtures/t1a-journey.json');

/**
 * The engine as recorded (`fixtures/t1a-journey.json`): each call is answered by the next recorded
 * one of its kind, sent as it was recorded. What the recording leaves out follows from what it
 * has: advancing a step, and the snapshots it elides after the first (the talk as the next
 * question leaves it).
 */
function replay() {
  const calls = RECORDED.calls.filter((c) => c.call);
  const of = (end) => calls.filter((c) => c.call.endsWith(end));
  const created = calls[0].response;
  const queue = { attempts: of('/attempts'), choices: of('/choices'), finish: of('/finish') };
  const now = structuredClone(created);
  const sent = [];
  const refused = (r) => Object.assign(new Error(r.detail.code), { response: { status: 409, data: r } });
  const next = (q) => {
    assert.ok(queue[q].length, `no ${q} call left in the recording`);
    return queue[q].shift();
  };
  const svc = {
    get: async () => structuredClone(now),
    advance: async (_j, o) => {
      assert.deepEqual([o.currentStepId, o.expectedRevision], [now.current_step_id, now.revision]);
      const steps = [...now.steps].sort((a, b) => a.ordinal - b.ordinal);
      const i = steps.findIndex((s) => s.id === o.currentStepId);
      steps[i].status = 'completed';
      if (steps[i + 1]) steps[i + 1].status = 'active';
      now.current_step_id = steps[i + 1]?.id ?? null;
      now.revision += 1;
      sent.push(['advance', steps[i].kind]);
      return structuredClone(now);
    },
    attempt: async (_j, stepId, o) => {
      const c = next('attempts');
      assert.deepEqual([o.expectedRevision, o.input.text], [c.body.expected_revision, c.body.input.text]);
      sent.push(['attempt', o.input.text]);
      const r = c.response;
      const talk = now.steps.find((s) => s.id === stepId);
      if (r.next_turn) talk.prompt = { ...talk.prompt, ...r.next_turn.prompt };
      else talk.status = 'completed';
      Object.assign(now, { revision: r.journey.revision, status: r.journey.status, current_step_id: r.journey.current_step_id });
      return { ...structuredClone(r), journey: structuredClone(now) };
    },
    finish: async (_j, o) => {
      const c = next('finish');
      assert.deepEqual([o.expectedRevision, o.finishKind], [c.body.expected_revision, c.body.finish_kind]);
      sent.push(['finish']);
      Object.assign(now, { revision: c.response.revision, status: c.response.status, current_step_id: c.response.current_step_id });
      return structuredClone(now);
    },
    choose: async (_j, o) => {
      const c = next('choices');
      const body = (b) => ({ storylet_id: b.storylet_id, at: b.at ?? null, to: b.to ?? null, text: b.text ?? null });
      assert.deepEqual(body({ storylet_id: o.storyletId, at: o.at, to: o.to, text: o.text }), body(c.body));
      sent.push(['choose', o.storyletId]);
      if (c.status !== 200) throw refused(c.response);
      return structuredClone(c.response);
    },
  };
  return { svc, created, sent, left: () => Object.values(queue).reduce((n, q) => n + q.length, 0) };
}

test('the recorded day: the page the server resolved is one the quarter stages', () => {
  const { STAGED } = require('./stage.ts');
  const { created } = replay();
  assert.equal(todayOf(created).kind, 'play');
  const page = pageOfJourney(created);
  assert.deepEqual([page.key, page.number, page.story_date_fr], ['t1.a', 1, 'mercredi 11 novembre']);
  assert.ok(page.can_do_native);
  const ids = page.movements.map((m) => m.id);
  assert.deepEqual(ids, ['a.p1', 'a.p2', 'a.p3', 'a.p4', 'a.p5', 'a.turn1', 'a.cafe', 'a.turn2', 'a.key', 'a.hook']);
  assert.deepEqual(ids, STAGED.filter((id) => ids.includes(id)), 'the director has blocking for each, in this order');
  for (const id of ['a.cafe', 'a.key']) {
    const choice = page.movements.find((m) => m.id === id);
    assert.equal(choice.choice, true, id);
    assert.equal(choice.panel.id, `${id}.prompt`);
    assert.deepEqual(choice.panel.lines.map((l) => [l.who, l.kind]), [['margaux_barman', 'speech']], `${id}: Margaux asks`);
  }
  assert.deepEqual(page.movements.find((m) => m.id === 'a.cafe').only_after, { 'a.turn1': ['a', 'c'] });
  const hook = page.movements.find((m) => m.kind === 'hook');
  assert.equal(hook.panel.id, 'a.p8');
  assert.ok(hook.panel.lines.length >= 3, 'the hook is whole, «À suivre…» included');
  const walk = page.storylets.find((s) => s.id === 'walk_out');
  assert.equal(walk.lines.find((l) => l.role === 'asked').who, 'margaux_barman');
  assert.ok(walk.lines.some((l) => l.role === 'back' && l.during === 'a.p2'));
  const text = page.storylets.find((s) => s.id === 'margaux_text');
  assert.deepEqual([text.after_seconds, text.lines.find((l) => l.role === 'text').from_fr], [40, 'Numéro inconnu']);
  const people = page.storylets.find((s) => s.id === 'talk').people;
  assert.deepEqual(people.map((p) => [p.who, p.register]), [['margaux_barman', 'tu'], ['augustin_de_roncourt', 'vous'], ['marin_leveque', 'tu'], ['lila_bonnet', 'tu'], ['camille_marchand', 'vous']]);
  assert.ok(people.every((p) => p.hello?.text_fr), 'everyone says something as you come up');
  assert.equal(people.find((p) => p.who === 'lila_bonnet').bye.text_fr, 'Allez, file.');
});

test('the recorded day, played through: every answer and gesture as the engine took it, then closed', async () => {
  const { SILENT_BEATS } = require('./stage.ts');
  const r = replay();
  const page = pageOfJourney(r.created);
  const story = new JourneyStory(r.created, page, { service: r.svc, sleep: noSleep });
  const acted = (beats) => beats.filter((b) => b.silence).every((b) => Object.values(SILENT_BEATS).some((re) => re.test(b.id)));

  // walked out during Gus's story: what the engine keeps is the line for the way back in
  const out = await story.gesture({ storylet: 'walk_out', at: 'a.p2' });
  assert.deepEqual(out.beats.map((b) => b.id), ['walk_out.back.gus']);
  assert.deepEqual(out.sets, { 'user.walked_out': true });
  // a tap on Lila: her hello, the help kept for when it is asked
  const lila = await story.gesture({ storylet: 'talk', to: 'lila_bonnet' });
  assert.deepEqual(lila.beats.map((b) => b.lines[0].who), ['lila_bonnet']);
  assert.ok(lila.chips.length);
  // «tu» to Gus: the slip first
  const gus = await story.gesture({ storylet: 'talk', to: 'augustin_de_roncourt', text: 'Tu viens souvent ici ?' });
  assert.equal(gus.beats[0].id, 'talk.augustin_de_roncourt.slip');

  // the first question acknowledges the scene; this talk has no words to offer, only the hint and an example
  assert.deepEqual(await story.ask('a.turn1'), { task: 'Say who you are and why you are here.', help: ['hint', 'example'] });
  const t1 = await story.answer('a.turn1', "Odile, c'est ma grand-mère.");
  assert.deepEqual([t1.turn, t1.reply, t1.next, t1.closing], ['a.turn1', 'a', 'a.cafe', false]);
  assert.equal(t1.beats[0].id, 'a.turn1.a.r1');
  assert.ok(acted(t1.beats));

  // the café crème, asked as a question: the words are its options
  assert.ok((await story.ask('a.cafe')).help.includes('words'));
  assert.deepEqual((await story.help('a.cafe', 'words')).words, ['Merci.', 'Non merci.', "Je n'ai rien commandé."]);
  const cafe = await story.answer('a.cafe', 'Non, merci. Pas ce soir.');
  assert.deepEqual([cafe.reply, cafe.next], ['declined', 'a.turn2']);
  assert.deepEqual(cafe.beats.map((b) => [b.id, Boolean(b.silence)]), [['a.cafe.declined.r1', true]]);
  assert.ok(acted(cafe.beats));

  // a word with Margaux between questions: what she told, in the learner's language too
  const odile = await story.gesture({ storylet: 'talk', to: 'margaux_barman', text: 'Tu connaissais bien Odile ?' });
  assert.equal(odile.heard, 'margaux.odile');
  assert.deepEqual(odile.learned.map((l) => [l.id, Boolean(l.text_native)]), [['margaux.odile', true]]);
  assert.equal(odile.people.find((p) => p.who === 'lila_bonnet').hello.text_fr, "Salut, l'héritage !", 'the hellos as things now stand');
  // stayed away: the text comes, then the answer to the learner's
  const away = await story.gesture({ storylet: 'margaux_text' });
  assert.deepEqual([away.beats[0].id, away.sets['user.stayed_away']], ['margaux_text.text', true]);
  const bon = await story.gesture({ storylet: 'margaux_text', text: "J'arrive." });
  assert.equal(bon.beats[0].lines[0].text_fr, 'Bon.');

  const t2 = await story.answer('a.turn2', 'Oui. Ce soir.');
  assert.deepEqual([t2.reply, t2.next], ['tonight', 'a.key']);
  // the key closes the talk; the tail comes under the hook's panel, which the hook plays
  const key = await story.answer('a.key', 'Tu peux la garder ?');
  assert.deepEqual([key.reply, key.next, key.closing], ['leave', null, true]);
  assert.deepEqual(key.beats.map((b) => b.id), ['a.key.leave.r1', 'a.p8']);

  await story.close();
  assert.deepEqual(r.sent.filter((c) => c[0] === 'advance' || c[0] === 'finish'), [['advance', 'scene'], ['advance', 'respond'], ['advance', 'resolution'], ['finish']]);
  assert.equal(story.snapshot.status, 'completed');

  // after the end card the room still talks, and Margaux's hello knows where the key is
  const after = await story.gesture({ storylet: 'talk', to: 'margaux_barman' });
  assert.equal(after.beats[0].lines[0].text_fr, 'Elle est derrière la caisse.');
  const why = await story.gesture({ storylet: 'talk', to: 'margaux_barman', text: 'Pourquoi elle est partie ?' });
  assert.equal(why.heard, 'margaux.why_left');
  // a gesture the day does not have is refused, and nothing comes of it
  assert.equal(await story.gesture({ storylet: 'dance' }), null);
  assert.equal(r.left(), 0, 'every recorded call was made, in order');
});
