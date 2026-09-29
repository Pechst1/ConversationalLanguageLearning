// node --test components/atelier-v2/journey/wp103.test.js
//
// WP-103 «Retour d'essai» — the owner's first test, the journey half.
//
//   T3  every drill states its goal (goal_native, else source_fr) under its
//       instruction, and the step header of a drill names the drill — the
//       day's reply objective belongs to the scene and the reply only;
//   T2  the listening cycle: «Afficher le texte» for the page at every stage
//       and per line where the lines are listed; hidden stays the default; the
//       listening question is shown before the audio and again after it;
//   T6  a slip is printed corrected under the learner's line, always visible,
//       and one note per issue, never the same explanation twice;
//   T7  under the latest line: whose turn it is, to whom, how far — in the
//       chrome language; and after the close «Continuer» is the only action.

const assert = require('node:assert/strict');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..', '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (typeof request === 'string' && request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};
const apiPath = Module._resolveFilename('@/services/api', module, false);
require.cache[apiPath] = {
  id: apiPath,
  filename: apiPath,
  loaded: true,
  exports: { __esModule: true, default: {}, apiService: {} },
};

const realConsoleError = console.error;
console.error = (...args) => {
  if (String(args[0] || '').includes('non-boolean attribute')) return;
  realConsoleError(...args);
};

const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

const frame = require('./drill-frame.ts');
const thread = require('./respond-thread.ts');
const radio = require('./story-episode-model.ts');
const steps = require('./JourneySteps.tsx');
const { EpisodeRadioView } = require('./StoryEpisodeReader.tsx');
const { JourneySession } = require('./JourneySession.tsx');
const { journeyCopy } = require('./journey-copy.ts');
const { dedupeNotes, correctionNotes } = require('@/lib/correction-notes.ts');

