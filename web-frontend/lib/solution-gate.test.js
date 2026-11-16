// node --test lib/solution-gate.test.js
//
// Owner, 2026-11-13: before a second chance the screen shows where and why, never what is
// right. The server withholds the solution (app/services/solution_gate.py); these pin how
// the screen reads the payload it gets.

const assert = require('node:assert/strict');
const path = require('node:path');
const { test } = require('node:test');

require(path.join(__dirname, '..', 'node_modules/sucrase/register/ts'));
const G = require('./solution-gate.ts');

const WITHHELD = {
  solution: { state: 'withheld', language: 'de' },
  corrected_answer: '',
  marks: [{ start: 9, end: 11, text: 'un', erratum: 0 }],
  errata: [
    { learner_text: 'un carte', corrected_target: '', hint: '„Un“ ist maskulin.', task_error_type: 'gender_agreement', mark: { start: 9, end: 11 } },
    { learner_text: '', corrected_target: '', hint: 'Deine Antwort verwendet nicht das geforderte Modalverb mit Infinitiv.', task_error_type: 'task_compliance' },
  ],
};

test('the state of the solution, from the payload', () => {
  assert.equal(G.solutionState(WITHHELD), 'withheld');
  assert.equal(G.solutionState({ solution: { state: 'shown', revealed_by: 'repair' } }), 'spent');
  assert.equal(G.solutionState({ solution: { state: 'shown' } }), 'shown');
  assert.equal(G.solutionState({}), 'none');
  assert.equal(G.solutionWithheld(WITHHELD), true);
});

test('«Try again» only while the chance is open', () => {
  assert.equal(G.retryOffered(WITHHELD), true);
  assert.equal(G.retryOffered({ solution: { state: 'shown', revealed_by: 'reveal' } }), false);
  assert.equal(G.retryOffered({ solution: { state: 'shown' } }), false);
  assert.equal(G.retryOffered({}), true);
});

test('the learner’s line, marked where it is wrong', () => {
  assert.deepEqual(G.markedLine("Oui j'ai un carte bancaire", WITHHELD.marks), [
    { text: "Oui j'ai ", marked: false },
    { text: 'un', marked: true },
    { text: ' carte bancaire', marked: false },
  ]);
  // A mark that does not fit the line is dropped, never guessed.
  assert.deepEqual(G.markedLine('court', [{ start: 2, end: 40 }]), [{ text: 'court', marked: false }]);
});

test('the repair in place holds what the learner wrote, never a fix', () => {
  const parts = G.withheldRepairParts("Oui j'ai un carte bancaire", WITHHELD.marks);
  assert.deepEqual(parts, [{ text: "Oui j'ai " }, { wrong: 'un', fix: '', erratum: 0 }, { text: ' carte bancaire' }]);
  assert.equal(G.withheldRepairParts('rien', []), null);
});

test('one reason first, the task as one quiet line, never the same sentence twice', () => {
  const hints = G.withheldHints({
    ...WITHHELD,
    errata: [...WITHHELD.errata, { hint: '„Un“ ist maskulin.', task_error_type: 'gender_agreement' }],
  });
  assert.equal(hints.reason, '„Un“ ist maskulin.');
  assert.deepEqual(hints.more, []);
  assert.equal(hints.task, 'Deine Antwort verwendet nicht das geforderte Modalverb mit Infinitiv.');
});
