// node --test lib/repair-parts.test.js
const assert = require('node:assert/strict');
const test = require('node:test');
require('sucrase/register/ts');
const { repairParts, assembleRepair, gapIsFixed } = require('./repair-parts.ts');

const LINE = "J'ai fini les taches avec un grand motivation";
const ERRATA = [
  { learner_text: 'taches', corrected_target: 'tâches', task_error_type: 'spelling' },
  { learner_text: 'un grand', corrected_target: 'une grande', task_error_type: 'agreement' },
  { learner_text: '', corrected_target: '', task_error_type: 'task_compliance' },
];

test('the line is cut into the parts to keep and the parts to fix', () => {
  const parts = repairParts(LINE, ERRATA);
  assert.deepEqual(parts, [
    { text: "J'ai fini les " },
    { wrong: 'taches', fix: 'tâches', erratum: 0 },
    { text: ' avec ' },
    { wrong: 'un grand', fix: 'une grande', erratum: 1 },
    { text: ' motivation' },
  ]);
  assert.equal(assembleRepair(parts, {}), LINE);
  assert.equal(assembleRepair(parts, { 1: 'tâches', 3: 'une grande' }), "J'ai fini les tâches avec une grande motivation");
});

test('a correction that cannot be placed sends the line back to a whole retype', () => {
  assert.equal(repairParts(LINE, [{ learner_text: '', corrected_target: 'le' }]), null);
  assert.equal(repairParts(LINE, [{ learner_text: 'chaises', corrected_target: 'tables' }]), null);
  assert.equal(repairParts(LINE, [{ learner_text: LINE, corrected_target: 'x' }]), null);
  assert.equal(repairParts(LINE, []), null);
  assert.equal(repairParts('Elle est partie et il est partie', [{ learner_text: 'partie', corrected_target: 'parti' }]), null);
});

test('a word inside another word is not the word', () => {
  assert.deepEqual(repairParts('Il avec a fini', [{ learner_text: 'a', corrected_target: 'est' }])[1], { wrong: 'a', fix: 'est', erratum: 0 });
});

// #282 (live walk 22 Oct): «Replace «à le» with «au» here.» over a field holding
// «à le marché aux puces»: typing «au», as told, was refused. The gap holds the words
// that differ, so the instruction, the field and the fix say the same thing.
test('a gap holds only the words that differ, and the rest of the stretch stays text', () => {
  const line = 'Il est à le marché aux puces avec Romy';
  const parts = repairParts(line, [{ learner_text: 'à le marché aux puces', corrected_target: 'au marché aux puces', task_error_type: 'preposition' }]);
  assert.deepEqual(parts, [
    { text: 'Il est ' },
    { wrong: 'à le', fix: 'au', erratum: 0 },
    { text: ' marché aux puces avec Romy' },
  ]);
  assert.equal(assembleRepair(parts, { 1: 'au' }), 'Il est au marché aux puces avec Romy');
  assert.ok(gapIsFixed('au', parts[1].fix));
});

test('an insertion keeps a word to hold its gap, a stretch with nothing in common stays whole', () => {
  assert.deepEqual(
    repairParts('Je vois la maison', [{ learner_text: 'la maison', corrected_target: 'la grande maison' }])[1],
    { wrong: 'maison', fix: 'grande maison', erratum: 0 },
  );
  assert.deepEqual(
    repairParts('Un grand maison', [{ learner_text: 'Un grand', corrected_target: 'Une grande' }])[0],
    { wrong: 'Un grand', fix: 'Une grande', erratum: 0 },
  );
});

test('a gap is fixed by its fix, accents counting, typography not', () => {
  assert.ok(gapIsFixed('Tâches', 'tâches'));
  assert.ok(!gapIsFixed('taches', 'tâches'));
  assert.ok(gapIsFixed('l’hôtel', "l'hôtel"));
});
