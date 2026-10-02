// node --test components/revue/revue-wire.test.js
//
// WP-119 phase 1 · the wire, client side.
//
//   1. every JSON example of docs/implementation/atelier-v2/WP-119-WIRE.md parses
//      (fixtures/wire-examples.json, copied verbatim), and so does every payload
//      the mock produces (fixtures/mock-wire.json — validated against
//      app/schemas/revue.py, extra=forbid);
//   2. snake_case → camelCase, field for field, with nothing invented;
//   3. errors: the flag-off 404 is `{ enabled: false }`, coded 404/409/422 become
//      typed RevueErrors carrying their `session_id` / `dossier_id` / `kind`;
//   4. request bodies go out in snake_case.

const assert = require('node:assert/strict');
const { test } = require('node:test');

const { fixture } = require('./revue-test-setup');

const types = require('../../lib/revue-types.ts');
const { createRevueClient, RevueError } = require('../../lib/revue-api.ts');

const WIRE = fixture('wire-examples');
const MOCK = fixture('mock-wire');

test('the wire document\'s offer example parses', () => {
  const offer = types.parseOffer(WIRE.offer);
  assert.deepEqual(offer.week, { iso: '2026-W40', label: 'Semaine 40', range: 'du 28 sept. au 4 oct.' });
  assert.equal(offer.recommended.dossierId, 'evergreen-marche-du-dimanche');
  assert.equal(offer.recommended.evergreen, true);
  assert.equal(offer.recommended.stage.platePlaceId, 'marche_canal');
  assert.equal(offer.recommended.stage.placeIsReal, false);
  assert.equal(offer.recommended.stage.dress, 'apron');
  assert.deepEqual(offer.recommended.stage.cast, [
    { id: 'romy_tremblay', hold: 'notebook' },
    { id: 'user', hold: null },
  ]);
  assert.equal(offer.recommendedReason, 'interests');
  assert.equal(offer.alternatives.length, 1);
  assert.equal(offer.alternatives[0].dossierId, 'evergreen-greve-transports');
  assert.equal(offer.evergreenOnly, true);
  assert.equal(offer.resume, null);
  assert.equal(offer.filed, null);
});

test('the wire document\'s match miss and turn examples parse', () => {
  assert.deepEqual(types.parseMatch(WIRE.match_miss), {
    match: null,
    romyLineFr: "Je n'ai que ça cette semaine, désolée. Le marché du dimanche à Aligre, ça te dit ?",
  });
  const turn = types.parseTurnResult(WIRE.turn);
  assert.deepEqual(turn.items.map((item) => item.kind), ['mine', 'line', 'uncertainty']);
  assert.equal(turn.items[0].textFr, 'Est-ce que les prix sont plus bas qu\'au supermarché ?');
  assert.equal(turn.items[1].role, 'reply');
  assert.equal(turn.items[1].speaker, 'romy_tremblay');
  assert.equal(turn.items[2].id, '11.u');
  assert.deepEqual(turn.room, { used: 2, phase: 'open', remainingTurns: 10 });
  assert.deepEqual(turn.support, { glosses: 'tap', translation: 'on_request', readingTargetWords: 90, vocabTarget: 5, level: 0 });
  assert.deepEqual(turn.quickReplies[0], { label: 'On formule la question', sendFr: 'On formule la question ensemble ?' });
  assert.equal(turn.steerToMake, false);
  assert.deepEqual(turn.evidence, { outcome: 'unscored', capabilityKnown: false, grader: 'revue-unscored-adapter-v1' });
});

