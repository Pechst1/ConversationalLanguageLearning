// node --test components/courrier/courrier-no-reply.test.js
//
// #397 (child of #333) — a reply nobody wrote is shown as «not answered yet»,
// and the walks read the Courrier in the learner's time zone.
//
//   1. the server marks a turn nobody answered `reply_state: 'pending'`; the page
//      keeps the text in the composer and says so, in all three chrome languages;
//   2. every walk driver gives its browser a time zone, so the Courrier's stamps
//      are the learner's hours and not the machine's UTC (#316 «again»).

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));

const Module = require('node:module');
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

const read = (...parts) => fs.readFileSync(path.join(WEB_ROOT, ...parts), 'utf8');

test('a turn the server marks pending is a reply nobody gave', () => {
  const { replyPending } = require('./mission-turns.ts');
  assert.equal(replyPending({ reply_state: 'pending' }), true);
  assert.equal(replyPending({ reply_text: 'Ah bon ?', branch: {} }), false);
  assert.equal(replyPending(undefined), false);
  assert.equal(replyPending(null), false);
});

test('the page keeps the text and says nobody answered', () => {
  const page = read('pages', 'missions.tsx');
  const send = page.slice(page.indexOf('const sendReply'), page.indexOf('const recheckReply'));
  const pending = send.indexOf('replyPending(result.outcome)');
  assert.ok(pending > 0, 'sendReply never looks at the pending state');
  assert.ok(pending < send.indexOf("setReply('')"), 'the composer is emptied before the pending state is read');
  assert.match(send.slice(pending, send.indexOf("setReply('')")), /toast\(t\.toast_reply_pending\)/);
});

test('the pending line exists in every chrome language and is not the stock reply', () => {
  const { courrierCopy } = require('./courrier-copy.ts');
  for (const lang of ['fr', 'en', 'de']) {
    const line = courrierCopy(lang).toast_reply_pending;
    assert.ok(line && line.length > 20, `${lang}: no pending line`);
    assert.doesNotMatch(line, /je l.ai bien lu/i);
  }
});

test('every walk driver sets a time zone on its browser context', () => {
  for (const file of ['walk.mjs', 'explore.mjs', 'appels-walk.mjs', 'explore-live.mjs']) {
    const source = read('e2e', file);
    assert.match(source, /newContext\([^;]*timezoneId: WALK_TIMEZONE/s, `${file} walks in the machine's time zone`);
  }
  const zone = read('e2e', 'lib', 'walk-timezone.mjs');
  assert.match(zone, /Europe\/Berlin/);
});
