// node --test components/epreuve/forge-miss-reason-1087.test.js
//
// #1087 (walk of 26 Nov 2026, a1-de-fresh, La Forge on Avoir, fake provider). A two-choice
// miss («___ chaud ce soir ?», picked «Tu es» for «Tu as») showed «Tu es → Tu as · Noch
// nicht» and an empty bar where the reason belongs. The server had sent one: its `why_wrong`
// lost «Regel: Avoir …» to the rule-name strip (the rule is in the header) and «Du hast „Tu
// es“ gewählt; hier ist „Tu as“ nötig.» to the déclic echo strip (it names both words), and
// its `hint` («Avoir heißt haben; auch für Alter, Hunger, Durst und Kälte …») was read only
// while the solution waited. Root cause #1085: the reason shown is what survives the strips,
// and nothing falls back to the next reason the server sent.
//
// The card is rendered from the walk's exact correction, after the solution, in the grammar
// pilot (`declic`) and out of it, for the two-choice miss and a three-option item's second miss.

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
const { ExerciseFeedbackMoment } = require('../../pages/atelier.tsx');

const RULE = 'Avoir: ich habe, ich bin 20, ich habe Hunger';
const WHY = 'Du hast „Tu es“ gewählt; hier ist „Tu as“ nötig. Regel: Avoir: ich habe, ich bin 20, ich habe Hunger.';
const HINT = 'Avoir heißt haben; auch für Alter, Hunger, Durst und Kälte: j\'ai 20 ans, j\'ai froid.';
const REPAIR = '✗ Je suis 20 ans. → ✓ J\'ai 20 ans.';

/** The attempt's `correction_payload` as the walk recorded it (solution shown). */
function walkCorrection(solution) {
  return {
    verdict: 'incorrect',
    assessment_status: 'checked',
    corrected_answer: { 'avoir-1': 'Tu as' },
    errata: [{
      item_id: 'avoir-1',
      display_label: RULE,
      learner_text: 'Tu es',
      corrected_target: 'Tu as',
      why_wrong: WHY,
      hint: HINT,
      repair_hint: REPAIR,
      task_error_type: 'grammar',
    }],
    solution,
  };
}

/** What `itemFeedback` makes of it for the choice on screen. */
function choiceFeedback(correction) {
  const erratum = correction.errata[0];
  return {
    correct: false,
    learner: 'Tu es',
    target: 'Tu as',
    why: erratum.why_wrong,
    repair: erratum.repair_hint,
    issues: correction.errata,
  };
}

function render(correction, { declic }) {
  const t = epreuveCopy('de');
  return renderToStaticMarkup(React.createElement(
    EpShell,
    { language: 'de' },
    React.createElement(ExerciseFeedbackMoment, {
      feedback: choiceFeedback(correction),
      submitted: true,
      correction,
      repairDrafts: {},
      onSetRepairDraft: () => undefined,
      onSubmitRepair: () => undefined,
      repairSubmitting: {},
      feedbackKey: 'k',
      onNext: () => undefined,
      nextLabel: t.continue,
      onReport: () => undefined,
      picked: true,
      ruleShown: RULE,
      declic,
    }),
  ));
}

/** The text of every reason paragraph on the card (the bar under the corrected line). */
function reasons(html) {
  return [...html.matchAll(/<p class="ep-why"[^>]*>([\s\S]*?)<\/p>/g)]
    .map((match) => match[1].replace(/<button[\s\S]*?<\/button>/g, '').replace(/<[^>]+>/g, '').replace(/&#x27;/g, "'").trim());
}

const CASES = [
  ['two choices, the solution at once', { state: 'shown', language: 'de' }],
  ['three options, after the second miss', { state: 'shown', language: 'de' }],
  ['the solution asked for', { state: 'shown', language: 'de', revealed_by: 'reveal' }],
];

for (const [name, solution] of CASES) {
  test(`${name}, grammar pilot: the miss says why avoir, never an empty bar`, () => {
    const html = render(walkCorrection(solution), { declic: true });
    assert.ok(html.includes('data-verdict="wrong"'), 'the miss is drawn');
    const shown = reasons(html);
    assert.ok(shown.length > 0, 'the card has a reason bar');
    for (const reason of shown) assert.notEqual(reason, '', `an empty reason bar is drawn: ${html.slice(0, 900)}`);
    assert.ok(
      shown.some((reason) => reason.includes('Avoir heißt haben')),
      `the reason explains avoir for «chaud» (the server's hint): ${JSON.stringify(shown)}`,
    );
  });

  test(`${name}, classic card: the reason is never empty`, () => {
    const html = render(walkCorrection(solution), { declic: false });
    const shown = reasons(html);
    assert.ok(shown.length > 0 && shown.every(Boolean), `a reason is drawn: ${JSON.stringify(shown)}`);
  });
}

test('a why that is only the rule falls back to the server\'s hint, in and out of the pilot', () => {
  const correction = walkCorrection({ state: 'shown', language: 'de' });
  correction.errata[0].why_wrong = `Regel: ${RULE}.`;
  for (const declic of [true, false]) {
    const shown = reasons(render(correction, { declic }));
    assert.ok(
      shown.some((reason) => reason.includes('Avoir heißt haben')),
      `declic=${declic}: the hint stands in for the stripped why: ${JSON.stringify(shown)}`,
    );
  }
});

test('with no hint (an English payload), the repair example is the reason, not nothing', () => {
  const correction = walkCorrection({ state: 'shown', language: 'en' });
  delete correction.errata[0].hint;
  correction.errata[0].why_wrong = `You chose “Tu es”; this item needs “Tu as”. Rule: ${RULE}.`;
  const shown = reasons(render(correction, { declic: true }));
  assert.ok(shown.length > 0 && shown.every(Boolean), `an empty reason bar is drawn: ${JSON.stringify(shown)}`);
  assert.ok(shown.some((reason) => reason.includes("J'ai 20 ans")), JSON.stringify(shown));
});
