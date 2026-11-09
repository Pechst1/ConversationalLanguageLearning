const assert = require('node:assert/strict');
require('sucrase/register/ts');
const { seanceAssessment } = require('./seance-feedback.ts');
assert.equal(seanceAssessment({ verdict: 'incorrect', errata: [] }), 'needs_work');
assert.equal(seanceAssessment({ verdict: 'partial', errata: [] }), 'needs_work');
assert.equal(seanceAssessment({ verdict: 'accepted', errata: [], ai_review: { status: 'failed' } }), 'unavailable');
assert.equal(seanceAssessment({ verdict: 'accepted', errata: [], assessment_status: 'unavailable' }), 'unavailable');
assert.equal(seanceAssessment({ verdict: 'accepted', errata: [{ task_error_type: 'task_compliance' }] }), 'needs_work');
assert.equal(seanceAssessment({ verdict: 'accepted', missing_targets: [{}] }), 'needs_work');
assert.equal(seanceAssessment({ verdict: 'accepted', lexical_gaps: [{}] }), 'needs_work');
assert.equal(seanceAssessment({ verdict: 'accepted', errata: [], ai_review: { status: 'complete' } }), 'correct');
assert.equal(seanceAssessment({ verdict: 'correct', errata: [], ai_review: { status: 'not_applicable' } }), 'correct');
console.log('Séance assessment regression checks passed');
assert.equal(seanceAssessment({ verdict: 'accepted', corrected_answer: 'there is no question', correction_debug: {fallback_used: true}, ai_review: {status: 'not_applicable'} }), 'unavailable');
assert.equal(seanceAssessment({ verdict: 'incorrect', assessment_status: 'checked', ai_review: {status: 'failed'} }), 'needs_work');

// WP-S1: a provisional local verdict is shown at once, not as «pending».
{
  const { correctRunFrom, runOutcome, secondCheckChange } = require('./seance-feedback.ts');
  const provisional = { verdict: 'accepted', errata: [], assessment_status: 'provisional', corrected_answer: 'Si je peux, je viendrai.', correction_debug: { fallback_used: true }, ai_review: { status: 'pending' } };
  assert.equal(seanceAssessment(provisional), 'correct');
  assert.equal(seanceAssessment({ ...provisional, verdict: 'partial', errata: [{ task_error_type: 'task_compliance' }] }), 'needs_work');

  const right = { verdict: 'correct', errata: [], assessment_status: 'checked', ai_review: { status: 'not_applicable' } };
  const wrong = { verdict: 'incorrect', errata: [{ task_error_type: 'agreement' }], assessment_status: 'checked' };
  const unchecked = { verdict: 'needs_review', errata: [], assessment_status: 'unavailable', ai_review: { status: 'failed' } };
  const legacyUnchecked = { verdict: 'accepted', errata: [], corrected_answer: 'x', correction_debug: { fallback_used: true } };

  // Unchecked and provisional answers never count as correct…
  assert.equal(runOutcome(unchecked), 'skips');
  assert.equal(runOutcome(legacyUnchecked), 'skips');
  assert.equal(runOutcome(provisional), 'skips');
  assert.equal(runOutcome(right), 'extends');
  assert.equal(runOutcome(wrong), 'breaks');
  // …and never extend the combo: two right answers around an unchecked one is a run of 2, not 3.
  assert.equal(correctRunFrom([right, unchecked, right]), 2);
  assert.equal(correctRunFrom([right, unchecked, provisional, unchecked]), 1);
  assert.equal(correctRunFrom([unchecked, unchecked]), 0);
  assert.equal(correctRunFrom([right, wrong, right, unchecked]), 1);
  // A task-compliance note alone keeps the line correct for the run.
  assert.equal(correctRunFrom([right, { verdict: 'accepted', errata: [{ task_error_type: 'task_compliance' }], assessment_status: 'checked' }]), 2);
  // Once the model's verdict lands the answer counts.
  assert.equal(correctRunFrom([right, { ...provisional, assessment_status: 'checked', correction_debug: { fallback_used: false }, ai_review: { status: 'complete' } }]), 2);

  // The «second check» note appears only when the verdict changed.
  assert.equal(secondCheckChange(provisional), null);
  assert.equal(secondCheckChange({ verdict: 'accepted', second_check: { status: 'complete', verdict_changed: false, verdict: 'accepted' } }), null);
  assert.equal(secondCheckChange({ verdict: 'partial', second_check: { status: 'complete', verdict_changed: true, verdict: 'partial' } }), 'worse');
  assert.equal(secondCheckChange({ verdict: 'accepted', second_check: { status: 'complete', verdict_changed: true, verdict: 'accepted' } }), 'better');
  console.log('Séance run and second-check checks passed');
}

// Owner, 2026-10-19: a rule check («Regelprüfung») whose free answer the rule's
// detector passed on the spot read as «Die zweite Prüfung brach ab».
{
  const testOut = {
    verdict: 'correct', score_0_4: 4, errata: [], assessment_status: 'checked', graded_by: 'local_test_out',
    corrected_answer: 'Ils ont envoyé un message à Romy le dernier samedi.',
    correction_debug: { fallback_used: true }, ai_review: { status: 'not_applicable' },
  };
  assert.equal(seanceAssessment(testOut), 'correct');
  assert.equal(seanceAssessment({ ...testOut, verdict: 'incorrect' }), 'needs_work');
}

// #471 (6 Nov walk): the server's assessment_status is the one source of truth.
// A key-accepted answer is stored «checked» with correction_debug.fallback_used
// (the rule-based key, no model); the client must not re-derive «unchecked»
// from that debug field. Payload of attempt 7c9c5dcf, as the API sent it.
{
  const { runOutcome, correctRunFrom } = require('./seance-feedback.ts');
  const keyAccepted = {
    assessment_status: 'checked', verdict: 'correct', local_status: 'right', errata: [],
    ai_review: { status: 'not_applicable' },
    correction_debug: { fallback_used: true },
    corrected_answer: 'je suis jeune, Lila',
  };
  assert.equal(seanceAssessment(keyAccepted), 'correct');
  assert.equal(runOutcome(keyAccepted), 'extends');
  assert.equal(correctRunFrom([keyAccepted, keyAccepted]), 2);
  // A checked wrong key answer is wrong, not unchecked.
  assert.equal(seanceAssessment({ ...keyAccepted, verdict: 'incorrect', errata: [{ task_error_type: 'agreement' }] }), 'needs_work');
  // An answer the server stored «unavailable» still reads as unchecked and moves nothing.
  const unavailable = { ...keyAccepted, assessment_status: 'unavailable', verdict: 'needs_review', corrected_answer: '' };
  assert.equal(seanceAssessment(unavailable), 'unavailable');
  assert.equal(runOutcome(unavailable), 'skips');
  assert.equal(seanceAssessment({ ...unavailable, corrected_answer: 'x' }), 'unavailable');
  console.log('Séance server-status authority checks passed');
}
