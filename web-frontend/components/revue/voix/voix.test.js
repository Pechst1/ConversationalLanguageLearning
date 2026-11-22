// node --test components/revue/voix/voix.test.js
//
// «Papier · la voix» (2026-11-22, REVUE_VOIX_ENABLED), the client:
//
//   1. the wire: the manifest and the dictée parsed; a 404 (the switch off) resolves null; a
//      line goes to /voix/line and its bytes through the transport's clip;
//   2. the rules: a regular's line is heard first only while clips can be made, none failed,
//      it is still to be answered and not yet heard or opened; autoplay only after a gesture
//      with «voices aloud» on;
//   3. the bubble: without the voice exactly as before; with it, the line is ruled bars and
//      «Écouter» / «Lire» (no French, no reaction yet); the lead's control in the newsroom's voice;
//   4. the dev mock answers the routes the server's way (404 while `voix` is off; the line only
//      after two tries); every string in fr, en and de.

const assert = require('node:assert/strict');
const { test } = require('node:test');

const setup = require('../revue-test-setup');

const { h, render, visibleText } = setup;

const voixLib = require('../../../lib/revue-voix.ts');
const { withVoixMock } = require('../../../lib/revue-mock-voix.ts');
const { createMockRevueTransport } = require('../../../lib/revue-mock.ts');
const { createRevueClient } = require('../../../lib/revue-api.ts');
const model = require('./voix-model.ts');
const { VOIX_COPIES } = require('./voix-copy.ts');
const { VoixProvider, VoixScope } = require('./VoixContext.tsx');
const { VxLeadListen } = require('./VxParts.tsx');
const { ComptoirBubble } = require('../comptoir/RvComptoirParts.tsx');
const { revueCopy } = require('../revue-copy.ts');
const { comptoirCopy } = require('../comptoir/comptoir-copy.ts');

const TAKE = "Voyons donc, c'est une bonne nouvelle !";
const MANIFEST = voixLib.parseVoixManifest({
  audio: 'ready',
  newsreader_id: 'narrator',
  lines: [
    { kind: 'lead', speaker_id: 'narrator', text_fr: 'Le 17 octobre, Céline Dion a chanté à Paris.' },
    { kind: 'take', speaker_id: 'romy_tremblay', text_fr: TAKE },
    { kind: 'dance', speaker_id: 'x', text_fr: 'ignored' },
  ],
  dictee: { text_fr: 'La chanteuse revient en mai 2027.', words: 6, max_tries: 2 },
});

const notFound = () => Promise.reject(Object.assign(new Error('nf'), { response: { status: 404 } }));

// ---------------------------------------------------------------------------
// 1 · the wire
// ---------------------------------------------------------------------------

test('the manifest and the dictée parse; unknown kinds are dropped', () => {
  assert.equal(MANIFEST.audio, 'ready');
  assert.deepEqual(MANIFEST.lines.map((l) => l.kind), ['lead', 'take']);
  assert.equal(MANIFEST.dictee.maxTries, 2);
  const graded = voixLib.parseDicteeResult({ outcome: 'not_yet', attempt: 1, max_tries: 2, resolved: false, answer_fr: 'La chanteuse revien',
    marks: [{ span_fr: 'revien', start: 13, kind: 'orthographe' }, { span_fr: 'x', start: 0, kind: 'nope' }], expected_fr: null, note: null });
  assert.equal(graded.marks.length, 1);
  assert.equal(graded.expectedFr, null);
  assert.equal(voixLib.parseVoixManifest({ audio: 'weird' }).audio, 'device');
});

