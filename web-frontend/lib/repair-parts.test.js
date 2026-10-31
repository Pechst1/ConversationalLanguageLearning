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

// #381 (live walk 30 Oct): «Je voudrais un tomate, sil te plait.» The gap holds «un»
// («tomate» stays text, #282), the correction above it shows «un tomate → une tomate»,
// and the learner typed «une tomate» there: the right fix was drawn red, and the line
// sent read «une tomate tomate».
const WALK_LINE = 'Je voudrais un tomate, sil te plait.';
const WALK_ERRATA = [
  { learner_text: 'un tomate', corrected_target: 'une tomate', task_error_type: 'agreement' },
  { learner_text: 'sil te plait', corrected_target: "s'il te plaît", task_error_type: 'spelling' },
];
const { gapTyped, isRepairableLine, repairState } = require('./repair-parts.ts');

test('#381 · a gap typed with the words the line already has around it holds the fix', () => {
  const parts = repairParts(WALK_LINE, WALK_ERRATA);
  assert.deepEqual(parts, [
    { text: 'Je voudrais ' },
    { wrong: 'un', fix: 'une', erratum: 0 },
    { text: ' tomate, ' },
    { wrong: 'sil te plait', fix: "s'il te plaît", erratum: 1 },
    { text: '.' },
  ]);
  assert.equal(gapTyped(parts, 1, 'une tomate'), 'une');
  assert.ok(gapIsFixed(gapTyped(parts, 1, 'une tomate'), parts[1].fix), '«une tomate» is not red');
  assert.ok(gapIsFixed(gapTyped(parts, 1, 'Une Tomate'), parts[1].fix), 'case is typography');
  // Still wrong: the accent is the fix.
  assert.ok(!gapIsFixed(gapTyped(parts, 3, "s'il te plait"), parts[3].fix));
  // The line sent is the line the server accepts: the learner's, each gap fixed.
  const fixedLine = parts.map((part) => ('text' in part ? part.text : part.fix)).join('');
  assert.equal(fixedLine, "Je voudrais une tomate, s'il te plaît.");
  assert.equal(assembleRepair(parts, { 1: 'une tomate', 3: 's’il te plaît' }), 'Je voudrais une tomate, s’il te plaît.');
  assert.ok(gapIsFixed(assembleRepair(parts, { 1: 'une tomate', 3: 's’il te plaît' }), fixedLine));
});

test('#381 · neighbouring words come off either side, and only to leave the fix', () => {
  const parts = repairParts('Demain je vais à le marché avec Paul', [
    { learner_text: 'je vais à le marché', corrected_target: 'je vais au marché', task_error_type: 'preposition' },
  ]);
  assert.deepEqual(parts[1], { wrong: 'à le', fix: 'au', erratum: 0 });
  assert.equal(gapTyped(parts, 1, 'je vais au marché'), 'au');
  assert.equal(gapTyped(parts, 1, 'vais au'), 'au');
  assert.equal(gapTyped(parts, 1, 'au marché.'), 'au');
  // A wrong fix stays as typed, neighbours and all: it is red and the line is refused.
  assert.equal(gapTyped(parts, 1, 'je vais à le marché'), 'je vais à le marché');
  assert.equal(gapTyped(parts, 1, 'aux marché'), 'aux marché');
  // Words the line does not hold there are not neighbours.
  assert.equal(gapTyped(parts, 1, 'au supermarché'), 'au supermarché');
  assert.equal(assembleRepair(parts, { 1: 'aux marché' }), 'Demain je vais aux marché marché avec Paul');
  // A gap typed as its fix is left alone, spaces and all.
  assert.equal(gapTyped(parts, 1, ' au '), ' au ');
  assert.equal(gapTyped([{ text: 'x' }], 0, 'x'), 'x', 'text is not a gap');
});

test('#381 · the band says the line is mended only once every repair on screen is accepted', () => {
  const line = { learner_text: WALK_LINE, corrected_target: "Je voudrais une tomate, s'il te plaît." };
  const state = (issues, repairs, extra = {}) => repairState({ issues, repairs, inPlace: false, isLabelCompare: false, needsNewAnswer: false, ...extra });
  // A free line fixed in place (La Forge's production rounds).
  assert.deepEqual(state([line], { 0: { status: 'ok' } }, { inPlace: true }), { complete: true, mended: true });
  assert.deepEqual(state([line], { 0: { status: 'no' } }, { inPlace: true }), { complete: false, mended: false });
  assert.deepEqual(state([line], {}, { inPlace: true }), { complete: false, mended: false });
  // Corrections retyped one by one: every one must be accepted.
  const two = [line, { learner_text: 'il a allé', corrected_target: 'il est allé hier.' }];
  assert.deepEqual(state(two, { 0: { status: 'ok' }, 1: { status: 'no' } }), { complete: false, mended: false });
  assert.deepEqual(state(two, { 0: { status: 'ok' }, 1: { status: 'ok' } }), { complete: true, mended: true });
  // A one-word fix has no repair step: «Continue» is there, the «Not yet» stands.
  assert.deepEqual(state([{ learner_text: 'taches', corrected_target: 'tâches' }], {}), { complete: true, mended: false });
  // A line to write anew, or a label compare, is never «mended».
  assert.deepEqual(state([line, { task_error_type: 'task_compliance', corrected_target: '' }], { 0: { status: 'ok' } }, { inPlace: true, needsNewAnswer: true }), { complete: false, mended: false });
  assert.deepEqual(state([line], { 0: { status: 'ok' } }, { isLabelCompare: true }), { complete: true, mended: false });
  // The field in place counts even on a line too short to need a retype.
  assert.deepEqual(state([{ learner_text: 'Merci beaucop', corrected_target: 'Merci beaucoup' }], { 0: { status: 'ok' } }, { inPlace: true }), { complete: true, mended: true });
  assert.ok(isRepairableLine('Il est allé hier.') && !isRepairableLine('tâches') && !isRepairableLine('Merci beaucoup'));
});
