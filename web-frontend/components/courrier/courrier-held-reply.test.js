// node --test components/courrier/courrier-held-reply.test.js
//
// Pilot P0, walk of 17 Nov (A1, Lila): after «Senden» the thread only said «Lila hat
// auf diese Nachricht noch nicht geantwortet», one «Noch einmal nachfragen» changed
// nothing visible, and nothing said Lila was writing while the button worked.
//
//   1. the server now hands the character's acknowledgement on the unanswered message
//      (`held_reply`); the page prints it, in her voice, instead of a silent thread;
//   2. «… schreibt zurück» shows while a reply is asked for again, not only on send;
//   3. a retry that still brings no reply leaves a line under the message, not only a toast.

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

const PAGE = fs.readFileSync(path.join(WEB_ROOT, 'pages', 'missions.tsx'), 'utf8');
const pendingBlock = () => PAGE.slice(PAGE.indexOf('turnReplyPending(turn) &&'), PAGE.indexOf('<CrRepair'));

test('the held acknowledgement line exists in every chrome language, with the name and the text', () => {
  const { courrierCopy, crFill } = require('./courrier-copy.ts');
  for (const lang of ['fr', 'en', 'de']) {
    const line = courrierCopy(lang).reply_held_line;
    assert.ok(line, `${lang}: no reply_held_line`);
    const filled = crFill(line, { name: 'Lila', text: 'Merci pour ton message, je l’ai bien lu.' });
    assert.match(filled, /Lila/);
    assert.match(filled, /Merci pour ton message/);
  }
});

test('the page prints the held acknowledgement under the unanswered message', () => {
  const block = pendingBlock();
  assert.match(block, /turn\.held_reply/, 'the acknowledgement the server sent is never shown');
  assert.match(block, /t\.reply_held_line/);
  // Without one (an older server), the thread still says nobody answered.
  assert.match(block, /t\.reply_pending_line/);
});

test('the writing sign shows while a reply is asked for again', () => {
  const typing = PAGE.slice(PAGE.lastIndexOf('{', PAGE.indexOf('className="cr-typing"')) - 80, PAGE.indexOf('className="cr-typing"'));
  assert.match(typing, /submitting \|\| retryingReply/, 'no «schreibt zurück» while «Noch einmal nachfragen» works');
});

test('a retry that brings no reply leaves a line on the thread', () => {
  const retry = PAGE.slice(PAGE.indexOf('const retryReply'), PAGE.indexOf('const finishMission'));
  assert.match(retry, /setRetryMissed\(/, 'a failed retry is only a toast');
  assert.match(pendingBlock(), /retryMissed === turn\.id[\s\S]*t\.toast_reply_retry_failed/);
});
