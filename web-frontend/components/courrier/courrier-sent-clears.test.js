// node --test components/courrier/courrier-sent-clears.test.js
//
// #782 — after «Senden» the reply box is empty and «Senden» is off; a send that
// failed keeps the text.
//
// The walk of 14 Nov wrote to Margaux, tapped Senden, and the message stood in the
// thread with «Margaux hat auf diese Nachricht noch nicht geantwortet · Noch einmal
// nachfragen» under it — yet the box still held the same sentence and Senden was
// live. The message had gone out; only the answer was missing, and asking for the
// answer again lives on the thread (#590), not in the composer.
//
// These tests drive the page's own `sendReply` handler (taken from
// pages/missions.tsx and run against a stub API) and its own `canSend` rule, then
// render the real CrComposer with that rule, so the «Senden» they check is the
// button the learner sees.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));
const { transform } = require(path.join(WEB_ROOT, 'node_modules/sucrase'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

const realConsoleError = console.error;
console.error = (...args) => {
  if (String(args[0] || '').includes('non-boolean attribute')) return;
  realConsoleError(...args);
};

const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const Cr = require('./Courrier.tsx');
const turnsModule = require('./mission-turns.ts');
const { courrierCopy } = require('./courrier-copy.ts');
const { AtelierV2Root } = require('@/components/atelier-v2/ui/AtelierV2Root.tsx');

const h = React.createElement;
const PAGE = fs.readFileSync(path.join(WEB_ROOT, 'pages', 'missions.tsx'), 'utf8');
const t = courrierCopy('de');
const MISSION = { id: 'm-782', status: 'active', turns: [] };
const DRAFT_KEY = `pilot:mission-draft:${MISSION.id}`;
const WRITTEN = 'Salut Margaux ! oui je passe demain matin. Je ne suis plus fatigue. Merci pour le cafe !';

/** `const <name> = async (…) => { … };` from the page, as plain JS. */
function pageHandler(name) {
  const start = PAGE.indexOf(`const ${name} = async`);
  assert.ok(start >= 0, `pages/missions.tsx has no ${name}`);
  let i = PAGE.indexOf('=> {', start) + 3;
  let depth = 0;
  for (; i < PAGE.length; i += 1) {
    if (PAGE[i] === '{') depth += 1;
    else if (PAGE[i] === '}' && --depth === 0) break;
  }
  return transform(PAGE.slice(start, i + 1) + ';', { transforms: ['typescript'] }).code;
}

/** The page's `canSend` rule, evaluated for a given composer state. */
function canSendFor(state) {
  const match = PAGE.match(/const canSend = ([^;]+);/);
  assert.ok(match, 'pages/missions.tsx has no canSend rule');
  const names = Object.keys(state);
  return new Function(...names, `return (${match[1]});`)(...names.map((n) => state[n]));
}

/** The learner types WRITTEN and taps Senden; `submit` is what the server does. */
async function send(submit) {
  const page = { reply: WRITTEN, submitting: false, mission: MISSION, toasts: [], errors: [] };
  const storage = new Map([[DRAFT_KEY, JSON.stringify(WRITTEN)]]);
  const toast = (message) => page.toasts.push(message);
  toast.error = (message) => page.errors.push(message);
  toast.success = (message) => page.toasts.push(message);
  const scope = {
    ...turnsModule,
    mission: MISSION,
    reply: page.reply,
    submitting: false,
    completed: false,
    lapsed: false,
    t,
    toast,
    console: { ...console, error: () => undefined },
    window: { localStorage: { removeItem: (key) => storage.delete(key), setItem: (k, v) => storage.set(k, v) } },
    apiService: { submitMissionTurn: submit },
    setSubmitting: (value) => { page.submitting = value; },
    setMission: (value) => { page.mission = typeof value === 'function' ? value(page.mission) : value; },
    setReply: (value) => { page.reply = typeof value === 'function' ? value(page.reply) : value; },
  };
  const names = Object.keys(scope);
  const sendReply = new Function(...names, `${pageHandler('sendReply')}\nreturn sendReply;`)(
    ...names.map((n) => scope[n]),
  );
  await sendReply({ preventDefault: () => undefined });

  const canSend = canSendFor({ reply: page.reply, submitting: page.submitting, completed: false, lapsed: false });
  const html = renderToStaticMarkup(
    h(AtelierV2Root, { language: 'de' },
      h(Cr.CrComposer, { open: true, canSubmit: canSend, sending: page.submitting },
        h('textarea', { lang: 'fr', value: page.reply, readOnly: true }))),
  );
  const button = html.match(/<button[^>]*cr-send[^>]*>/);
  assert.ok(button, 'the composer has no send press');
  return { ...page, canSend, sendDisabled: /\sdisabled=""/.test(button[0]), draftKept: storage.has(DRAFT_KEY) };
}

const stored = (outcome) => async (missionId, body) => {
  assert.equal(missionId, MISSION.id);
  assert.equal(body.text, WRITTEN);
  return { mission: { ...MISSION, turns: [{ role: 'user', text: WRITTEN }] }, outcome };
};

test('a message the correspondent answered empties the box and turns Senden off', async () => {
  const after = await send(stored({ reply_text: 'Super, à demain !', branch: {} }));
  assert.equal(after.reply, '', 'the reply box still holds the sent text');
  assert.equal(after.sendDisabled, true, '«Senden» is still live after the send');
  assert.equal(after.draftKept, false, 'the sent text is still saved as a draft');
});

test('a message that went out but nobody answered yet empties the box too (#782)', async () => {
  const after = await send(stored({ reply_text: '', branch: {}, reply_state: 'pending' }));
  assert.equal(after.reply, '', 'the reply box still holds the sent text: a second tap would send it again');
  assert.equal(after.sendDisabled, true, '«Senden» is still live after the message went out');
  assert.equal(after.draftKept, false, 'the sent text comes back as a draft on the next visit');
  // The learner is still told nobody answered, and where to ask again (the thread, #590).
  assert.deepEqual(after.toasts, [t.toast_reply_pending]);
  assert.deepEqual(after.errors, []);
});

test('a send that failed keeps the text and Senden', async () => {
  const after = await send(async () => { throw new Error('network down'); });
  assert.equal(after.reply, WRITTEN, 'a failed send lost what the learner wrote');
  assert.equal(after.sendDisabled, false, '«Senden» is off after a failed send');
  assert.equal(after.draftKept, true, 'a failed send dropped the saved draft');
  assert.deepEqual(after.errors, [t.toast_send_failed]);
});