test('every mock payload parses into the full client shapes', () => {
  const session = types.parseSessionView(MOCK.session_arrive);
  assert.equal(session.status, 'active');
  assert.equal(session.beat, 'arrive');
  assert.equal(session.plan.band, 'A1');
  assert.equal(session.plan.glossLanguage, 'de');
  assert.deepEqual(session.plan.makeOptions, ['headline_choice', 'reader_question']);
  assert.equal(session.plan.vocabulary.length, 5);
  assert.ok(session.plan.vocabulary.every((gloss) => gloss.fr && gloss.gloss && gloss.claimId));
  assert.deepEqual(session.thread.map((item) => item.kind), ['narration', 'narration', 'line', 'line', 'summary']);
  assert.deepEqual(session.thread.filter((item) => item.kind === 'line').map((item) => item.role), ['place_note', 'purpose']);
  assert.equal(session.quickReplies[0].sendFr, "D'accord, je t'aide.");

  const facts = types.parseTurnResult(MOCK.turn_facts);
  const claims = facts.items.find((item) => item.kind === 'claims');
  assert.equal(claims.claims.length, 2);
  assert.equal(claims.claims[0].source.publishedAt, '2026-09-23');
  assert.equal(claims.claims[0].attributedTo, null);

  const offer = types.parseMakeOffer(MOCK.make_offer);
  assert.equal(offer.recommended, 'reader_question');
  assert.deepEqual(offer.options.map((option) => option.kind), ['headline_choice', 'reader_question']);
  assert.equal(offer.options[0].options.length, 3);
  assert.match(offer.options[1].seedFr, /prix/);

  const propose = types.parseMakeResult(MOCK.make_propose);
  assert.equal(propose.kind, 'reader_question');
  assert.ok(propose.draft.proposalFr.startsWith('Est-ce que'));
  assert.ok(propose.draft.contribution.length >= 1);
  const send = types.parseMakeResult(MOCK.make_send);
  assert.equal(send.made.kind, 'reader_question');
  const pick = types.parseMakeResult(MOCK.make_pick);
  assert.equal(pick.kind, 'headline_choice');
  assert.equal(typeof pick.correct, 'boolean');
  assert.ok(pick.evidence.quote.length > 10);

  const close = types.parseCloseResult(MOCK.close);
  assert.equal(close.session.status, 'closed');
  assert.equal(close.closing.colophonFr, 'La suite la semaine prochaine.');
  assert.equal(close.closing.dispatch.bodyFr.length, 3);
  assert.ok(close.closing.kept.words.every((word) => typeof word.used === 'boolean'));

  const resume = types.parseOffer(MOCK.offer_resume);
  assert.equal(resume.resume.beat, 'pursue');
  assert.match(resume.resume.openQuestionFr, /prix/);
  const filed = types.parseOffer(MOCK.offer_filed);
  assert.equal(filed.filed.made.kind, 'reader_question');
  assert.equal(filed.filed.dispatch.kickerFr, 'Le Papier de Romy · semaine 40');

  for (const key of Object.keys(MOCK).filter((name) => name.startsWith('turn_'))) {
    const result = types.parseTurnResult(MOCK[key]);
    assert.ok(result.items.length >= 2, key);
    assert.equal(result.items[0].kind, 'mine', key);
  }
});

test('an unknown thread kind (a later phase\'s guest) is dropped, never guessed', () => {
  const thread = types.parseThread([
    { id: '1', seq: 1, at: 'x', kind: 'guest', text_fr: 'Bonjour' },
    { id: '2', seq: 2, at: 'x', kind: 'mine', text_fr: 'Salut', mode: 'voice' },
  ]);
  assert.deepEqual(thread.map((item) => item.kind), ['mine']);
  assert.equal(thread[0].mode, 'voice');
});

function fakeTransport(routes) {
  const calls = [];
  const reply = async (method, url, body) => {
    calls.push({ method, url, body });
    const answer = routes[`${method} ${url}`];
    if (!answer) throw Object.assign(new Error('404'), { response: { status: 404, data: { detail: 'Not Found' } } });
    if (answer.__error) throw Object.assign(new Error(String(answer.__error)), { response: { status: answer.__error, data: answer.body } });
    return answer;
  };
  return { calls, transport: { get: (url) => reply('GET', url, null), post: (url, body) => reply('POST', url, body) } };
}

test('the flag-off 404 on GET /revue/week is { enabled: false }; on with an offer, enabled', async () => {
  const off = createRevueClient(fakeTransport({}).transport);
  assert.deepEqual(await off.week(), { enabled: false });
  const on = createRevueClient(fakeTransport({ 'GET /revue/week': WIRE.offer }).transport);
  const week = await on.week();
  assert.equal(week.enabled, true);
  assert.equal(week.offer.recommended.titleFr, 'Le marché du dimanche à Aligre');
});

