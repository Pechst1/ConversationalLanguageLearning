// node --test components/atelier-v2/journey/respond-thread.test.js
//
// WP-89 «Le fil» — the respond step is one conversation.
//
//   1. the thread model (pure): the local copy, the bubble order and dedupe,
//      the server thread winning, the exchange in flight;
//   2. the exchange tokens: one per planned exchange, filled as each passes,
//      «Échange 2 sur 3» in the learner's language;
//   3. verdict only at the close: continuing turns get no band, no frown and
//      no sound — a light tick — and a slip is a proofreader's mark;
//   4. the rendered column: an ordered list with speaker labels, the learner's
//      lines on the right, the current line last and the field under it.

const assert = require('node:assert/strict');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..', '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) {
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

const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

const model = require('./respond-thread.ts');
const steps = require('./JourneySteps.tsx');
const { feelForTransition } = require('./useJourneyFeel.ts');
const { journeyCopy } = require('./journey-copy.ts');

const EN = journeyCopy('en');
const FR = journeyCopy('fr');
const DE = journeyCopy('de');
const h = React.createElement;

const OPENING = 'Bonjour ! Qu’est-ce que je vous sers ?';

function prompt(extra = {}) {
  return {
    turn_index: 0,
    max_turns: 3,
    repair_allowed: true,
    character_id: 'margaux_barman',
    character_name: 'Margaux',
    character_line_fr: OPENING,
    character_line_audio_url: null,
    objective_native: 'Order a coffee.',
    input_modes: ['text'],
    targets: [],
    help_available: [],
    ...extra,
  };
}

function step(extra = {}) {
  return {
    id: 'step-respond',
    ordinal: 3,
    kind: 'respond',
    status: 'active',
    estimated_seconds: 120,
    assistance_used: [],
    prompt: prompt(extra),
  };
}

const SLIP = {
  span_fr: 'un café noire',
  corrected_fr: 'un café noir',
  note_native: '«café» is masculine, so «noir» has no -e.',
};

function result(extra = {}) {
  return {
    contract_version: 1,
    evidence_ref: 'ev-1',
    task_outcome: 'met',
    assistance_level: 'none',
    correction: null,
    character_reply_fr: 'Très bien. Au comptoir ou en terrasse ?',
    reply_source: 'model',
    next_turn: null,
    pending: false,
    journey: {},
    ...extra,
  };
}

const graded = (res, verdict = 'correct') => ({ kind: 'graded', verdict, result: res, replySource: 'model' });
const replying = (res, verdict = 'correct') => ({ ...graded(res, verdict), kind: 'replying' });

const props = (s, feedback = { kind: 'idle' }, extra = {}) => ({
  step: s,
  copy: EN,
  busy: false,
  feedback,
  help: null,
  onHelp() {},
  onSubmit() {},
  onContinue() {},
  ...extra,
});

const kinds = (bubbles) => bubbles.map((bubble) => `${bubble.kind[0]}:${bubble.text}`);

// ===========================================================================
// 1. The thread model
// ===========================================================================

test('the local copy survives a round trip, refuses garbage and fits the draft cap', () => {
  assert.deepEqual(model.parseLocalThread(''), model.EMPTY_THREAD);
  assert.deepEqual(model.parseLocalThread('{not json'), model.EMPTY_THREAD);
  assert.deepEqual(model.parseLocalThread('{"v":2,"exchanges":[]}'), model.EMPTY_THREAD);
  assert.deepEqual(model.parseLocalThread('{"v":1,"exchanges":[{"turn":-1,"learner_fr":"x"}]}'), model.EMPTY_THREAD);

  let thread = model.EMPTY_THREAD;
  thread = model.recordExchange(thread, {
    turn: 1,
    prompt_fr: 'Au comptoir ?',
    learner_fr: 'Au comptoir, merci.',
    character_fr: 'Parfait.',
    correction: null,
  });
  thread = model.recordExchange(thread, {
    turn: 0,
    prompt_fr: OPENING,
    learner_fr: 'Bonjour, un café noire.',
    character_fr: 'Au comptoir ?',
    correction: SLIP,
  });
  assert.deepEqual(thread.exchanges.map((item) => item.turn), [0, 1], 'kept oldest first');
  const again = model.recordExchange(thread, { ...thread.exchanges[0] });
  assert.equal(again, thread, 'a replayed result is the same turn, kept once');

  const stored = model.serializeLocalThread(thread);
  assert.deepEqual(model.parseLocalThread(stored), thread);
  assert.equal(model.threadDraftKey('abc'), 'abc:thread', 'filed under the step, pruned with it');

  const long = 'mot '.repeat(200);
  let big = model.EMPTY_THREAD;
  for (let turn = 0; turn < 6; turn += 1) {
    big = model.recordExchange(big, { turn, prompt_fr: long, learner_fr: long, character_fr: long, correction: null });
  }
  const capped = model.serializeLocalThread(big);
  assert.ok(capped.length <= model.MAX_THREAD_CHARS, 'never above the draft cap');
  const kept = model.parseLocalThread(capped).exchanges;
  assert.ok(kept.length >= 1 && kept[kept.length - 1].turn === 5, 'the oldest go first');
});

test('turn 0: the opening line alone, as the latest bubble', () => {
  const bubbles = model.threadBubbles({ prompt: prompt() });
  assert.deepEqual(kinds(bubbles), [`c:${OPENING}`]);
  assert.equal(bubbles[0].latest, true);
});

test('turn 1 of 3 from the local copy: opening, the learner, the reply said once', () => {
  const local = model.recordExchange(model.EMPTY_THREAD, {
    turn: 0,
    prompt_fr: OPENING,
    learner_fr: 'Un café, s’il vous plaît.',
    character_fr: 'Très bien. Au comptoir ou en terrasse ?',
    correction: null,
  });
  // The next turn's line IS the reply: said once, not twice.
  const bubbles = model.threadBubbles({
    prompt: prompt({ turn_index: 1, character_line_fr: 'Très bien.  Au comptoir ou en terrasse ?' }),
    local,
  });
  assert.deepEqual(kinds(bubbles), [
    `c:${OPENING}`,
    'l:Un café, s’il vous plaît.',
    'c:Très bien. Au comptoir ou en terrasse ?',
  ]);
  assert.deepEqual(bubbles.map((bubble) => bubble.latest === true), [false, false, true]);

  // A next line that is not the reply follows it.
  const follow = model.threadBubbles({
    prompt: prompt({ turn_index: 1, character_line_fr: 'Vous prenez du sucre ?' }),
    local,
  });
  assert.deepEqual(kinds(follow).slice(-2), ['c:Très bien. Au comptoir ou en terrasse ?', 'c:Vous prenez du sucre ?']);
});

test('the server thread wins the words; the local copy still supplies the opening', () => {
  const local = model.recordExchange(model.EMPTY_THREAD, {
    turn: 0,
    prompt_fr: OPENING,
    learner_fr: 'un cafe',
    character_fr: 'Un café.',
    correction: null,
  });
  const bubbles = model.threadBubbles({
    prompt: prompt({
      turn_index: 1,
      character_line_fr: 'Au comptoir ?',
      thread: [{ learner_fr: 'Un café, s’il vous plaît.', character_fr: 'Au comptoir ?', correction: SLIP }],
    }),
    local,
  });
  assert.deepEqual(kinds(bubbles), [`c:${OPENING}`, 'l:Un café, s’il vous plaît.', 'c:Au comptoir ?']);
  assert.deepEqual(bubbles[1].correction, SLIP, 'the mark comes from the server thread');

  // A fresh device has no local copy: the thread starts at the first answer.
  const fresh = model.threadBubbles({
    prompt: prompt({
      turn_index: 1,
      character_line_fr: 'Au comptoir ?',
      thread: [{ learner_fr: 'Un café.', character_fr: 'Au comptoir ?', correction: null }],
    }),
  });
  assert.deepEqual(kinds(fresh), ['l:Un café.', 'c:Au comptoir ?']);
});

test('the exchange in flight: pending under the current line, then kept once', () => {
  const sending = model.threadBubbles({
    prompt: prompt(),
    inFlight: { turn: 0, prompt_fr: OPENING, learner_fr: 'Un café.', character_fr: null, correction: null },
  });
  assert.deepEqual(kinds(sending), [`c:${OPENING}`, 'l:Un café.']);
  assert.equal(sending[1].pending, true);
  assert.equal(sending[0].latest, true, 'the character line stays the latest while they type');

  // The reply lands: the snapshot is on turn 1, the exchange not yet kept.
  const flight = {
    turn: 0,
    prompt_fr: OPENING,
    learner_fr: 'Un café.',
    character_fr: 'Au comptoir ?',
    correction: null,
  };
  const landed = model.threadBubbles({ prompt: prompt({ turn_index: 1, character_line_fr: 'Au comptoir ?' }), inFlight: flight });
  assert.deepEqual(kinds(landed), [`c:${OPENING}`, 'l:Un café.', 'c:Au comptoir ?']);
  assert.equal(landed[1].pending, false);
  // …and once kept, the same exchange is not doubled.
  const local = model.recordExchange(model.EMPTY_THREAD, flight);
  assert.deepEqual(
    kinds(model.threadBubbles({ prompt: prompt({ turn_index: 1, character_line_fr: 'Au comptoir ?' }), local, inFlight: flight })),
    kinds(landed),
  );

  // The closing turn: the line it answered, the answer, then the last reply.
  const closing = model.threadBubbles({
    prompt: prompt({ turn_index: 1, character_line_fr: 'Au comptoir ?' }),
    local,
    inFlight: { turn: 1, prompt_fr: 'Au comptoir ?', learner_fr: 'Oui, au comptoir.', character_fr: 'Installez-vous.', correction: null },
  });
  assert.deepEqual(kinds(closing), [
    `c:${OPENING}`,
    'l:Un café.',
    'c:Au comptoir ?',
    'l:Oui, au comptoir.',
    'c:Installez-vous.',
  ]);
  assert.equal(closing[4].latest, true);
});

test('the kept exchange is derived from the result, turn and all', () => {
  const kept = model.exchangeFromResult({
    result: result({ correction: SLIP, next_turn: { step_id: 's', prompt: prompt({ turn_index: 2 }) } }),
    prompt: prompt({ turn_index: 2 }),
    sent: null,
    fallbackText: 'Un café noire.',
  });
  assert.equal(kept.turn, 1, 'next_turn 2 settles turn 1');
  assert.equal(kept.learner_fr, 'Un café noire.');
  assert.deepEqual(kept.correction, SLIP);
  const sent = model.exchangeFromResult({
    result: result(),
    prompt: prompt({ turn_index: 2 }),
    sent: { turn: 2, text: 'Merci !', prompt_fr: 'Autre chose ?' },
  });
  assert.equal(sent.turn, 2);
  assert.equal(sent.prompt_fr, 'Autre chose ?');
  assert.equal(model.exchangeFromResult({ result: result({ pending: true }), prompt: prompt(), sent: null, fallbackText: 'x' }), null);
  assert.equal(model.exchangeFromResult({ result: result(), prompt: prompt(), sent: null, fallbackText: '  ' }), null);
});

// ===========================================================================
// 2. The exchange tokens
// ===========================================================================

test('one token per planned exchange, filled as each passes', () => {
  assert.deepEqual(model.exchangeProgress(prompt({ turn_index: 0, max_turns: 3 }), false), { total: 3, played: 0, position: 1 });
  assert.deepEqual(model.exchangeProgress(prompt({ turn_index: 1, max_turns: 3 }), false), { total: 3, played: 1, position: 2 });
  assert.deepEqual(model.exchangeProgress(prompt({ turn_index: 2, max_turns: 3 }), true), { total: 3, played: 3, position: 3 });
  // A «relance» past the plan grows the sequence rather than overflowing it.
  assert.deepEqual(model.exchangeProgress(prompt({ turn_index: 3, max_turns: 3 }), false), { total: 4, played: 3, position: 4 });

  const two = model.exchangeProgress(prompt({ turn_index: 1, max_turns: 3 }), false);
  assert.equal(model.exchangeLabel(FR.exchange_of, two), 'Échange 2 sur 3');
  assert.equal(model.exchangeLabel(EN.exchange_of, two), 'Exchange 2 of 3');
  assert.equal(model.exchangeLabel(DE.exchange_of, two), 'Austausch 2 von 3');
});

test('a four-exchange Intensif conversation shows four tokens and one verdict', () => {
  const s = step({ turn_index: 3, max_turns: 4 });
  const html = renderToStaticMarkup(h(steps.RespondStepView, props(s, graded(result(), 'correct'))));
  assert.equal((html.match(/class="av2-thread__token"/g) || []).length, 4);
  assert.equal((html.match(/data-state="done"/g) || []).length, 4, 'all four played at the close');
  assert.ok(html.includes('Exchange 4 of 4'));

  const band = (feedback) =>
    renderToStaticMarkup(
      h(steps.JourneyFeedbackView, { feedback, copy: EN, onContinue() {}, onRetry() {}, onDismiss() {} }),
    );
  const nextTurn = { step_id: s.id, prompt: prompt({ turn_index: 1, max_turns: 4 }) };
  const verdicts = [
    band(graded(result({ next_turn: nextTurn }), 'correct')),
    band(graded(result({ next_turn: nextTurn }), 'wrong')),
    band(graded(result({ next_turn: nextTurn }), 'supported')),
    band(graded(result(), 'correct')),
  ].filter(Boolean);
  assert.equal(verdicts.length, 1, 'one verdict, on the closing turn');
  assert.ok(verdicts[0].includes('data-state="correct"'));
});

// ===========================================================================
// 3. Verdict only at the close
// ===========================================================================

test('continuing vs closing, and what the learner feels', () => {
  const going = graded(result({ next_turn: { step_id: 's', prompt: prompt({ turn_index: 1 }) } }), 'wrong');
  const closing = graded(result(), 'wrong');
  assert.equal(model.continuesConversation(going), true);
  assert.equal(model.closesConversation(going), false);
  assert.equal(model.continuesConversation({ ...going, kind: 'replying' }), true);
  assert.equal(model.closesConversation(closing), true);
  assert.equal(model.continuesConversation({ kind: 'idle' }), false);

  const before = { phase: 'session', stepId: 's1', result: null, reply: null };
  const at = (feedback) => ({ phase: 'session', stepId: 's1', feedback });
  // A reply mid-conversation is a light tick — never the wrong buzz or sound.
  assert.equal(feelForTransition(before, at({ ...going, kind: 'replying' })), 'reply');
  assert.equal(feelForTransition({ ...before, reply: going.result }, at(going)), null, 'the staged pair ticks once');
  // The closing turn is felt as the verdict it is.
  assert.equal(feelForTransition(before, at(closing)), 'wrong');
});

test('the proofreader’s mark finds the slip in the learner’s line', () => {
  assert.deepEqual(model.markSpan('Bonjour, un café noire.', 'un café noire'), {
    before: 'Bonjour, ',
    mark: 'un café noire',
    after: '.',
  });
  assert.deepEqual(model.markSpan('J’ai faim', "j'ai"), { before: '', mark: 'J’ai', after: ' faim' });
  assert.equal(model.markSpan('Bonjour', 'bonsoir'), null);
  assert.equal(model.markSpan('Bonjour', ''), null);
});

// ===========================================================================
// 4. The rendered column
// ===========================================================================

function turnOneOfThree(extra = {}) {
  return step({
    turn_index: 1,
    max_turns: 3,
    character_line_fr: 'Au comptoir ou en terrasse ?',
    thread: [{ learner_fr: 'Bonjour, un café noire.', character_fr: 'Au comptoir ou en terrasse ?', correction: SLIP }],
    ...extra,
  });
}

test('turn 1 of 3: an ordered list with speaker labels, the field under the current line', () => {
  const html = renderToStaticMarkup(h(steps.RespondStepView, props(turnOneOfThree())));
  assert.match(html, /<ol class="av2-thread" aria-label="The conversation">/);
  assert.equal((html.match(/<li class="av2-thread__line"/g) || []).length, 2);
  assert.ok(html.includes('<span class="av2-sr">You: </span>'), 'the learner line is labelled');
  assert.ok(html.includes('<span class="av2-sr">Margaux: </span>'), 'and so is the character’s');
  assert.match(html, /class="av2-fr av2-thread__mine" lang="fr"/);
  // Tokens: one filled, two to come; the reader hears where they are.
  assert.equal((html.match(/class="av2-thread__token" data-state="done"/g) || []).length, 1);
  assert.equal((html.match(/class="av2-thread__token"/g) || []).length, 3);
  assert.ok(html.includes('<span class="av2-sr">Exchange 2 of 3</span>'));
  // The latest line is the one headline, and the field comes after the list.
  assert.equal((html.match(/av2-headline/g) || []).length, 1);
  assert.ok(html.indexOf('</ol>') < html.indexOf('<textarea'), 'the field sits under the thread');
  assert.ok(html.indexOf('av2-thread__tokens') < html.indexOf('<ol'), 'tokens under the name, above the thread');
  // The mark: a red dotted underline on the slip, the note closed until tapped.
  assert.match(html, /<button type="button" class="av2-thread__mark" aria-expanded="false"[^>]*>un café noire/);
  assert.ok(!html.includes('av2-thread__note'), 'the margin note waits for the tap');
  // A mark is never a verdict.
  for (const forbidden of [EN.correct, EN.wrong, EN.supported]) {
    assert.ok(!html.includes(`>${forbidden}<`), `no «${forbidden}» mid-conversation`);
  }
});

test('a continuing turn: no band, no frown, the field reopens; a closing one is judged once', () => {
  const going = result({
    task_outcome: 'not_yet',
    correction: SLIP,
    character_reply_fr: 'Au comptoir ou en terrasse ?',
    next_turn: { step_id: 'step-respond', prompt: prompt({ turn_index: 1 }) },
  });
  const s = turnOneOfThree({ thread: [] });
  const sent = { get: (key) => (key === 'step-respond:0' ? 'Bonjour, un café noire.' : ''), set() {} };
  const html = renderToStaticMarkup(h(steps.RespondStepView, props(s, graded(going, 'wrong'), { draft: sent })));
  assert.ok(!html.includes('portrait-cross'), 'the face never frowns mid-conversation');
  assert.ok(html.includes('<textarea'), 'the field is open for the next exchange');
  assert.ok(!/<textarea[^>]*disabled/.test(html), 'and not locked');

  const band = renderToStaticMarkup(
    h(steps.JourneyFeedbackView, {
      feedback: graded(going, 'wrong'),
      copy: EN,
      onContinue() {},
      onRetry() {},
      onDismiss() {},
      speaker: { id: 'margaux_barman', name: 'Margaux' },
    }),
  );
  assert.equal(band, '', 'no band, no «Continue», no smile on next_turn');

  // The closing turn: the verdict mood on the face, the field gone, the band once.
  const closeHtml = renderToStaticMarkup(
    h(steps.RespondStepView, props(turnOneOfThree({ turn_index: 2 }), graded(result(), 'correct'), {
      draft: { get: (key) => (key === 'step-respond:2' ? 'Au comptoir, merci.' : ''), set() {} },
    })),
  );
  assert.match(closeHtml, /class="av2-speech" data-mood="happy"/);
  assert.ok(!closeHtml.includes('<textarea'));
  assert.ok(closeHtml.includes('Au comptoir, merci.'), 'the learner’s last line stays on the page');
});

// ===========================================================================
// 5. W7 — «with help» only when help was really used
// ===========================================================================

test('a partial answer without help reads as partial, never «with help»', () => {
  const state = require('./journey-state.ts');
  const band = (res, copy = EN) =>
    renderToStaticMarkup(
      h(steps.JourneyFeedbackView, {
        feedback: state.feedbackFromAttempt(res),
        copy,
        onContinue() {},
        onRetry() {},
        onDismiss() {},
      }),
    );
  // The walk's W7: partially_met, no help used, on the closing turn.
  const unaided = result({ task_outcome: 'partially_met', assistance_level: 'none' });
  assert.equal(state.verdictTitleKey('supported', 'none'), 'nearly');
  for (const copy of [EN, DE, FR]) {
    const html = band(unaided, copy);
    assert.ok(html.includes(copy.nearly), `partial is said as partial (${copy.nearly})`);
    assert.ok(!html.includes(copy.supported), 'and never credited to help nobody asked for');
  }
  // Help really used: then, and only then, «with help».
  for (const assistance of ['hint', 'translation', 'solution']) {
    assert.equal(state.verdictTitleKey('supported', assistance), 'supported');
  }
  const helped = band(result({ task_outcome: 'partially_met', assistance_level: 'hint' }));
  assert.ok(helped.includes(EN.supported));
  assert.ok(band(result({ task_outcome: 'met', assistance_level: 'hint' })).includes(EN.supported));
  assert.ok(band(result({ task_outcome: 'met', assistance_level: 'none' })).includes(EN.correct));
  // Mid-conversation there is no band to say it in at all.
  assert.equal(
    band(result({ task_outcome: 'partially_met', assistance_level: 'none', next_turn: { step_id: 's', prompt: prompt({ turn_index: 1 }) } })),
    '',
  );
});
