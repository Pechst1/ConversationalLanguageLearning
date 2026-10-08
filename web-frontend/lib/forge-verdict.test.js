// node --test lib/forge-verdict.test.js
//
// WP-103 T9 — La Forge's free production: «Je relis…», and a verdict is never
// reversed. The owner saw «Right / Well done!», then ten seconds later «3
// corrections». Locally only a real match to an accepted answer may say
// «Right»; everything else waits for the model; and what was shown stands.

const assert = require('node:assert/strict');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (typeof request === 'string' && request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

const V = require('./forge-verdict.ts');
const { seanceAssessment } = require('./seance-feedback.ts');
const { forgeCorrectionNotes } = require('./correction-notes.ts');

const provisional = (extra = {}) => ({
  verdict: 'accepted',
  errata: [],
  assessment_status: 'provisional',
  ai_review: { status: 'pending' },
  ...extra,
});
const right = provisional({ local_status: 'right' });
const checked = (extra = {}) => ({ verdict: 'accepted', errata: [], assessment_status: 'checked', ai_review: { status: 'complete' }, ...extra });
const wrong = checked({
  verdict: 'incorrect',
  errata: [{ why_wrong: 'Adjective position.' }, { why_wrong: 'Adjective position.' }, { why_wrong: 'adjective position' }],
});

test('the server’s local verdict is read from the correction or its forge block', () => {
  assert.equal(V.localStatusOf({ local_status: 'right' }), 'right');
  assert.equal(V.localStatusOf({ forge: { local_status: 'checking' } }), 'checking');
  assert.equal(V.localStatusOf({ local_status: 'maybe' }), null);
  assert.equal(V.localStatusOf(null), null);
});

test('only a real local match says «Right»; anything else is «Je relis…»', () => {
  assert.equal(V.productionPhase(right), 'right');
  assert.equal(V.productionPhase(provisional({ local_status: 'checking' })), 'checking');
  // An older server sends no local_status: its provisional verdict is not shown as one.
  assert.equal(V.productionPhase(provisional()), 'checking');
  assert.equal(V.productionPhase(provisional({ local_status: 'checking', verdict: 'accepted', errata: [] })), 'checking');
  assert.equal(V.showsVerdict('checking'), false);
  assert.equal(V.showsVerdict('right'), true);
  assert.equal(V.showsVerdict('settled'), true);
});

test('a checked verdict is settled; a model that failed is not a wait', () => {
  assert.equal(V.productionPhase(checked()), 'settled');
  assert.equal(V.productionPhase(wrong), 'settled');
  assert.equal(V.productionPhase(null), 'settled');
  assert.equal(V.productionPhase(provisional({ ai_review: { status: 'failed' } })), 'unavailable');
  // Unchecked and still waiting on the model (a legacy payload): a wait, not a verdict.
  assert.equal(V.productionPhase({ verdict: 'accepted', ai_review: { status: 'pending' } }), 'checking');
  assert.equal(V.productionPhase({ verdict: 'accepted', ai_review: { status: 'queued' } }), 'checking');
  // Even a real match is final once checked.
  assert.equal(V.productionPhase({ ...right, assessment_status: 'checked' }), 'settled');
});

test('the poll keeps asking while the model has not read it', () => {
  assert.equal(V.reviewIsPending(provisional({ local_status: 'checking' })), true);
  assert.equal(V.reviewIsPending(right), true, 'a late reading is still fetched, to settle the record');
  assert.equal(V.reviewIsPending(checked()), false);
  assert.equal(V.reviewIsPending(provisional({ ai_review: { status: 'failed' } })), false);
  assert.equal(V.reviewIsPending(null), false);
});

test('never a flip: a shown «Right» stands against a late model reading', () => {
  const settled = V.settleShownCorrection(right, wrong);
  assert.equal(V.productionPhase(settled), 'settled', 'the poll can stop');
  assert.equal(seanceAssessment(settled), 'correct', 'the learner is still told «Right»');
  assert.equal(settled.verdict, 'accepted');
  assert.deepEqual(settled.errata, [], 'no corrections appear after «Right»');
  assert.equal(settled.second_check, undefined, 'and no second-check note reverses it');
  assert.equal(settled.verdict_frozen, true);
  assert.equal(settled.ai_review.status, 'complete');
});

test('a wait resolves to whatever the model says — first time a verdict is shown', () => {
  const waiting = provisional({ local_status: 'checking' });
  // «Je relis…» → corrections: there was no earlier verdict to reverse.
  assert.equal(V.settleShownCorrection(waiting, wrong), wrong);
  // «Je relis…» → «Right».
  const model = checked();
  assert.equal(V.settleShownCorrection(waiting, model), model);
  // Nothing shown yet: the first correction is taken as it comes.
  assert.equal(V.settleShownCorrection(null, wrong), wrong);
  assert.equal(V.settleShownCorrection(undefined, right), right);
});

test('a confirming model reading is taken as it comes', () => {
  const confirmed = checked({ second_check: { status: 'complete', verdict_changed: false, verdict: 'accepted' } });
  assert.equal(V.settleShownCorrection(right, confirmed), confirmed);
  assert.equal(V.settleShownCorrection(right, right), right);
});

test('the screen sequence never shows «Right» and then corrections', () => {
  // What the learner is shown after each arrival, given the rule.
  const shownAfter = (arrivals) => {
    let held = null;
    const log = [];
    for (const arrival of arrivals) {
      held = V.settleShownCorrection(held, arrival);
      const phase = V.productionPhase(held);
      log.push(V.showsVerdict(phase) ? (seanceAssessment(held) === 'correct' ? 'right' : 'corrections') : 'reading');
    }
    return log;
  };
  // The owner’s test: local check, then the model finds three issues.
  assert.deepEqual(shownAfter([provisional({ local_status: 'checking' }), wrong]), ['reading', 'corrections']);
  assert.deepEqual(shownAfter([provisional(), wrong]), ['reading', 'corrections'], 'an older server too');
  // A real match stays a match, whatever the model says later.
  assert.deepEqual(shownAfter([right, right, wrong]), ['right', 'right', 'right']);
  assert.deepEqual(shownAfter([right, checked()]), ['right', 'right']);
  // Never «right» → «corrections», in any order of arrival.
  for (const arrivals of [[right, wrong], [right, wrong, wrong], [provisional(), right, wrong]]) {
    const log = shownAfter(arrivals);
    assert.ok(!(log.includes('right') && log.slice(log.indexOf('right')).includes('corrections')), log.join(' → '));
  }
});

test('one correction block: notes are deduplicated whichever way they arrive', () => {
  assert.deepEqual(forgeCorrectionNotes(wrong), ['Adjective position.'], 'three errata, one explanation');
  assert.deepEqual(forgeCorrectionNotes({ notes_native: ['A.', 'B.', 'A.'], errata: [{ why_wrong: 'x' }] }), ['A.', 'B.'], 'the server’s notes win');
  assert.deepEqual(forgeCorrectionNotes({ errata: [] }), []);
  assert.deepEqual(forgeCorrectionNotes(null), []);
});
