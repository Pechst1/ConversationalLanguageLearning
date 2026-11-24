// node --test components/epreuve/forge-count-1044.test.js
//
// #1044 (live walk 24 Nov 2026, A1.1 day 42, La Forge item 2/4). «Romy demande combien
// annees je ai. Je ai soixante-deux ans.» The sheet said «3 corrections», listed one
// reason (and one behind «More») and marked only «combien annees»: both «je ai» stayed
// unmarked. The count came from the errata, the list from the notes (one per issue) and
// the marks from what could be placed. The payload below is the server's reading of the
// model's three fixes (tests/test_forge_corrections_agree_1044.py).

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
const { epreuveCopy } = require('./epreuve-copy.ts');
const { feedbackFromFreeformCorrection } = require('../../pages/atelier.tsx');
const { repairParts } = require('../../lib/repair-parts.ts');

const LEARNER = 'Romy demande combien annees je ai. Je ai soixante-deux ans.';
const AGE = '“Combien d’années” asks for a number of years; this context asks for age, so use “quel âge”.';
const ELISION = "Before a vowel, «je» becomes «j'»: «j'ai».";
const erratum = (learner_text, corrected_target, why_wrong) => ({
  item_id: '', display_label: 'Grammar', learner_text, corrected_target, why_wrong, repair_hint: '', severity: 2, task_error_type: 'grammar',
});
const CORRECTION = {
  verdict: 'partial',
  errata: [erratum('combien annees', 'quel âge', AGE), erratum('je ai', "j'ai", ELISION), erratum('Je ai', "J'ai", ELISION)],
  corrected_answer: "Romy demande quel âge j'ai. J'ai soixante-deux ans.",
  notes_native: [AGE, ELISION],
};

test('the number in the header is the number of corrections listed', () => {
  const t = epreuveCopy('en');
  const feedback = feedbackFromFreeformCorrection(CORRECTION, '', LEARNER, t);
  const [card] = feedback.issues;
  const listed = String(card.why_wrong || '').split('\n').filter(Boolean);
  assert.equal(listed.length, 2, listed.join(' | '));
  assert.equal(card.display_label, '2 corrections', `header «${card.display_label}» over ${listed.length} listed corrections`);
});

test('each word the correction changes is marked, «je ai» both times', () => {
  const parts = repairParts(LEARNER, CORRECTION.errata);
  assert.ok(parts, 'the corrections could not be placed: nothing is marked, the line is retyped whole');
  assert.deepEqual(
    parts.filter((part) => 'wrong' in part).map((part) => [part.wrong, part.fix]),
    [['combien annees', 'quel âge'], ['je ai', "j'ai"], ['Je ai', "J'ai"]],
  );
});

test('a stretch named once where it stands twice is still not guessed', () => {
  const one = [{ learner_text: 'partie', corrected_target: 'parti' }];
  assert.equal(repairParts('Elle est partie et il est partie', one), null);
  const both = repairParts('Elle est partie et il est partie', [...one, ...one]);
  assert.deepEqual(both && both.filter((part) => 'wrong' in part).map((part) => part.wrong), ['partie', 'partie']);
});