test('every coded error of the wire becomes a typed RevueError', async () => {
  const codes = [];
  for (const example of WIRE.errors) {
    const error = types.parseRevueError(example.status, example.body);
    assert.ok(error instanceof RevueError);
    codes.push(`${example.status} ${error.code}`);
  }
  assert.deepEqual(codes, [
    '404 revue_disabled',
    '404 revue_dossier_not_found',
    '409 revue_session_active',
    '409 revue_week_filed',
    '404 revue_session_not_found',
    '409 revue_session_closed',
    '409 revue_make_unavailable',
    '422 revue_unknown_option',
  ]);
  const active = types.parseRevueError(409, { detail: { code: 'revue_session_active', session_id: 'abc' } });
  assert.equal(active.sessionId, 'abc');
  const unavailable = types.parseRevueError(409, { detail: { code: 'revue_make_unavailable', kind: 'headline_choice' } });
  assert.equal(unavailable.makeKind, 'headline_choice');
  assert.equal(types.parseRevueError(422, { detail: [{ loc: ['body', 'text'] }] }).code, 'validation');
  assert.equal(types.parseRevueError(401, { detail: 'Not authenticated' }).code, 'unauthorized');

  const { transport } = fakeTransport({
    'POST /revue/sessions': { __error: 409, body: { detail: { code: 'revue_session_active', session_id: 's-1' } } },
  });
  const client = createRevueClient(transport);
  await assert.rejects(client.start({ dossierId: 'x' }), (error) => error instanceof RevueError && error.code === 'revue_session_active' && error.sessionId === 's-1');
  const offline = createRevueClient({ get: async () => { throw new Error('offline'); }, post: async () => { throw new Error('offline'); } });
  await assert.rejects(offline.session('s'), (error) => error.code === 'network');
});

test('request bodies go out in snake_case, on the wire\'s paths', async () => {
  const { calls, transport } = fakeTransport({
    'POST /revue/sessions': MOCK.session_arrive,
    'POST /revue/sessions/s%201/turns': MOCK.turn_facts,
    'POST /revue/sessions/s%201/make': MOCK.make_pick,
    'GET /revue/sessions/s%201/make': MOCK.make_offer,
    'POST /revue/sessions/s%201/close': MOCK.close,
    'POST /revue/match': WIRE.match_miss,
    'GET /revue/week?week=2026-W40': WIRE.offer,
  });
  const client = createRevueClient(transport);
  await client.start({ dossierId: 'evergreen-greve-transports', freeRequest: 'grève', angleId: 'a2', week: '2026-W40' });
  await client.turn('s 1', { text: 'Bonjour', clientTurnId: 't-1' });
  await client.make('s 1', { kind: 'headline_choice', action: 'pick', optionId: 'h2' });
  await client.make('s 1', { kind: 'reader_question', action: 'propose', text: 'les prix' });
  await client.make('s 1', { kind: 'reader_question', action: 'send', textFr: 'Est-ce que les prix ?' });
  await client.makeOffer('s 1');
  await client.close('s 1');
  await client.match('le cinéma', '2026-W40');
  await client.week('2026-W40');
  assert.deepEqual(calls.map((call) => [call.method, call.url, call.body]), [
    ['POST', '/revue/sessions', { week: '2026-W40', dossier_id: 'evergreen-greve-transports', free_request: 'grève', angle_id: 'a2' }],
    ['POST', '/revue/sessions/s%201/turns', { text: 'Bonjour', mode: 'text', client_turn_id: 't-1' }],
    ['POST', '/revue/sessions/s%201/make', { kind: 'headline_choice', action: 'pick', option_id: 'h2' }],
    ['POST', '/revue/sessions/s%201/make', { kind: 'reader_question', action: 'propose', text: 'les prix' }],
    ['POST', '/revue/sessions/s%201/make', { kind: 'reader_question', action: 'send', text_fr: 'Est-ce que les prix ?' }],
    ['GET', '/revue/sessions/s%201/make', null],
    ['POST', '/revue/sessions/s%201/close', {}],
    ['POST', '/revue/match', { text: 'le cinéma', week: '2026-W40' }],
    ['GET', '/revue/week?week=2026-W40', null],
  ]);
});
