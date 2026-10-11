// node --test lib/forge-followup.test.js
//
// WP-103 T8 — La Forge's «Correct / À corriger» leads somewhere: after «À
// corriger» the learner corrects the sentence (a field, or tiles at A1);
// «Passer» shows the right one; either way it is seen.

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

const F = require('./forge-followup.ts');

const WRONG_ITEM = {
  id: 'c1',
  prompt: 'Lila cherche un poster grand (Lila is looking for a big poster)',
  labels: ['Correct', 'À corriger'],
  correct_label: 'À corriger',
  classify_kind: 'judgement',
};
const RIGHT_ITEM = { ...WRONG_ITEM, id: 'c2', prompt: 'Lila cherche un grand poster', correct_label: 'Correct' };

const FOLLOW_UP = {
  kind: 'correct_it',
  source_fr: 'Lila cherche un poster grand.',
  goal_native: 'Correct the sentence.',
};

test('a wrong sentence with a follow-up: the sentence quoted, the goal, the right form', () => {
  const { followUp, correctedFr } = F.classifyRepair(WRONG_ITEM, {
    corrected_fr: 'Lila cherche un grand poster.',
    follow_up: FOLLOW_UP,
  });
  assert.equal(correctedFr, 'Lila cherche un grand poster.');
  assert.equal(followUp.kind, 'correct_it');
  assert.equal(followUp.sourceFr, 'Lila cherche un poster grand.');
  assert.equal(followUp.goalNative, 'Correct the sentence.');
  assert.deepEqual(followUp.accepted, ['Lila cherche un grand poster.']);
  assert.equal(followUp.options, null, 'a field, unless the item carries options');
});

test('the follow-up is read from the correction, its forge block, or the item', () => {
  assert.ok(F.classifyRepair(WRONG_ITEM, { forge: { follow_up: FOLLOW_UP }, corrected_fr: 'x y z' }).followUp);
  assert.ok(F.classifyRepair({ ...WRONG_ITEM, follow_up: FOLLOW_UP, corrected_fr: 'Lila cherche un grand poster.' }, {}).followUp);
  // Missing pieces fall back: the source is the item's own sentence, without its gloss.
  const bare = F.classifyRepair(WRONG_ITEM, { follow_up: { kind: 'correct_it' }, corrected_fr: 'Lila cherche un grand poster.' });
  assert.equal(bare.followUp.sourceFr, 'Lila cherche un poster grand');
  assert.equal(bare.followUp.goalNative, null);
});

test('at A1 an item that carries options is tiles', () => {
  const { followUp } = F.classifyRepair(WRONG_ITEM, {
    corrected_fr: 'Lila cherche un grand poster.',
    follow_up: { ...FOLLOW_UP, options: ['Lila', 'cherche', 'un', 'grand', 'poster', 'petit'] },
  });
  assert.equal(followUp.options.length, 6);
  const one = F.classifyRepair(WRONG_ITEM, { corrected_fr: 'a b c', follow_up: { ...FOLLOW_UP, options: ['seul'] } });
  assert.equal(one.followUp.options, null, 'a single tile is not a bank');
});

test('without a follow-up the corrected sentence is still offered', () => {
  const repair = F.classifyRepair(WRONG_ITEM, { corrected_fr: 'Lila cherche un grand poster.' });
  assert.equal(repair.followUp, null);
  assert.equal(repair.correctedFr, 'Lila cherche un grand poster.', '«La bonne phrase»');
  assert.deepEqual(F.classifyRepair(WRONG_ITEM, {}), { followUp: null, correctedFr: null }, 'an older payload adds nothing');
  assert.deepEqual(F.classifyRepair(WRONG_ITEM, null), { followUp: null, correctedFr: null });
});

test('a right sentence has nothing to correct; other kinds of sort are not judgements', () => {
  assert.deepEqual(F.classifyRepair(RIGHT_ITEM, { corrected_fr: 'x' }), { followUp: null, correctedFr: null });
  const pair = { id: 'p', prompt: 'Which sentence says…', labels: ['a b c', 'a c b'], correct_label: 'a b c', classify_kind: 'minimal_pair' };
  assert.deepEqual(F.classifyRepair(pair, { corrected_fr: 'x' }), { followUp: null, correctedFr: null });
  assert.equal(F.isJudgementItem(WRONG_ITEM), true);
  assert.equal(F.isJudgementItem(pair), false);
  assert.equal(F.isJudgementItem({ labels: ['Correct', 'À corriger'] }), true, 'without the kind, by its labels');
  assert.equal(F.isJudgementItem(null), false);
  // A follow-up of another kind is not drawn.
  assert.equal(F.classifyRepair(WRONG_ITEM, { corrected_fr: 'x y', follow_up: { kind: 'other', source_fr: 'a' } }).followUp, null);
});

test('graded like a transform: the right sentence, whatever the case, quotes or final stop', () => {
  const { followUp } = F.classifyRepair(WRONG_ITEM, {
    corrected_fr: 'Lila cherche un grand poster.',
    follow_up: { ...FOLLOW_UP, accepted_fr: ['Lila cherche une grande affiche.'] },
  });
  for (const said of [
    'Lila cherche un grand poster.',
    'lila cherche un grand poster',
    '  Lila  cherche un grand poster !',
    '« Lila cherche un grand poster. »',
    'Lila cherche une grande affiche',
  ]) {
    assert.equal(F.followUpMatches(said, followUp), true, said);
  }
  for (const said of ['Lila cherche un poster grand.', '', '   ', 'Lila cherche un grand poste']) {
    assert.equal(F.followUpMatches(said, followUp), false, JSON.stringify(said));
  }
  // Tiles: the elision joins up.
  const elided = F.classifyRepair(WRONG_ITEM, { corrected_fr: 'J’ai un grand poster.', follow_up: FOLLOW_UP });
  assert.equal(F.followUpMatches(['J’', 'ai', 'un', 'grand', 'poster'], elided.followUp), true);
  assert.equal(F.followUpMatches("J' ai un grand poster", elided.followUp), true);
  // Accents matter in French.
  assert.equal(F.followUpMatches('Il a mange', F.classifyRepair(WRONG_ITEM, { corrected_fr: 'Il a mangé', follow_up: FOLLOW_UP }).followUp), false);
});

test('one shot, like a transform: right, or the right sentence is shown', () => {
  const { followUp } = F.classifyRepair(WRONG_ITEM, { corrected_fr: 'Lila cherche un grand poster.', follow_up: FOLLOW_UP });
  assert.equal(F.followUpOutcome('Lila cherche un grand poster', followUp), 'right');
  assert.equal(F.followUpOutcome('Lila cherche un poster', followUp), 'revealed');
  assert.equal(F.followUpSettled('right'), true);
  assert.equal(F.followUpSettled('revealed'), true);
  assert.equal(F.followUpSettled(null), false);
});
