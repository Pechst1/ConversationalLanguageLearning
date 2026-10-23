/**
 * Les appels — the client and the call's pure model.
 *
 * Run: `node --test lib/appels-api.test.js`
 */

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const WEB_ROOT = path.resolve(__dirname, '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));

const {
  appelsCopy,
  callClock,
  callerPortrait,
  createAppelsClient,
  lastCallerTurn,
  parseCall,
} = require('./appels-api.ts');
const { createMockAppelsClient } = require('./appels-mock.ts');

const LIVE = {
  id: 'c1',
  status: 'live',
  caller: { id: 'romy_tremblay', name: 'Romy', face: 'romy_tremblay' },
  turns: [
    { who: 'caller', text_fr: 'Allô ?', clip_id: 'nova-abc' },
    { who: 'learner', text_fr: 'Oui !', mode: 'voice' },
    { who: 'nobody', text_fr: 'dropped' },
  ],
  voicemail: null,
  turns_left: 2,
  reason_en: null,
};

test('a call parses, and unknown turns are dropped', () => {
  const call = parseCall(LIVE);
  assert.equal(call.status, 'live');
  assert.equal(call.turns.length, 2);
  assert.equal(call.turns[0].clip_id, 'nova-abc');
  assert.equal(parseCall({ id: 'x', status: 'dialling' }), null);
  assert.equal(parseCall(null), null);
});

test('the caller line, the clock and the face', () => {
  const call = parseCall({ ...LIVE, turns: [...LIVE.turns, { who: 'caller', text_fr: 'Super.' }] });
  assert.deepEqual(lastCallerTurn(call), { turn: { who: 'caller', text_fr: 'Super.', clip_id: null }, index: 2 });
  assert.equal(lastCallerTurn(null), null);
  assert.equal(callClock(125), '2:05');
  assert.equal(callClock(-3), '0:00');
  assert.equal(callerPortrait(call), '/assets/serial/drawn/romy_tremblay/portrait-neutre.png');
  assert.equal(callerPortrait({ ...call, caller: { ...call.caller, face: null } }), null);
});

test('the feature off reads as no call; other failures carry their code', async () => {
  const off = createAppelsClient({
    get: async () => {
      throw { response: { status: 404, data: { detail: 'Not Found' } } };
    },
    post: async () => {
      throw { response: { status: 409, data: { detail: { code: 'appel_not_live' } } } };
    },
  });
  assert.equal(await off.today(), null);
  await assert.rejects(off.say('c1', 'Allô', 'text'), (error) => error.status === 409 && error.code === 'appel_not_live');
});

test('the client posts to the call and reads the call back', async () => {
  const seen = [];
  const client = createAppelsClient({
    get: async (url) => {
      seen.push(['GET', url]);
      return { call: LIVE };
    },
    post: async (url, body) => {
      seen.push(['POST', url, body]);
      return { call: { ...LIVE, status: 'ended' } };
    },
  });
  assert.equal((await client.today()).id, 'c1');
  assert.equal((await client.say('c1', 'Bonsoir', 'voice')).status, 'ended');
  await client.hangUp('c1');
  assert.deepEqual(seen, [
    ['GET', '/appels/today'],
    ['POST', '/appels/c1/say', { text: 'Bonsoir', mode: 'voice' }],
    ['POST', '/appels/c1/hang-up', undefined],
  ]);
});

test('the copy speaks the learner chrome language, French by default', () => {
  assert.equal(appelsCopy('fr').calling('Romy'), 'Romy t’appelle');
  assert.equal(appelsCopy('en').calling('Romy'), 'Romy is calling');
  assert.equal(appelsCopy('de').calling('Romy'), 'Romy ruft an');
  assert.equal(appelsCopy(null).answer, 'Décrocher');
  assert.equal(appelsCopy('fr').turns_left(1), 'Encore une réplique');
});

test('the mock rings, talks three lines and ends', async () => {
  const client = createMockAppelsClient({ latency: 0 });
  assert.equal((await client.today()).status, 'ringing');
  assert.equal((await client.answer('mock-call')).status, 'live');
  await client.say('mock-call', 'Oui.', 'voice');
  await client.say('mock-call', 'Non.', 'text');
  const ended = await client.say('mock-call', 'Bonne soirée !', 'voice');
  assert.equal(ended.status, 'ended');
  assert.ok(ended.reason_en);
});
