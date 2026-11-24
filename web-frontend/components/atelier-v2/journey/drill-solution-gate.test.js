// node --test components/atelier-v2/journey/drill-solution-gate.test.js
//
// P5 (owner, 2026-11-13; review finding 3): no solution before the retry in the scene's
// drill. A missed pick that comes back at the end of its set draws no right card and no
// corrected line; the sheet says what was given, why it is off, and that it comes back.
// The retry, a choice between two, and a miss with no retry show the solution at once.

const assert = require('node:assert/strict');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '../../..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  return originalResolve.call(this, request, ...rest);
};
const apiPath = Module._resolveFilename('@/services/api', module, false);
require.cache[apiPath] = {
  id: apiPath, filename: apiPath, loaded: true, exports: { __esModule: true, default: {}, apiService: {} },
};

const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const answerKey = require('@/lib/answer-key.ts');
const { JourneyFeedbackView } = require('./JourneySteps.tsx');
const { journeyCopy } = require('./journey-copy.ts');

const THREE = [{ id: 'o1' }, { id: 'o2' }, { id: 'o3' }];
const RIGHT = 'C’est qui, vous ?';
const miss = {
  task_outcome: 'not_yet',
  assistance_level: 'none',
  check: { outcome: 'not_yet', checked_by: 'key', call: 'not_called', counts: true, edits: [] },
};
const withheld = {
  ...miss,
  correction: {
    kind: 'pick',
    span_fr: 'Il pleut.',
    corrected_fr: '',
    note_native: 'Nicht diese. Sieh dir die Regel noch einmal an, bevor die Aufgabe wiederkommt.',
    notes_native: [],
    solution: { state: 'withheld' },
  },
};
const shown = {
  ...miss,
  correction: { kind: 'pick', span_fr: 'Il pleut.', corrected_fr: RIGHT, note_native: `Richtig ist „${RIGHT}“.`, notes_native: [] },
};

function sheet(result, language = 'de') {
  return renderToStaticMarkup(
    React.createElement(JourneyFeedbackView, {
      feedback: { kind: 'graded', verdict: 'incorrect', result, replySource: 'unknown' },
      copy: journeyCopy(language),
      stepKind: 'recall',
      onContinue() {},
      onRetry() {},
      onDismiss() {},
    }),
  );
}

test('a missed three-way pick with a retry to come draws no right card, before or after the server answers', () => {
  const prompt = { retry: false, options: THREE };
  assert.equal(answerKey.rightCardMayShow(prompt, { graded: false }), false, 'the device waits for the server');
  assert.equal(answerKey.rightCardMayShow(prompt, { graded: true, correction: withheld.correction }), false);
});

test('the right card is drawn on the retry, on a choice between two, and when the server shows the solution', () => {
  assert.equal(answerKey.rightCardMayShow({ retry: true, options: THREE }, { graded: false }), true);
  assert.equal(answerKey.rightCardMayShow({ retry: false, options: THREE.slice(0, 2) }, { graded: false }), true);
  assert.equal(answerKey.rightCardMayShow({ retry: false, options: THREE }, { graded: true, correction: shown.correction }), true);
  assert.equal(answerKey.rightCardMayShow({ retry: false, options: THREE }, { graded: true, correction: null }), true);
});

test('the withheld sheet names the pick and the reason, says it comes back, and never the answer', () => {
  for (const language of ['en', 'de', 'fr']) {
    const copy = journeyCopy(language);
    const html = sheet(withheld, language);
    assert.ok(html.includes('data-solution="withheld"'), language);
    assert.ok(html.includes(copy.drill_miss_choice), `${language}: «${copy.drill_miss_choice}»`);
    assert.ok(html.includes(copy.drill_solution_later), `${language}: it comes back`);
    assert.ok(html.includes('Il pleut.'), `${language}: the pick the learner gave`);
    assert.ok(!html.includes('qui, vous'), `${language}: the answer is not on the sheet`);
    assert.ok(!html.includes(copy.correction_pick), `${language}: no «${copy.correction_pick}»`);
  }
});

test('after the retry the sheet shows the solution as before', () => {
  const de = journeyCopy('de');
  const html = sheet(shown);
  assert.ok(html.includes(de.correction_pick));
  assert.ok(html.includes(RIGHT));
  assert.ok(!html.includes(de.drill_solution_later));
});

// #1024 (live walk 23 Nov): a missed word item said «Not this one. Look at the rule again
// and choose once more.» under locked choices. The server's lines for a withheld word
// pick (app/services/learner_copy.py, journey.withheld.word_choice), pinned per language.
const WORD_MISS = {
  en: 'Not this one: think again about what «regarder» means.',
  de: 'Nicht diese: Überleg noch einmal, was „regarder“ bedeutet.',
  fr: 'Pas celle-ci : repense à ce que veut dire « regarder ».',
};
const RULE_WORDING = { en: /\brule\b/i, de: /\bRegel\b/i, fr: /\brègle\b/i };
const CHOOSE_NOW = { en: /choose once more|choose again/i, de: /wähle neu|wähle noch/i, fr: /choisis à nouveau|choisis encore/i };

test('a withheld word miss names the word, never a rule, and promises no choice while the cards are locked', () => {
  for (const language of ['en', 'de', 'fr']) {
    const result = {
      ...miss,
      correction: {
        kind: 'meaning',
        span_fr: 'to hate',
        corrected_fr: '',
        note_native: WORD_MISS[language],
        notes_native: [],
        solution: { state: 'withheld' },
      },
    };
    const html = sheet(result, language);
    const text = html.replace(/<[^>]+>/g, ' ');
    assert.ok(html.includes('data-solution="withheld"'), language);
    assert.ok(text.includes('regarder'), `${language}: the word task is named`);
    assert.ok(!RULE_WORDING[language].test(text), `${language}: a word item has no rule: ${text}`);
    assert.ok(!CHOOSE_NOW[language].test(text), `${language}: no choice is promised now: ${text}`);
    assert.ok(text.includes(journeyCopy(language).drill_solution_later), `${language}: it comes back later`);
  }
});

test('every new line exists in en, de and fr', () => {
  for (const language of ['en', 'de', 'fr']) {
    const copy = journeyCopy(language);
    for (const key of ['drill_miss_where', 'drill_miss_choice', 'drill_solution_later']) {
      assert.ok(String(copy[key] || '').trim(), `${language}.${key}`);
    }
  }
});
