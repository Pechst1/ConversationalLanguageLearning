/**
 * P11 · the last panel always has a way on.
 *
 * 17 Nov walk: «La suite s’écrit…» held the last panel with no button and no
 * timeout. Now the slot says the ending is being written from the first second;
 * after 8 s (R2; P11 had 30 s) it is «Continuer» again with «the ending will be there next time»,
 * the hook lets that tap pass, and the journey keeps polling behind it.
 *
 * Run: `node --test components/atelier-v2/journey/p11-finale-wait.test.js`
 */

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');

const HERE = __dirname;
const WEB_ROOT = path.resolve(HERE, '../../..');

require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolveWithAlias(request, ...rest) {
  if (typeof request === 'string' && request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

const READER = path.join(WEB_ROOT, 'components/feuilleton/reader');
const { FINALE_ESCAPE_MS, finaleNav, finaleWaitOver } = require(path.join(READER, 'finale-wait.ts'));
const { readerCopy } = require(path.join(READER, 'reader-copy.ts'));
const {
  continueAfterStoryWait,
  polledSnapshotIsCurrent,
  storyPollTarget,
} = require(path.join(HERE, 'journey-state.ts'));

const waiting = { isLast: true, waiting: true, filed: false };

test('the last panel says the ending is being written, then lets the learner on after 8 s', () => {
  assert.equal(FINALE_ESCAPE_MS, 8_000);
  assert.equal(finaleNav({ ...waiting, waitedMs: 0 }), 'writing');
  assert.equal(finaleNav({ ...waiting, waitedMs: 7_999 }), 'writing');
  assert.equal(finaleNav({ ...waiting, waitedMs: 8_000 }), 'continue_late');
  assert.equal(finaleNav({ ...waiting, waitedMs: null }), 'writing');
  assert.equal(finaleNav({ ...waiting, waiting: false, waitedMs: 60_000 }), 'normal');
  assert.equal(finaleNav({ ...waiting, isLast: false, waitedMs: 60_000 }), 'normal');
  assert.equal(finaleWaitOver(1_000, 9_000), true);
  assert.equal(finaleWaitOver(1_000, 8_999), false);
  assert.equal(finaleWaitOver(null, 99_000), false);
});

test('both lines exist in fr, de and en', () => {
  for (const language of ['fr', 'de', 'en']) {
    const t = readerCopy(language);
    assert.ok(t.ending_writing && t.ending_later, language);
  }
  assert.equal(readerCopy('fr').ending_writing, 'La suite s’écrit…');
});

function step(id, ordinal, kind, prompt = {}) {
  return { id, ordinal, kind, status: 'active', prompt };
}

test('«Continuer» passes a late ending only after the wait, and never before a later act', () => {
  const pending = step('r1', 3, 'resolution', { story_pending: true });
  const oneAct = { id: 'j', status: 'active', revision: 4, current_step_id: 'r1', steps: [step('s', 1, 'scene'), pending] };
  assert.equal(continueAfterStoryWait(oneAct, pending, false), false, 'not before 8 s');
  assert.equal(continueAfterStoryWait(oneAct, pending, true), true, 'after 8 s the learner goes on');
  const twoActs = { ...oneAct, steps: [...oneAct.steps, step('s2', 4, 'scene'), step('r2', 5, 'resolution')] };
  assert.equal(continueAfterStoryWait(twoActs, pending, true), false, 'the server holds a later act');
  const settled = step('r1', 3, 'resolution', { story_pending: false });
  assert.equal(continueAfterStoryWait(oneAct, settled, false), true);
});

test('the journey keeps polling for a late ending behind the learner, never undoing a tap', () => {
  const pending = step('r1', 3, 'resolution', { story_pending: true });
  pending.status = 'completed';
  const left = { id: 'j', status: 'completed', revision: 7, current_step_id: null, steps: [pending] };
  assert.equal(storyPollTarget(left), 'j');
  assert.equal(polledSnapshotIsCurrent({ id: 'j', revision: 6 }, { id: 'j', revision: 7 }), false);
  assert.equal(polledSnapshotIsCurrent({ id: 'j', revision: 7 }, { id: 'j', revision: 7 }), true);
});

test('the hook asks continueAfterStoryWait, and the reader draws both slots', () => {
  const hook = fs.readFileSync(path.join(HERE, 'useDailyJourney.ts'), 'utf8');
  assert.match(hook, /continueAfterStoryWait\(journeyRef\.current, current, waitOver\)/);
  assert.match(hook, /polledSnapshotIsCurrent\(next, journeyRef\.current\)/);
  const reader = fs.readFileSync(path.join(READER, 'FeuilletonReader.tsx'), 'utf8');
  assert.match(reader, /t\.ending_writing/);
  assert.match(reader, /t\.ending_later/);
});