test('a 404 is the switch off: null; a line asks /voix/line and fetches its clip through the transport', async () => {
  const off = voixLib.createVoixClient({ get: notFound, post: notFound });
  assert.equal(await off.manifest('s1'), null);

  const posted = [];
  const fetched = [];
  const client = voixLib.createVoixClient({
    get: async () => ({}),
    post: async (url, body) => {
      posted.push([url, body]);
      return { status: 'ready', clip_id: 'nova-abc' };
    },
    clip: async (id) => {
      fetched.push(id);
      return new Blob(['x']);
    },
  });
  const resolve = client.resolver('s 1');
  global.URL.createObjectURL = () => 'blob:clip';
  global.URL.revokeObjectURL = () => {};
  const clip = await resolve({ text_fr: TAKE, character_id: 'romy_tremblay' });
  assert.equal(clip.url, 'blob:clip');
  assert.deepEqual(posted[0], ['/revue/sessions/s%201/voix/line', { text_fr: TAKE, character_id: 'romy_tremblay' }]);
  assert.deepEqual(fetched, ['nova-abc']);
  await resolve({ text_fr: TAKE, character_id: 'romy_tremblay' });
  assert.equal(posted.length, 1, 'a second play costs no request');
});

// ---------------------------------------------------------------------------
// 2 · the rules
// ---------------------------------------------------------------------------

test('a line is heard first only while it can be, and until it was heard or opened', () => {
  const key = model.heardKey('romy_tremblay', TAKE);
  const state = { manifest: MANIFEST, pending: [key], revealed: new Set(), failed: false };
  assert.equal(model.isVeiled(state, 'romy_tremblay', TAKE), true);
  assert.equal(model.isVeiled({ ...state, revealed: new Set([key]) }, 'romy_tremblay', TAKE), false, 'heard or «Lire»');
  assert.equal(model.isVeiled({ ...state, failed: true }, 'romy_tremblay', TAKE), false, 'a failed clip: the text at once');
  assert.equal(model.isVeiled({ ...state, manifest: { ...MANIFEST, audio: 'device' } }, 'romy_tremblay', TAKE), false, 'no speech: the text at once');
  assert.equal(model.isVeiled({ ...state, pending: [] }, 'romy_tremblay', TAKE), false, 'an answered take stays read');
  assert.equal(model.isVeiled(state, 'romy_tremblay', 'Une ligne de Romy.'), false, "not the session's line");
  assert.equal(model.isVeiled({ ...state, manifest: null }, 'romy_tremblay', TAKE), false, 'the switch off');
  assert.equal(model.isVeiled(state, 'narrator', MANIFEST.lines[0].textFr), false, 'the lead is never veiled');
});

test('pending lines: unanswered takes, the reply before the comeback', () => {
  const view = {
    cast: [
      { id: 'romy_tremblay', take: { fr: TAKE }, reaction: 'agree' },
      { id: 'margaux_barman', take: { fr: 'Moi, je suis contente.' }, reaction: null },
    ],
    opinion: { reply: { by: 'augustin_de_roncourt', line: { fr: 'Tu rêves !' } }, comeback: null },
  };
  assert.deepEqual(model.pendingLines(view), [model.heardKey('margaux_barman', 'Moi, je suis contente.'), model.heardKey('augustin_de_roncourt', 'Tu rêves !')]);
  view.opinion.comeback = { textFr: 'Non.' };
  assert.equal(model.pendingLines(view).length, 1);
  assert.deepEqual(model.pendingLines(null), []);
});

test('the veil sets as many ruled lines as the text; autoplay needs a gesture and the setting', () => {
  assert.deepEqual(model.veilLines('x'.repeat(34 * 2 + 17)), [100, 100, 50]);
  assert.deepEqual(model.veilLines(''), []);
  assert.equal(model.mayAutoplay({ voicesAloud: true, gesture: false }), false);
  assert.equal(model.mayAutoplay({ voicesAloud: false, gesture: true }), false);
  assert.equal(model.mayAutoplay({ voicesAloud: true, gesture: true }), true);
});

// ---------------------------------------------------------------------------
// 3 · the bubble and the lead
// ---------------------------------------------------------------------------

const voice = { speak: () => {}, stop: () => {}, speakingKey: null, supported: true, progress: () => null };
const copy = revueCopy('de');
const ccopy = comptoirCopy('de');

function bubble(textFr = TAKE) {
  return h(ComptoirBubble, {
    castId: 'romy_tremblay', name: 'Romy', textFr, stance: 'pour', glosses: [], glossLanguage: 'de', voice, voiceKey: 'k', copy, ccopy,
    children: h('div', { className: 'ct-react' }, 'd’accord'),
  });
}

