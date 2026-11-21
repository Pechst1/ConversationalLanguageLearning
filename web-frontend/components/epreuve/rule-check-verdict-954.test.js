// node --test components/epreuve/rule-check-verdict-954.test.js
//
// #954 (walk of 20 Nov 2026, a1-de-fresh, fake provider). The Regelprüfung's own sentence
// «Ils sont fatigues.» showed «Noch nicht · Die Aufgabe · Die Antwort erfüllt die Aufgabe
// noch nicht. Lies sie noch einmal und versuch es erneut.» with no retry button, then the
// result counted it right («3 von 3 richtig»).
//
//   1. a correction with no erratum, no rewrite and nothing missing has no reason to give:
//      it never stands in «the task is not met» (`task_default_why`) for one;
//   2. «try again» is said by a button, never by a reason printed where no retry is offered;
//   3. a hit whose accent was forgiven names it in one line (`slip_note_native`).

const assert = require('node:assert/strict');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  return originalResolve.call(this, request, ...rest);
};
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const { EpShell } = require('./Epreuve.tsx');
const { epreuveCopy } = require('./epreuve-copy.ts');
const { ExerciseFeedbackMoment, feedbackFromFreeformCorrection } = require('../../pages/atelier.tsx');

const LEARNER = 'Ils sont fatigues.';
const RETRY_SAID = /versuch es erneut|réessaie|and retry|try again/i;

function render(correction, lang, { onTryAgain } = {}) {
  const feedback = feedbackFromFreeformCorrection(correction, '', LEARNER, epreuveCopy(lang));
  const html = renderToStaticMarkup(React.createElement(
    EpShell,
    { language: lang },
    React.createElement(ExerciseFeedbackMoment, {
      feedback,
      submitted: true,
      correction,
      repairDrafts: {},
      onSetRepairDraft: () => undefined,
      onSubmitRepair: () => undefined,
      repairSubmitting: {},
      feedbackKey: 'k',
      onNext: () => undefined,
      nextLabel: epreuveCopy(lang).continue,
      onTryAgain,
      onReport: () => undefined,
      production: true,
    }),
  ));
  return { feedback, html };
}

// A rule check's own sentence graded wrong with nothing said about it (a detector miss on
// the fake provider): no erratum, no rewrite, nothing missing.
const EMPTY_MISS = {
  verdict: 'incorrect',
  score_0_4: 1,
  corrected_answer: LEARNER,
  errata: [],
  missing_targets: [],
  assessment_status: 'checked',
  checked: true,
  graded_by: 'local_test_out',
  ai_review: { status: 'not_applicable' },
};

for (const lang of ['de', 'en', 'fr']) {
  test(`${lang}: an empty correction is not «the task is not met»`, () => {
    const t = epreuveCopy(lang);
    const { feedback, html } = render(EMPTY_MISS, lang);
    assert.equal(feedback.correct, false, 'the server said wrong: the screen says wrong');
    for (const issue of feedback.issues || []) {
      assert.notEqual(issue.why_wrong, t.task_default_why, 'no reason came, so none is made up');
      assert.notEqual(issue.task_error_type, 'task_compliance', 'nothing said the task was missed');
    }
    assert.ok(!html.includes(t.task_default_why), `the task line is printed: ${html.slice(0, 400)}`);
  });

  test(`${lang}: no «try again» is printed where no retry is offered`, () => {
    // A task note with no reason of its own (the case task_default_why is for).
    const taskMiss = {
      ...EMPTY_MISS,
      errata: [{ task_error_type: 'task_compliance', learner_text: LEARNER, corrected_target: '', why_wrong: '' }],
    };
    const { html } = render(taskMiss, lang);
    assert.ok(html.includes('data-verdict="wrong"'));
    const said = html.replace(/<button[\s\S]*?<\/button>/g, '');
    assert.doesNotMatch(said, RETRY_SAID, 'a reason promises a retry no button offers');
  });

  test(`${lang}: a hit with a forgiven accent names it`, () => {
    const note = { de: 'Richtig — achte auf den Akzent: «fatigués».', en: 'Right — watch the accent: «fatigués».', fr: "Juste — attention à l'accent : « fatigués »." }[lang];
    const hit = {
      verdict: 'correct',
      score_0_4: 4,
      corrected_answer: 'Ils sont fatigués.',
      errata: [],
      missing_targets: [],
      lexical_gaps: [],
      accent_notes: [{ learner_text: LEARNER, corrected_target: 'Ils sont fatigués.' }],
      slip_note_native: note,
      assessment_status: 'checked',
      checked: true,
      graded_by: 'local_test_out',
      ai_review: { status: 'not_applicable' },
    };
    const { feedback, html } = render(hit, lang);
    assert.equal(feedback.correct, true);
    assert.ok(html.includes('data-verdict="correct"'));
    assert.ok(html.includes('Ils sont fatigués.'), 'the hit shows the sentence with its accent');
    const escaped = note.replace(/'/g, '&#x27;');
    assert.ok(html.includes(escaped) || html.includes(note), `the accent is named: ${html.slice(0, 600)}`);
  });
}