const EN = journeyCopy('en');
const DE = journeyCopy('de');
const FR = journeyCopy('fr');
const h = React.createElement;
// Typographic spaces (the French «\u202f?») read as ordinary ones, entities as characters.
const decode = (html) =>
  html
    .replace(/&#x27;|&#39;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, '&')
    .replace(/[\u00a0\u202f]/g, ' ');

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function recallStep(extra = {}, target = null) {
  return {
    id: 'step-recall',
    ordinal: 2,
    kind: 'recall',
    status: 'active',
    estimated_seconds: 40,
    assistance_used: [],
    prompt: {
      task_type: 'word_bank',
      instruction_native: 'Build the sentence. Some chips are not needed.',
      prompt_fr: null,
      options: [
        { id: 'a', text_fr: 'Une' },
        { id: 'b', text_fr: 'petite' },
        { id: 'c', text_fr: 'table' },
      ],
      target: target || {
        kind: 'grammar',
        id: 'g-12',
        label_fr: 'Genre et nombre',
        label_native: 'Gender and number',
      },
      optional: false,
      help_available: [],
      ...extra,
    },
  };
}

const commonProps = (step, extra = {}) => ({
  step,
  copy: EN,
  busy: false,
  feedback: { kind: 'idle' },
  help: null,
  onHelp() {},
  onSubmit() {},
  onContinue() {},
  ...extra,
});

const SCENARIO = {
  scenario_key: 's',
  content_version: '1',
  title_fr: 'Le Mistral',
  objective_key: 'o',
  objective_native: 'Ask Romy if she wants to sit with you.',
  level_band: 'A1',
  character_id: 'romy_tremblay',
  character_name: 'Romy',
  location_id: 'le_mistral',
  location_name: 'Le Mistral',
  image_url: null,
  serial_thread_id: null,
  serial_episode_id: null,
  estimated_seconds: 300,
};

function journeyWith(stepList, currentId) {
  return {
    id: 'journey-1',
    status: 'active',
    revision: 3,
    current_step_id: currentId,
    scenario: SCENARIO,
    steps: stepList,
    day_shape: 'standard',
  };
}

function controllerFor(journey, step, extra = {}) {
  return {
    phase: { kind: 'session', journey, step },
    feedback: { kind: 'idle' },
    envelope: null,
    journey,
    step,
    respondPrompt: null,
    controlLanguage: 'en',
    legacyResume: null,
    progress: { done: 0, total: journey.steps.length },
    busy: false,
    help: null,
    voice: { kind: 'idle' },
    recovery: null,
    actions: new Proxy({}, { get: () => () => Promise.resolve() }),
    ...extra,
  };
}

const respondPrompt = (extra = {}) => ({
  turn_index: 0,
  max_turns: 3,
  repair_allowed: true,
  character_id: 'marin_leveque',
  character_name: 'Marin',
  character_line_fr: 'Tu veux t’asseoir ?',
  character_line_audio_url: null,
  objective_native: 'Ask Romy if she wants to sit with you.',
  input_modes: ['text'],
  targets: [],
  help_available: [],
  ...extra,
});

const respondStep = (extra = {}) => ({
  id: 'step-respond',
  ordinal: 3,
  kind: 'respond',
  status: 'active',
  estimated_seconds: 120,
  assistance_used: [],
  prompt: respondPrompt(extra),
});

const attemptResult = (extra = {}) => ({
  contract_version: 1,
  evidence_ref: 'ev-1',
  task_outcome: 'met',
  assistance_level: 'none',
  correction: null,
  character_reply_fr: 'Avec plaisir. Installez-vous.',
  reply_source: 'model',
  next_turn: null,
  pending: false,
  journey: {},
  ...extra,
});

const gradedFeedback = (result, verdict = 'correct') => ({ kind: 'graded', verdict, result, replySource: 'model' });

// ===========================================================================
// T3 — the goal line
// ===========================================================================

test('T3 · a drill’s goal is goal_native, else the scene line it is cut from', () => {
  const goal = 'Build: "A small white table is in the kitchen."';
  assert.deepEqual(frame.drillGoalLine({ goal_native: goal, source_fr: 'Une petite table blanche est dans la cuisine.' }), {
    kind: 'goal',
    text: goal,
  });
  assert.deepEqual(frame.drillGoalLine({ goal_native: '', source_fr: '  Une petite   table blanche. ' }), {
    kind: 'source',
    text: 'Une petite table blanche.',
  });
  assert.equal(frame.drillGoalLine({}), null, 'an older payload states nothing');
  assert.equal(frame.drillGoalLine(null), null);
  assert.equal(frame.drillGoalLine({ goal_native: '   ', source_fr: null }), null);
});

test('T3 · a goal the screen already says is not said twice', () => {
  assert.equal(
    frame.drillGoalLine({ goal_native: 'Build the sentence.', instruction_native: 'Build the sentence' }),
    null,
    'same as the instruction, up to the final stop',
  );
  assert.equal(
    frame.drillGoalLine({ source_fr: 'Une table.', prompt_fr: '« Une table. »', instruction_native: 'x' }),
    null,
    'same as the French headline, up to the quotes',
  );
  assert.equal(
    frame.drillGoalLine({ goal_native: 'Build: "A table."', source_fr: 'Une table.', instruction_native: 'Build the sentence.' })
      .kind,
    'goal',
    'the goal wins over the source',
  );
});

test('T3 · the recall drill prints its goal right under the instruction', () => {
  const goal = 'Build: "A small white table is in the kitchen."';
  const html = decode(renderToStaticMarkup(h(steps.RecallStepView, commonProps(recallStep({ goal_native: goal })))));
  assert.match(html, /<p class="av2-goal" data-goal="goal">Build: "A small white table is in the kitchen\."<\/p>/);
  assert.ok(
    html.indexOf('Build the sentence. Some chips are not needed.') < html.indexOf('av2-goal'),
    'under the instruction',
  );
  assert.ok(html.indexOf('av2-goal') < html.indexOf('av2-tiles'), 'and above the chips');
});

test('T3 · without a goal the scene line it is cut from is quoted, with its label', () => {
  const html = decode(
    renderToStaticMarkup(
      h(steps.RecallStepView, commonProps(recallStep({ source_fr: 'Une petite table blanche est dans la cuisine.' }))),
    ),
  );
  assert.match(html, /data-goal="source"/);
  assert.ok(html.includes('From the scene'));
  assert.match(html, /<p class="av2-fr av2-goal__fr" lang="fr">Une petite table blanche est dans la cuisine\.<\/p>/);
  for (const [copy, label] of [[DE, 'Aus der Szene'], [FR, 'Dans la scène']]) {
    const localized = decode(
      renderToStaticMarkup(
        h(steps.RecallStepView, commonProps(recallStep({ source_fr: 'Une table.' }), { copy })),
      ),
    );
    assert.ok(localized.includes(label), label);
  }
});

test('T3 · an older payload draws no goal; a listening item never prints its answer', () => {
  const plain = renderToStaticMarkup(h(steps.RecallStepView, commonProps(recallStep())));
  assert.ok(!plain.includes('av2-goal'));
  const dictation = renderToStaticMarkup(
    h(
      steps.RecallStepView,
      commonProps(
        recallStep({
          task_type: 'dictation',
          options: [],
          audio_url: '/api/v1/daily-journeys/line-audio/abc',
          source_fr: 'Une petite table blanche.',
          goal_native: 'Write: "A small white table."',
        }),
      ),
    ),
  );
  assert.ok(!dictation.includes('Une petite table blanche.'), 'the phrase to write is not printed');
  assert.ok(!dictation.includes('av2-goal'));
});

// ===========================================================================
// T3 — the step header names the drill
// ===========================================================================

test('T3 · the header of a drill is «Rappel · Genre et nombre», in the chrome language', () => {
  const step = recallStep();
  assert.equal(frame.drillHeaderLabel(step, 'en', EN), 'Recall · Gender and number');
  assert.equal(frame.drillHeaderLabel(step, 'de', DE), 'Wiederholung · Gender and number', 'native label as sent');
  assert.equal(frame.drillHeaderLabel(step, 'fr', FR), 'Rappel · Genre et nombre', 'French chrome names the unit in French');
  const noNative = recallStep({}, { kind: 'vocabulary', id: 'v', label_fr: 'une table', label_native: null });
  assert.equal(frame.drillHeaderLabel(noNative, 'en', EN), 'Recall · une table');
  const noLabel = recallStep({}, { kind: 'vocabulary', id: 'v', label_fr: '', label_native: null });
  assert.equal(frame.drillHeaderLabel(noLabel, 'en', EN), 'Recall');

  const rule = {
    id: 'r', ordinal: 1, kind: 'rule', status: 'active', estimated_seconds: 30, assistance_used: [],
    prompt: { concept_id: 1, title_native: 'Subject pronouns', title_fr: 'Les pronoms', rule_card: {} },
  };
  assert.equal(frame.drillHeaderLabel(rule, 'en', EN), 'Rule · Subject pronouns');
  const forge = {
    id: 'f', ordinal: 1, kind: 'forge', status: 'active', estimated_seconds: 300, assistance_used: [],
    prompt: { concept_id: 1, title_native: 'Past tense', title_fr: 'Le passé', budget_seconds: 300, href: '/x', forged: false },
  };
  assert.equal(frame.drillHeaderLabel(forge, 'en', EN), 'La Forge · Past tense');
});

test('T3 · the day’s reply objective belongs to the scene and the reply only', () => {
  const line = (step) =>
    frame.stepHeaderLine({
      step,
      language: 'en',
      copy: EN,
      location: 'Le Mistral',
      objective: 'Ask Romy if she wants to sit with you.',
    });
  assert.equal(line(recallStep()), 'Recall · Gender and number');
  assert.ok(!line(recallStep()).includes('Ask Romy'), 'no objective above a drill');
  assert.equal(line(respondStep()), 'Le Mistral · Ask Romy if she wants to sit with you.');
  assert.equal(line({ kind: 'scene', prompt: {} }), 'Le Mistral · Ask Romy if she wants to sit with you.');
  assert.equal(line({ kind: 'resolution', prompt: {} }), 'Le Mistral · Ask Romy if she wants to sit with you.');
  assert.equal(line({ kind: 'read', prompt: {} }), '', 'a page to read carries its own kicker');
  assert.equal(line(null), 'Le Mistral · Ask Romy if she wants to sit with you.', 'no step: the day, as before');
  assert.equal(frame.stepShowsDayObjective('recall'), false);
  assert.equal(frame.stepShowsDayObjective('respond'), true);
});

test('T3 · the session prints the drill’s name, not the day’s objective, above a drill', () => {
  const recall = recallStep({ goal_native: 'Build: "A small table."' });
  const journey = journeyWith([recall, respondStep()], recall.id);
  const html = decode(renderToStaticMarkup(h(JourneySession, { controller: controllerFor(journey, recall) })));
  assert.ok(html.includes('Recall · Gender and number'), 'the drill is named');
  assert.ok(!html.includes('Ask Romy if she wants to sit with you.'), 'the objective is not above the drill');
  assert.ok(!html.includes('Le Mistral ·'), 'nor the place');

  const respond = respondStep();
  const journey2 = journeyWith([recall, respond], respond.id);
  const reply = decode(renderToStaticMarkup(h(JourneySession, { controller: controllerFor(journey2, respond) })));
  assert.ok(reply.includes('Le Mistral · Ask Romy if she wants to sit with you.'), 'the reply keeps the objective');
});

// ===========================================================================
// T6 — one note per issue; the corrected form is printed
// ===========================================================================

test('T6 · notes are deduplicated: the same explanation is said once', () => {
  const said = 'The adjective goes after «grand» here. It agrees with «poster».';
  assert.deepEqual(dedupeNotes([said, said, said]), [said]);
  assert.deepEqual(
    dedupeNotes(['Adjective position.', 'adjective position', 'Adjective position!']),
    ['Adjective position.'],
    'case, quotes and the final stop do not matter',
  );
  assert.equal(dedupeNotes(['Short.', 'A longer note that says short. And more.']).length, 2, 'distinct sentences stay');
  assert.deepEqual(
    dedupeNotes(['Use «ta» for feminine nouns.', 'Use «ta» for feminine nouns like «place». Fine.']),
    ['Use «ta» for feminine nouns like «place». Fine.'],
    'a sentence contained in a longer one already said is not said again',
  );
  assert.deepEqual(dedupeNotes(['«ta» agrees with «place».', 'Use «ta»: «place» is feminine. «ta» agrees with «place».']), [
    '«ta» agrees with «place».',
    'Use «ta»: «place» is feminine.',
  ]);
  assert.deepEqual(dedupeNotes([]), []);
  assert.deepEqual(dedupeNotes(null), []);
  assert.deepEqual(dedupeNotes(['  ', '', 12, null]), []);
  // A note that repeats itself is said once too.
  assert.deepEqual(dedupeNotes(['Feminine. Feminine. Feminine.']), ['Feminine.']);
});

test('T6 · notes_native wins, note_native is the fallback', () => {
  assert.deepEqual(
    correctionNotes({ note_native: 'old', notes_native: ['one', 'two', 'one'] }),
    ['one', 'two'],
  );
  assert.deepEqual(correctionNotes({ note_native: 'only', notes_native: null }), ['only']);
  assert.deepEqual(correctionNotes({ note_native: '', notes_native: [] }), []);
  assert.deepEqual(correctionNotes(null), []);
});

test('T6 · what is printed under the learner’s line', () => {
  assert.deepEqual(
    thread.printedFix({ span_fr: 'ton place', corrected_fr: 'ta place', note_native: '«place» is feminine.' }),
    { fixed: 'ta place', notes: ['«place» is feminine.'] },
  );
  assert.deepEqual(thread.printedFix({ span_fr: 'a', corrected_fr: 'b', note_native: '' }), { fixed: 'b', notes: [] });
  assert.equal(thread.printedFix(null), null);
  // The kept copy of the thread survives notes_native, deduplicated and clipped.
  const kept = thread.recordExchange(thread.EMPTY_THREAD, {
    turn: 0,
    prompt_fr: 'Bonjour',
    learner_fr: 'Je veux ton place.',
    character_fr: 'Bien sûr.',
    correction: { span_fr: 'ton place', corrected_fr: 'ta place', note_native: 'n', notes_native: ['a.', 'a.', 'b.'] },
  });
  assert.deepEqual(kept.exchanges[0].correction.notes_native, ['a.', 'b.']);
  const restored = thread.parseLocalThread(thread.serializeLocalThread(kept));
  assert.deepEqual(restored.exchanges[0].correction.notes_native, ['a.', 'b.']);
});

const SLIP = {
  span_fr: 'ton place',
  corrected_fr: 'ta place',
  note_native: '«place» is feminine, so it takes «ta».',
};

function turnTwoOfThree(correction = SLIP) {
  return respondStep({
    turn_index: 1,
    character_line_fr: 'Bien sûr. Tu veux un café ?',
    thread: [{ learner_fr: 'Je veux ton place.', character_fr: 'Bien sûr. Tu veux un café ?', correction }],
  });
}

test('T6 · the corrected form is under the learner’s line, always visible; the note waits for the tap', () => {
  const html = decode(renderToStaticMarkup(h(steps.RespondStepView, commonProps(turnTwoOfThree()))));
  assert.match(html, /<span class="av2-thread__slip">ton place<\/span>/, 'the slip is only marked');
  assert.match(html, /<span class="av2-thread__fixed" lang="fr">ta place<\/span>/, 'the corrected form is printed');
  assert.ok(html.indexOf('av2-thread__slip') < html.indexOf('av2-thread__fixed'), 'under the line');
  assert.ok(html.includes('Corrected form'), 'and named for a screen reader');
  assert.ok(!html.includes('av2-thread__note'), 'the explanation is behind the tap');
  assert.ok(!html.includes('is feminine'), 'not in the page until opened');
  assert.match(html, /aria-expanded="false"/);
});

test('T6 · with no explanation the corrected form is still printed, and nothing opens', () => {
  const html = renderToStaticMarkup(
    h(steps.RespondStepView, commonProps(turnTwoOfThree({ span_fr: 'ton place', corrected_fr: 'ta place', note_native: '' }))),
  );
  assert.ok(html.includes('ta place'));
  assert.ok(!html.includes('av2-thread__fixbtn'), 'no dead control');
});

test('T6 · the closing verdict lists the turn’s corrections, one line per issue', () => {
  const closing = attemptResult({
    correction: {
      span_fr: 'un poster grand',
      corrected_fr: 'un grand poster',
      note_native: 'old single note',
      notes_native: ['Adjective position.', 'adjective position!', '«poster» is masculine.'],
    },
  });
  const band = decode(
    renderToStaticMarkup(
      h(steps.JourneyFeedbackView, {
        feedback: gradedFeedback(closing, 'supported'),
        copy: EN,
        onContinue() {},
        onRetry() {},
        onDismiss() {},
      }),
    ),
  );
  assert.ok(band.includes('un grand poster'));
  assert.equal((band.match(/<li>/g) || []).length, 2, 'the repeated note is said once');
  assert.ok(band.includes('Adjective position.') && band.includes('«poster» is masculine.'));
  assert.ok(!band.includes('old single note'), 'notes_native replaces the single note');
});

// ===========================================================================
// T7 — «À vous — répondez à Marin · échange 2 sur 3»
// ===========================================================================

test('T7 · the exchange cue, in each chrome language', () => {
  const progress = (position, total) => ({ total, played: position - 1, position });
  const cue = (copy, position, total, name = 'Marin') =>
    thread.exchangeCue({ copy, name, progress: progress(position, total) });

  assert.equal(cue(FR, 2, 3).text, 'À vous — répondez à Marin · Échange 2 sur 3');
  assert.equal(cue(EN, 2, 3).text, 'Your turn — reply to Marin · Exchange 2 of 3');
  assert.equal(cue(DE, 2, 3).text, 'Du bist dran — antworte Marin · Austausch 2 von 3');
  assert.equal(cue(EN, 1, 3).last, false);

  const last = cue(FR, 3, 3);
  assert.equal(last.text, 'À vous — répondez à Marin · Dernier échange');
  assert.equal(last.last, true);
  assert.equal(cue(EN, 4, 4).part, 'Last exchange');

  // One exchange only: no count, and never «last».
  const single = cue(FR, 1, 1);
  assert.equal(single.part, null);
  assert.equal(single.text, 'À vous — répondez à Marin');
  assert.equal(single.last, false);
  // Nobody to name.
  assert.equal(cue(EN, 1, 3, '').lead, 'Your turn');
  assert.equal(cue(EN, 1, 3, null).text, 'Your turn · Exchange 1 of 3');
});

test('T7 · the cue sits under the latest line while the field is open, and only then', () => {
  const open = renderToStaticMarkup(h(steps.RespondStepView, commonProps(turnTwoOfThree(null))));
  assert.match(open, /<p class="av2-thread__cue"><span>Your turn — reply to Marin<\/span><span class="av2-thread__cue-part"> · Exchange 2 of 3<\/span><\/p>/);
  assert.ok(open.indexOf('</ol>') < open.indexOf('av2-thread__cue'), 'under the thread');
  assert.ok(open.indexOf('av2-thread__cue') < open.indexOf('<textarea'), 'above the field');
  assert.ok(!open.includes('data-last="true"'), 'not the last one');

  const lastTurn = renderToStaticMarkup(
    h(steps.RespondStepView, commonProps(respondStep({ turn_index: 2, character_line_fr: 'Et avec ça ?', thread: [
      { learner_fr: 'Un café.', character_fr: 'Au comptoir ?', correction: null },
      { learner_fr: 'Au comptoir.', character_fr: 'Et avec ça ?', correction: null },
    ] }), { copy: FR })),
  );
  assert.match(lastTurn, /data-last="true"/);
  assert.ok(lastTurn.includes('Dernier échange'));

  // The wait and the close have no cue: the field is not open.
  const waiting = renderToStaticMarkup(
    h(steps.RespondStepView, commonProps(turnTwoOfThree(null), { feedback: { kind: 'submitting' } })),
  );
  assert.ok(!waiting.includes('av2-thread__cue'));
  const closed = renderToStaticMarkup(
    h(steps.RespondStepView, commonProps(respondStep({ turn_index: 2 }), { feedback: gradedFeedback(attemptResult()) })),
  );
  assert.ok(!closed.includes('av2-thread__cue'));
});

test('T7 · after the close «Continue» is the only action', () => {
  const respond = respondStep({ turn_index: 2 });
  const journey = journeyWith([respond], respond.id);
  const feedback = gradedFeedback(attemptResult());
  const close = renderToStaticMarkup(
    h(JourneySession, { controller: controllerFor(journey, respond, { feedback }) }),
  );
  assert.ok(close.includes('Continue'), 'the one action is there');
  assert.ok(!close.includes(EN.finish_early), 'no «stop here» beside it');
  assert.ok(!close.includes('<textarea'), 'no field');

  const midway = renderToStaticMarkup(
    h(JourneySession, { controller: controllerFor(journeyWith([respondStep()], 'step-respond'), respondStep()) }),
  );
  assert.ok(midway.includes(EN.finish_early), 'while the conversation is open the quiet exit stays');
});

// ===========================================================================
// T2 — «Afficher le texte»
// ===========================================================================

const EPISODE = {
  id: 'scene-1',
  scene_id: 'scene-1',
  serial_thread_id: 't',
  serial_episode_id: null,
  journey_id: 'j',
  title_fr: 'Une place au comptoir',
  status: 'available',
  chapter: { id: 'c1', title_fr: 'Chapitre 1' },
  panel_index: 0,
  panels: [
    {
      id: 'p1',
      index: 0,
      narration_fr: 'Le Mistral est presque vide.',
      dialogue: [
        { character_id: 'romy_tremblay', character_name: 'Romy', text_fr: 'Tu veux t’asseoir avec moi ?' },
        { character_id: 'marin_leveque', character_name: 'Marin', text_fr: 'Avec plaisir, merci.' },
      ],
      image_url: null,
      image_status: 'unavailable',
    },
  ],
  resolution: null,
};

const AUDIO = {
  state: { kind: 'ready', clips: [] },
  clips: [],
  prepare() {},
  play() {},
  playFrom() {},
  stop() {},
  busy: false,
  heard: false,
};

function radioHtml(stage, extra = {}, copy = EN) {
  const state = { ...radio.RADIO_INITIAL, stage, guess: 'accord', heard: true, ...(extra.state || {}) };
  const text = extra.text || radio.RADIO_TEXT_INITIAL;
  return decode(
    renderToStaticMarkup(
      h(EpisodeRadioView, {
        episode: EPISODE,
        copy,
        audio: extra.audio || AUDIO,
        state,
        text,
        verification: radio.verifyEpisodeGuess(EPISODE, state.guess),
        onContinue() {},
        onReadInstead() {},
        dispatch() {},
        dispatchText() {},
      }),
    ),
  );
}

test('T2 · the text toggles are a pure machine; hidden is the default', () => {
  const start = radio.RADIO_TEXT_INITIAL;
  assert.equal(radio.radioLineShown(start, 'p1:l0'), false, 'hidden by default');
  const one = radio.radioTextReduce(start, { type: 'line', key: 'p1:l0' });
  assert.equal(radio.radioLineShown(one, 'p1:l0'), true);
  assert.equal(radio.radioLineShown(one, 'p1:l1'), false, 'one line only');
  assert.equal(radio.radioLineShown(radio.radioTextReduce(one, { type: 'line', key: 'p1:l0' }), 'p1:l0'), false, 'a toggle either way');
  const all = radio.radioTextReduce(one, { type: 'all' });
  assert.equal(radio.radioLineShown(all, 'p1:l1'), true, 'the whole page');
  assert.deepEqual(radio.radioTextReduce(all, { type: 'all' }), radio.RADIO_TEXT_INITIAL, 'off hides every line again');
  assert.equal(radio.radioTextReduce(start, { type: 'line', key: '' }), start);
});

test('T2 · the page toggle is at every stage; the line toggles where the lines are listed', () => {
  assert.deepEqual(
    radio.RADIO_STAGES.map((stage) => radio.radioTextControls(stage)),
    [
      { page: true, lines: false },
      { page: true, lines: true },
      { page: true, lines: true },
      { page: true, lines: false },
    ],
  );
  for (const stage of radio.RADIO_STAGES) {
    const html = radioHtml(stage);
    assert.equal((html.match(/data-radio-text-toggle/g) || []).length, 1, `${stage}: one page toggle`);
    assert.ok(html.includes('Show the text'), `${stage}: «Show the text»`);
    assert.match(html, /data-radio-text-toggle="" aria-pressed="false"|aria-pressed="false"[^>]*data-radio-text-toggle/);
  }
  // Two spoken lines and one narration line: three per-line toggles where lines are listed.
  const lineCount = radio.episodeListenLines(EPISODE).length;
  assert.equal(lineCount, 3);
  assert.equal((radioHtml('ecouter').match(/data-radio-line-toggle/g) || []).length, lineCount);
  assert.equal((radioHtml('verifier').match(/data-radio-line-toggle/g) || []).length, lineCount);
  assert.equal((radioHtml('predire').match(/data-radio-line-toggle/g) || []).length, 0);
  assert.equal((radioHtml('retenir').match(/data-radio-line-toggle/g) || []).length, 0);
});

test('T2 · while listening the words stay hidden until asked for', () => {
  const hidden = radioHtml('ecouter');
  assert.ok(!hidden.includes('Tu veux t’asseoir avec moi ?'), 'hidden by default');
  assert.ok(!hidden.includes('Avec plaisir, merci.'));
  assert.ok(hidden.includes('Text hidden'));
  assert.match(hidden, /data-radio-lines="hidden"/);

  const one = radioHtml('ecouter', { text: radio.radioTextReduce(radio.RADIO_TEXT_INITIAL, { type: 'line', key: 'p1:l0' }) });
  assert.ok(one.includes('Tu veux t’asseoir avec moi ?'), 'one line shown');
  assert.ok(!one.includes('Avec plaisir, merci.'), 'the others stay hidden');
  assert.ok(one.includes('Hide the text'), 'and the toggle says what it will do');

  const all = radioHtml('ecouter', { text: radio.radioTextReduce(radio.RADIO_TEXT_INITIAL, { type: 'all' }) });
  assert.ok(all.includes('Tu veux t’asseoir avec moi ?') && all.includes('Avec plaisir, merci.'), 'the whole page');
  assert.ok(all.includes('Le Mistral est presque vide.'), 'narration too');
  assert.match(all, /data-radio-lines="shown"/);
});

test('T2 · the text is never a wall: it can be shown before guessing and after the cycle', () => {
  const on = radio.radioTextReduce(radio.RADIO_TEXT_INITIAL, { type: 'all' });
  const predire = radioHtml('predire', { state: { guess: null }, text: on });
  assert.match(predire, /data-radio-page-text/);
  assert.ok(predire.includes('Avec plaisir, merci.'), 'even before a prediction');
  const retenir = radioHtml('retenir', { text: on });
  assert.match(retenir, /data-radio-page-text/);
  assert.ok(retenir.includes('Tu veux t’asseoir avec moi ?'));
  // Off, neither stage prints the lines.
  assert.ok(!radioHtml('predire', { state: { guess: null } }).includes('data-radio-page-text'));
  assert.ok(!radioHtml('retenir').includes('data-radio-page-text'));
  // And with the audio gone, the text and the way on are still there.
  const noAudio = radioHtml('ecouter', { audio: { ...AUDIO, state: { kind: 'unavailable', reason: 'failed' } }, text: on });
  assert.ok(noAudio.includes('Avec plaisir, merci.') || noAudio.includes('Read the scene'));
  assert.ok(noAudio.includes('Read the scene'));
});

test('T2 · the listening question is shown before the audio and again after it', () => {
  const before = radioHtml('ecouter');
  assert.match(before, /data-radio-task/);
  assert.ok(before.includes('Your listening question') && before.includes('How does it end?'));
  assert.ok(before.includes('Your guess') && before.includes('dit oui'), 'with the learner’s guess');
  const after = radioHtml('verifier');
  assert.match(after, /data-radio-task/);
  assert.ok(after.includes('How does it end?'), 'and again once it has been heard');
  assert.ok(after.includes('Your guess held.') || after.includes('The scene does not settle it'), 'with its answer');
  // Not on the first and last screens: the question is asked there in the ChoiceList.
  assert.ok(!radioHtml('retenir').includes('data-radio-task'));
  // In the learner’s language.
  assert.ok(radioHtml('ecouter', {}, FR).includes('Comment ça finit ?'));
  assert.ok(radioHtml('ecouter', {}, DE).includes('Wie geht es aus?'));
  assert.deepEqual(radio.radioTask(EPISODE, null), { guessFr: null });
  assert.match(radio.radioTask(EPISODE, 'accord').guessFr, /dit oui/);
});

test('T2 · one primary per screen at every stage', () => {
  for (const stage of radio.RADIO_STAGES) {
    const html = radioHtml(stage);
    const primaries = (html.match(/av2-btn--primary/g) || []).length;
    assert.ok(primaries <= 1, `${stage}: ${primaries} primaries`);
  }
});

test('WP-103 · every new journey key exists in all three chrome languages', () => {
  const keys = [
    'drill_recall', 'drill_rule', 'drill_forge', 'drill_from_scene',
    'exchange_your_turn_to', 'exchange_your_turn', 'exchange_last',
    'thread_fix_sr', 'thread_note_close', 'conversation_fixes',
    'radio_text_show', 'radio_text_hide', 'radio_task_label', 'radio_task_question',
  ];
  for (const table of [EN, DE, FR]) {
    for (const key of keys) {
      assert.equal(typeof table[key], 'string', key);
      assert.ok(table[key].trim().length > 0, key);
    }
  }
  for (const table of [EN, DE, FR]) {
    assert.ok(table.exchange_your_turn_to.includes('{name}'));
  }
  assert.equal(FR.exchange_last, 'Dernier échange');
  assert.equal(FR.radio_text_show, 'Afficher le texte');
});
