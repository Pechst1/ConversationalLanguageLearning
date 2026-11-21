/**
 * P11 · a word graded offline is kept.
 *
 * 17 Nov walk: offline, «Weiß ich» said the review could not be saved, put the card
 * back at the end and lost the grade. Now the grade is held on the device, the card
 * stays filed (the counter moves on), and the grade is sent on reconnect or next open.
 *
 * Run: `node --test lib/grade-queue.test.js`
 */

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');

const WEB_ROOT = path.resolve(__dirname, '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolveWithAlias(request, ...rest) {
  if (typeof request === 'string' && request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

const queue = require('./grade-queue.ts');
const { fileCard, EMPTY_PROGRESS } = require('../components/lexique/deck-session.ts');

function memoryStorage() {
  const map = new Map();
  return {
    getItem: (key) => (map.has(key) ? map.get(key) : null),
    setItem: (key, value) => map.set(key, String(value)),
    removeItem: (key) => map.delete(key),
    key: (i) => [...map.keys()][i] ?? null,
    get length() { return map.size; },
  };
}

const NETWORK = Object.assign(new Error('Network Error'), { code: 'ERR_NETWORK' });
const REFUSED = Object.assign(new Error('422'), { response: { status: 422 } });

test('only a grade the network lost is kept', () => {
  assert.equal(queue.gradeLostToNetwork(NETWORK), true);
  assert.equal(queue.gradeLostToNetwork({ code: 'ECONNABORTED' }), true);
  assert.equal(queue.gradeLostToNetwork({ response: { status: 503 } }), true);
  assert.equal(queue.gradeLostToNetwork(REFUSED), false);
});

test('an offline grade is queued, sent on reconnect, and the card stays counted', async () => {
  const storage = memoryStorage();
  const now = 1_000_000;
  queue.enqueueGrade({ word_id: 7, rating: 2, format: 'flashcard' }, storage, now);
  queue.enqueueGrade({ word_id: 9, rating: 0, format: 'flashcard' }, storage, now + 1);
  queue.enqueueGrade({ word_id: 7, rating: 3, format: 'flashcard' }, storage, now + 2);
  assert.deepEqual(queue.readGradeQueue(storage, now + 3).map((g) => [g.word_id, g.rating]), [[9, 0], [7, 3]]);

  // Still offline: nothing is lost.
  const offline = await queue.flushGradeQueue(async () => { throw NETWORK; }, storage, now + 4);
  assert.deepEqual(offline, { sent: 0, left: 2 });

  // Reconnected: both go, in order.
  const sent = [];
  const back = await queue.flushGradeQueue(async (g) => { sent.push(g.word_id); }, storage, now + 5);
  assert.deepEqual(back, { sent: 2, left: 0 });
  assert.deepEqual(sent, [9, 7]);
  assert.equal(storage.getItem(queue.GRADE_QUEUE_KEY), null);

  // The counter: a queued card is filed, not asked again.
  const filed = fileCard(EMPTY_PROGRESS, 7, false);
  assert.ok(filed.filed.has(7));
  assert.deepEqual(filed.again, []);
});

test('a refused grade is dropped, a lost one stops the run', async () => {
  const storage = memoryStorage();
  for (const id of [1, 2, 3]) queue.enqueueGrade({ word_id: id, rating: 2, format: 'flashcard' }, storage, id);
  const result = await queue.flushGradeQueue(async (g) => {
    if (g.word_id === 1) throw REFUSED;
    if (g.word_id === 2) throw NETWORK;
  }, storage, 10);
  assert.deepEqual(result, { sent: 0, left: 2 });
  assert.deepEqual(queue.readGradeQueue(storage, 10).map((g) => g.word_id), [2, 3]);
  // Old grades are not sent a week later.
  assert.deepEqual(queue.readGradeQueue(storage, queue.GRADE_QUEUE_MAX_AGE_MS + 10), []);
});

test('the deck says it is offline or holding grades, and nothing when live', () => {
  assert.equal(queue.deckConnection({ online: false, queued: 0, syncing: false }).state, 'offline_cached');
  assert.equal(queue.deckConnection({ online: true, queued: 2, syncing: false }).state, 'pending_sync');
  assert.equal(queue.deckConnection({ online: true, queued: 2, syncing: true }).state, 'syncing');
  assert.equal(queue.deckConnection({ online: true, queued: 0, syncing: false }).state, 'live');
});

test('the review page queues a lost grade instead of asking the card again, and shows the banner', () => {
  const page = fs.readFileSync(path.join(WEB_ROOT, 'pages/vocabulary/review.tsx'), 'utf8');
  const lost = page.indexOf('if (gradeLostToNetwork(error))');
  assert.ok(lost > 0, 'the failed grade is checked for a lost network');
  assert.ok(page.indexOf('enqueueGrade(', lost) > lost);
  assert.ok(page.indexOf('return;', lost) < page.indexOf('reviewNotSaved(prev', lost));
  assert.match(page, /addEventListener\('online', reconnected\)/);
  assert.match(page, /sendQueuedGrades\(\)\.finally\(\(\) => loadQueue/);
  assert.match(page, /<ConnectionNotice/);
});