function scoped(children, { manifest = MANIFEST, pending = [model.heardKey('romy_tremblay', TAKE)], failed = false } = {}) {
  return h(VoixProvider, { client: {} },
    h(VoixScope, { session: { id: 's1', manifest, failed, resolve: async () => null }, voice, pending, chrome: 'de', motherTongue: 'de' }, children));
}

test('without the voice the bubble is as before', () => {
  const html = render(bubble());
  assert.match(visibleText(html), /Voyons donc/);
  assert.match(html, /ct-react/);
  assert.doesNotMatch(html, /vx-/);
});

test('with the voice a pending take is heard first: ruled bars, «Anhören» and «Lesen», no words, no reaction yet', () => {
  const html = render(scoped(bubble()));
  assert.match(html, /vx-veil__line/);
  assert.doesNotMatch(visibleText(html), /Voyons donc/);
  assert.doesNotMatch(html, /ct-react/);
  assert.match(visibleText(html), /Anhören/);
  assert.match(visibleText(html), /Lesen/);
  assert.match(html, /class="vx-face"/, 'the face says it again');
  const device = render(scoped(bubble(), { manifest: { ...MANIFEST, audio: 'device' } }));
  assert.match(visibleText(device), /Voyons donc/, 'no speech: the text at once');
  const failed = render(scoped(bubble(), { failed: true }));
  assert.match(visibleText(failed), /Voyons donc/, 'a failed clip: the text at once');
});

test('the lead: the newsroom control with the voice, the player chip without', () => {
  const fallback = h('button', { className: 'rv-chip' }, 'Anhören');
  assert.equal(render(h(VxLeadListen, { textFr: 'Le lead.', fallback })), '<button class="rv-chip">Anhören</button>');
  const html = render(scoped(h(VxLeadListen, { textFr: 'Le lead.', fallback })));
  assert.match(visibleText(html), /Vorspann anhören/);
  assert.match(visibleText(html), /gelesen von der Redaktion/);
  assert.doesNotMatch(html, /rv-chip/);
});

// ---------------------------------------------------------------------------
// 4 · the mock and the copy
// ---------------------------------------------------------------------------

async function mockSession(options) {
  const transport = withVoixMock(createMockRevueTransport({ persist: false, comptoir: true, band: 'A2', language: 'de' }), options);
  const client = createRevueClient(transport);
  await client.week();
  const session = await client.start();
  return { transport, voix: voixLib.createVoixClient(transport), session };
}

test('the mock answers the server way: 404 while off, the session lines, the dictée solved only after two tries', async () => {
  const off = await mockSession({ enabled: false });
  assert.equal(await off.voix.manifest(off.session.id), null);

  const { transport, voix, session } = await mockSession({ enabled: true });
  const manifest = await voix.manifest(session.id);
  assert.equal(manifest.audio, 'ready');
  assert.deepEqual(manifest.lines.map((l) => l.kind), ['lead', 'take', 'take', 'take']);
  assert.ok(manifest.dictee && manifest.lines[0].textFr.includes(manifest.dictee.textFr));
  await assert.rejects(transport.post(`/revue/sessions/${session.id}/voix/line`, { text_fr: 'Achète.' }));
  const first = await voix.dictee(session.id, 'n’importe quoi', 1);
  assert.equal(first.resolved, false);
  assert.equal(first.expectedFr, null);
  const second = await voix.dictee(session.id, 'n’importe quoi', 2);
  assert.equal(second.expectedFr, manifest.dictee.textFr);
  const right = await voix.dictee(session.id, manifest.dictee.textFr.toLowerCase(), 1);
  assert.equal(right.outcome, 'met');

  const silent = await mockSession({ enabled: true, audio: false });
  const device = await silent.voix.manifest(silent.session.id);
  assert.equal(device.audio, 'device');
  assert.equal(device.dictee, null);
});

test('every string in fr, en and de', () => {
  const keys = Object.keys(VOIX_COPIES.fr).sort();
  for (const language of ['en', 'de']) {
    assert.deepEqual(Object.keys(VOIX_COPIES[language]).sort(), keys, language);
    for (const key of keys) assert.ok(VOIX_COPIES[language][key].trim(), `${language}.${key}`);
  }
});
