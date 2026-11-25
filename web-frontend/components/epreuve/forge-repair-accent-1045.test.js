// node --test components/epreuve/forge-repair-accent-1045.test.js
//
// #1045 (live walk 24 Nov 2026, A1.1 day 42, La Forge item 4/4). The corrected line
// retyped without its «é» («… et un cafe chaud.») read «Not quite — try the line
// again.», with nothing to say that only the accent was missing. The server names the
// word (`micro_repairs[i].note = 'accent'`, `expected_word`); the repair says it.

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

const LEARNER = 'Il y a du pain, du confiture et un cafe chaud.';
const CORRECTED = 'Il y a du pain, de la confiture et un café chaud.';

function render(lang, record, errata) {
  const correction = {
    verdict: 'partial',
    assessment_status: 'checked',
    corrected_answer: CORRECTED,
    errata,
    notes_native: ['«confiture» is feminine: «de la confiture».', '«café» takes an accent.'],
    solution: { state: 'shown', revealed_by: 'reveal' },
    micro_repairs: { 0: { target: CORRECTED, erratum_index: 0, ...record } },
  };
  const feedback = feedbackFromFreeformCorrection(correction, '', LEARNER, epreuveCopy(lang));
  return renderToStaticMarkup(React.createElement(
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
      onReport: () => undefined,
      production: true,
    }),
  ));
}

// What the repair says: the text of its own notice (role=alert on a miss, status on a hit).
function repairSays(html, role) {
  const at = html.indexOf('ep-repair');
  assert.ok(at >= 0, 'no repair on screen');
  const notice = new RegExp('role="' + role + '"[^>]*>(?:(?!</p>).)*?<p>([^<]*)</p>').exec(html.slice(at));
  assert.ok(notice, 'the repair says nothing');
  return notice[1];
}

const PLACED = [
  { learner_text: 'du confiture', corrected_target: 'de la confiture', task_error_type: 'grammar', why_wrong: '«confiture» is feminine: «de la confiture».' },
  { learner_text: 'cafe', corrected_target: 'café', task_error_type: 'orthography', why_wrong: '«café» takes an accent.' },
];
// A correction the line cannot hold in place: the line is retyped whole («Type the corrected line…»).
const WHOLE = [
  { learner_text: LEARNER, corrected_target: CORRECTED, task_error_type: 'grammar', why_wrong: '«confiture» is feminine; «café» takes an accent.' },
];
const MISS = { typed: 'Il y a du pain, de la confiture et un cafe chaud.', status: 'no', note: 'accent', learner_word: 'cafe', expected_word: 'café' };

for (const [name, errata] of [['retyped whole', WHOLE], ['fixed in place', PLACED]]) {
  test(`a repair refused for its accent says which word (${name})`, () => {
    for (const lang of ['en', 'de', 'fr']) {
      const said = repairSays(render(lang, MISS, errata), 'alert');
      assert.match(said, /café/, `${lang}: the repair said «${said}», not which word lacks its accent`);
    }
  });
}

test('a repair accepted with an accent note says so', () => {
  const said = repairSays(render('en', { ...MISS, status: 'ok' }, WHOLE), 'status');
  assert.match(said, /café/, said);
});

test('a repair without a note says what it always said', () => {
  const t = epreuveCopy('en');
  assert.equal(repairSays(render('en', { typed: 'x', status: 'no' }, WHOLE), 'alert'), t.repair_no);
});
